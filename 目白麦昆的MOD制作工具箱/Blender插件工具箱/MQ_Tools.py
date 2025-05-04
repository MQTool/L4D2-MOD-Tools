import bpy
import os
import time
import requests
import shutil
import re
import math
import random
import uuid # Added import
import logging  # 添加日志模块
from typing import Dict, Set, List, Optional
from dataclasses import dataclass
from collections import defaultdict, Counter
from bpy.props import (StringProperty, BoolProperty, FloatProperty, EnumProperty,
                       IntProperty, PointerProperty, CollectionProperty)
from bpy.types import (Panel, Operator, PropertyGroup, UIList, Menu)
from mathutils import Vector

bl_info = {
    "name": "MQ Tools",
    "author": "地狱酱",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "视图3D > 侧边栏 > MQ Tools",
    "description": "多功能工具集（含快速拆分、描边工具、骨骼工具、VMT材质工具）",
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
    "category": "Object",
}

# PBR材质设置属性组
class PBRMaterialSettings(PropertyGroup):
    """PBR材质着色工具的设置"""
    log_to_file: BoolProperty(
        name="输出日志到文件",
        description="将详细执行日志输出到文件中",
        default=True
    )
    log_file_path: StringProperty(
        name="日志文件路径",
        description="指定日志文件输出的路径和文件名",
        subtype='FILE_PATH',
        default="//pbr_material_log.txt"  # 默认在Blender文件同目录
    )
    # 添加复制外部纹理设置
    copy_textures_externally: BoolProperty(
        name="复制纹理到外部文件夹",
        description="为每个材质创建纹理文件的物理副本到指定文件夹，避免导出合并",
        default=False
    )
    external_texture_directory: StringProperty(
        name="外部纹理文件夹",
        description="选择存储复制纹理的目标文件夹",
        subtype='DIR_PATH'
    )

# --------------------------------------------------------------------------
# 工具 1: 快速拆分助手 Pro
# --------------------------------------------------------------------------

# ------------------------- 辅助函数 -------------------------
def check_material_duplicate(self, context):
    """检查材质是否重复选择"""
    settings = context.scene.qseparator_settings
    current_item = None
    
    # 找到当前正在更新的项
    for item in settings.excluded_materials:
        if item == self:
            current_item = item
            break
    
    if not current_item or not current_item.material:
        return
    
    # 检查是否有其他项已经选择了相同的材质
    for item in settings.excluded_materials:
        if item != current_item and item.material == current_item.material:
            # 如果发现重复，清除当前选择
            current_item.material = None
            break

# ------------------------- 属性定义 -------------------------
class ExcludedItem(bpy.types.PropertyGroup):
    def poll_target(self, obj):
        # 只允许选择网格对象，且不能是已经被选择的对象
        settings = bpy.context.scene.qseparator_settings
        excluded_objects = {item.target for item in settings.excluded_items if item.target and item != self}
        return obj.type == 'MESH' and obj not in excluded_objects
    
    target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="排除对象",
        description="选择要排除的网格对象",
        poll=poll_target
    )

class ExcludedMaterial(bpy.types.PropertyGroup):
    def poll_material(self, material):
        # 只允许选择未被选择的材质
        settings = bpy.context.scene.qseparator_settings
        excluded_materials = {item.material for item in settings.excluded_materials if item.material and item != self}
        return material not in excluded_materials
    
    material: bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="排除材质",
        description="选择要排除的材质",
        poll=poll_material
    )

class QSeparatorSettings(bpy.types.PropertyGroup):
    excluded_items: bpy.props.CollectionProperty(type=ExcludedItem)
    active_index: bpy.props.IntProperty(default=-1)
    affect_output: bpy.props.BoolProperty(
        name="应用排除列表",
        default=True,
        description="启用时排除列表会影响所有生成内容"
    )
    export_mode: bpy.props.EnumProperty(
        name="输出模式",
        items=[
            ('GLB', "GLB模式", "生成GLB配置"),
            ('SMD', "SMD模式", "生成SMD配置"),
            ('DMX', "DMX模式", "生成DMX配置"),
        ],
        default='GLB',
        description="选择生成的配置类型"
    )
    translate_mode: bpy.props.EnumProperty(
        name="翻译模式",
        items=[
            ('NONE', "不翻译", "保持原始名称"),
            ('CH2EN', "中译英", "将中文翻译为英文并重命名材质"),
            ('EN2CH', "英译中", "将英文翻译为中文"),
            ('AI_CH2EN', "AI中译英", "使用AI将中文专业翻译为英文"),
            ('AI_EN2CH', "AI英译中", "使用AI将英文专业翻译为中文"),
        ],
        default='NONE',
        description="选择翻译模式"
    )
    api_key: bpy.props.StringProperty(
        name="API密钥",
        description="输入用于翻译的API密钥"
    )
    enable_auto_preprocess: bpy.props.BoolProperty(
        name="启用自动前置预处理",
        default=False,
        description="启用时将自动创建合集并整理对象"
    )
    enable_total_collection: bpy.props.BoolProperty(
        name="启用总合集",
        default=False,
        description="启用时将所有内容放入指定的总合集中"
    )
    total_collection_name: bpy.props.StringProperty(
        name="总合集名称",
        default="总合集",
        description="GLB模式下创建的总合集名称"
    )
    excluded_materials: bpy.props.CollectionProperty(type=ExcludedMaterial)
    material_active_index: bpy.props.IntProperty(default=-1)
    affect_materials: bpy.props.BoolProperty(
        name="应用材质排除",
        default=True,
        description="启用时材质排除列表会影响所有生成内容"
    )

# ------------------------- 核心逻辑 -------------------------
@dataclass
class CollectionInfo:
    """集合信息缓存类"""
    level: int
    parent: Optional[str]
    objects: List[str]

class CollectionCache:
    """集合缓存管理器"""
    def __init__(self):
        self.cache: Dict[str, CollectionInfo] = {}
        self.last_update = 0
    
    def update_cache(self, context) -> None:
        """更新集合缓存"""
        current_time = time.time()
        # 每秒最多更新一次缓存
        if current_time - self.last_update < 1.0:
            return
            
        self.cache.clear()
        scene_coll = context.scene.collection
        
        def process_collection(coll, parent_name: Optional[str], level: int):
            self.cache[coll.name] = CollectionInfo(
                level=level,
                parent=parent_name,
                objects=[obj.name for obj in coll.objects]
            )
            for child in coll.children:
                process_collection(child, coll.name, level + 1)
                
        process_collection(scene_coll, None, 0)
        self.last_update = current_time

# 创建全局缓存实例
collection_cache = CollectionCache()

def get_second_level_collections(context) -> List[str]:
    """获取所有第二层级的集合"""
    collection_cache.update_cache(context)
    return [name for name, info in collection_cache.cache.items() 
            if info.level == 2 and info.parent != "Collection"]

def generate_bodygroups(context):
    settings = context.scene.qseparator_settings
    excluded_objects = {item.target for item in settings.excluded_items if item.target} if settings.affect_output else set()
    excluded_materials = {item.material for item in settings.excluded_materials if item.material} if settings.affect_materials else set()
    
    config_entries = []
    second_level_colls = get_second_level_collections(context)
    
    for coll_name in second_level_colls:
        coll = bpy.data.collections.get(coll_name)
        if not coll or not coll.objects:
            continue
            
        # 检查集合是否包含排除对象或材质
        contains_excluded_obj = any(obj in excluded_objects for obj in coll.objects)
        contains_excluded_mat = any(mat in excluded_materials 
                                  for obj in coll.objects 
                                  for mat in obj.data.materials if mat)

        # 生成配置条目
        config_entry = generate_config_entry(
            coll, 
            settings.export_mode, 
            settings.translate_mode, 
            include_blank=not (contains_excluded_obj or contains_excluded_mat)
        )
        if config_entry:
            config_entries.append(config_entry)
    
    return '\n'.join(config_entries) if config_entries else "// 没有可生成的配置内容"

def translate_text(text: str, mode: str) -> str:
    """统一的翻译处理函数"""
    settings = bpy.context.scene.qseparator_settings
    
    if mode == 'NONE' or not settings.api_key:
        return text

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.api_key}"
    }
    
    if mode.startswith('AI_'):
        if mode == 'AI_CH2EN':
            system_prompt = """你是一个专业的游戏MOD组件翻译专家，特别擅长将中文3D模型相关术语翻译为英文。
翻译规则：
1. 专注于游戏模组和3D模型组件的专业翻译
2. "描边"统一翻译为"Outline"
3. 使用下划线连接英文单词
4. 保持专业术语的准确性
5. 只返回翻译结果，不要有任何解释或额外内容
6. 使用游戏开发领域常用的英文术语
7. Up或者Down这类词语意思主要为方向相关

例如：
- 基础描边 -> Base_Outline
- 头部装甲 -> Head_Armor
- 武器特效 -> Weapon_Effect"""
        else:  # AI_EN2CH
            system_prompt = """你是一个专业的游戏MOD组件翻译专家，特别擅长处理3D模型相关的专业术语翻译。
翻译规则：
1. 专注于游戏模组和3D模型组件的准确翻译
2. Outline统一翻译为"描边"
3. 移除名称中的下划线，使用更自然的中文表达
4. 保持专业术语的准确性
5. 只返回翻译结果，不要有任何解释或额外内容
6. 使用游戏领域常用的中文术语
7. Up或者Down这类词语意思主要为方向相关

例如：
- Base_Outline -> 基础描边
- Head_Armor -> 头部装甲
- Weapon_Effect -> 武器特效"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请翻译以下游戏模组组件名称：{text}"}
        ]
    else:
        direction = "中文翻译为英文" if mode == 'CH2EN' else "英文翻译为中文"
        messages = [
            {"role": "user", "content": f"请将以下{direction}，只需要返回翻译结果：\n{text}"}
        ]
    
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.1
    }
    
    try:
        print(f"正在翻译: {text}")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        translated_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
        if translated_text:
            print(f"翻译结果: {translated_text}")
            return translated_text
        else:
            print("翻译返回为空")
            return text
            
    except Exception as e:
        print(f"翻译时出错: {str(e)}")
        return text

def generate_config_entry(collection, export_mode: str, translate_mode: str, include_blank: bool = True) -> str:
    """生成单个集合的配置条目"""
    original_name = collection.name
    translated_name = None
    settings = bpy.context.scene.qseparator_settings
    
    # 检查是否为排除的材质
    excluded_materials = {item.material.name for item in settings.excluded_materials if item.material}
    if original_name in excluded_materials:
        # 如果是排除的材质，使用原始名称
        display_name = original_name
        node_name = original_name
    else:
        # 正常的翻译逻辑
        if translate_mode in {'CH2EN', 'AI_CH2EN'}:
            translated_name = translate_text(original_name, translate_mode)
            display_name = original_name
            node_name = translated_name
        else:
            display_name = translate_text(original_name, translate_mode) if translate_mode != 'NONE' else original_name
            node_name = original_name
    
    # 修改：统一使用4个空格的缩进
    indent = "    "
    blank_line = "    blank\n" if include_blank else ""
    
    if export_mode == 'DMX':
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio "{node_name}.dmx"\n'
                f'{blank_line}'
                '}\n')
    elif export_mode == 'SMD':
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio "{node_name}.smd"\n'
                f'{blank_line}'
                '}\n')
    else:
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio $custom_model$ InNode {node_name}\n'
                f'{blank_line}'
                '}\n')

def auto_preprocess(context):
    """自动前置预处理：整理对象和集合结构"""
    settings = context.scene.qseparator_settings
    total_collection_name = settings.total_collection_name.strip() or "总合集"
    
    try:
        # 获取或创建总合集
        total_collection = bpy.data.collections.get(total_collection_name)
        if not total_collection:
            total_collection = bpy.data.collections.new(total_collection_name)
            context.scene.collection.children.link(total_collection)
        
        # 处理场景中的网格对象
        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
                
            # 检查对象是否已在合适的集合中
            current_collections = obj.users_collection
            
            # 如果对象没有集合或只在主集合中
            if not current_collections or (len(current_collections) == 1 and current_collections[0] == context.scene.collection):
                # 创建或获取同名集合
                obj_collection = bpy.data.collections.get(obj.name)
                if not obj_collection:
                    obj_collection = bpy.data.collections.new(obj.name)
                    total_collection.children.link(obj_collection)
                
                # 从其他集合中移除对象
                for coll in current_collections:
                    coll.objects.unlink(obj)
                
                # 将对象添加到新集合
                obj_collection.objects.link(obj)
            
            # 如果对象已在自定义集合中，确保该集合在总合集下
            else:
                for coll in current_collections:
                    if coll != context.scene.collection and coll != total_collection:
                        # 如果集合不在总合集中，移动到总合集下
                        if coll.name not in total_collection.children:
                            # 先从其他父集合中解除链接
                            for parent_coll in bpy.data.collections:
                                if coll.name in parent_coll.children:
                                    parent_coll.children.unlink(coll)
                            # 链接到总合集
                            total_collection.children.link(coll)
        
        # 清理空集合
        for coll in bpy.data.collections:
            if (coll != context.scene.collection and 
                coll != total_collection and 
                not coll.objects and 
                not coll.children):
                bpy.data.collections.remove(coll)
        
        return {'FINISHED'}
        
    except Exception as e:
        return {'CANCELLED'}

# ------------------------- 操作符 -------------------------
class QSEPARATOR_OT_CopyText(bpy.types.Operator):
    bl_idname = "qseparator.copy_text"
    bl_label = "复制配置文本"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        text = generate_bodygroups(context)
        context.window_manager.clipboard = text
        count = text.count('$bodygroup')
        
        # 如果是中译英模式，自动处理材质翻译
        if settings.translate_mode in {'CH2EN', 'AI_CH2EN'}:
            processed = 0
            for mat in bpy.data.materials:
                translated_name = translate_text(mat.name, settings.translate_mode)
                if translated_name != mat.name:
                    mat.name = translated_name  # 直接使用翻译后的名称，不添加前缀
                    processed += 1
            if processed > 0:
                self.report({'INFO'}, f"已复制{count}个配置项并翻译{processed}个材质")
            else:
                self.report({'INFO'}, f"已复制{count}个配置项" if count else "没有可生成的内容")
        else:
            self.report({'INFO'}, f"已复制{count}个配置项" if count else "没有可生成的内容")
        return {'FINISHED'}

class QSEPARATOR_OT_AddSearchItem(bpy.types.Operator):
    bl_idname = "qseparator.add_search_item"
    bl_label = "添加排除项"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        settings.excluded_items.add()
        settings.active_index = len(settings.excluded_items) - 1
        return {'FINISHED'}

class QSEPARATOR_OT_RemoveSearchItem(bpy.types.Operator):
    bl_idname = "qseparator.remove_search_item"
    bl_label = "移除选中项"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        if 0 <= settings.active_index < len(settings.excluded_items):
            settings.excluded_items.remove(settings.active_index)
            settings.active_index = min(settings.active_index, len(settings.excluded_items)-1)
        return {'FINISHED'}

class QSEPARATOR_OT_ClearAllItems(bpy.types.Operator):
    bl_idname = "qseparator.clear_all_items"
    bl_label = "清空所有项"
    
    def execute(self, context):
        context.scene.qseparator_settings.excluded_items.clear()
        return {'FINISHED'}

class QSEPARATOR_OT_QuickSeparate(bpy.types.Operator):
    bl_idname = "qseparator.quick_separate"
    bl_label = "执行智能拆分"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.qseparator_settings
        total_collection = None
        
        # 如果是GLB模式且启用了总合集功能，处理总合集
        if (settings.export_mode == 'GLB' and 
            settings.enable_total_collection and 
            settings.total_collection_name.strip()):
            
            total_collection_name = settings.total_collection_name.strip()
            
            # 获取或创建总合集
            total_collection = bpy.data.collections.get(total_collection_name)
            if not total_collection:
                total_collection = bpy.data.collections.new(total_collection_name)
                context.scene.collection.children.link(total_collection)
            
            # 将所有非主集合移动到总合集下
            for coll in bpy.data.collections:
                if (coll != context.scene.collection and 
                    coll != total_collection and 
                    coll.name not in total_collection.children):
                    # 从当前父级解除链接
                    for parent_coll in bpy.data.collections:
                        if coll.name in parent_coll.children:
                            parent_coll.children.unlink(coll)
                    # 链接到总合集
                    total_collection.children.link(coll)
            
            # 处理骨架对象
            for obj in context.scene.objects:
                if obj.type == 'ARMATURE':
                    # 从其他集合中移除
                    for coll in obj.users_collection:
                        coll.objects.unlink(obj)
                    # 添加到总合集
                    total_collection.objects.link(obj)

        excluded_objects = {item.target for item in settings.excluded_items if item.target}

        target_objects = [
            obj for obj in context.scene.objects 
            if obj.type == 'MESH' 
            and obj not in excluded_objects
            and obj.name.lower() != "face"
        ]

        if not target_objects:
            self.report({'WARNING'}, "没有可操作的对象")
            return {'CANCELLED'}

        original_active = context.view_layer.objects.active
        original_selected = set(context.selected_objects)

        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in target_objects:
                obj.select_set(True)
            context.view_layer.objects.active = target_objects[-1]

            # 执行材质分离
            if context.object.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.separate(type='MATERIAL')
            bpy.ops.object.mode_set(mode='OBJECT')

            # 处理分离后的对象
            new_objects = [obj for obj in context.selected_objects if obj not in original_selected]
            for obj in new_objects:
                if obj.type != 'MESH' or not obj.data.materials:
                    continue

                mat_name = obj.data.materials[0].name
                obj.name = mat_name  # 直接使用材质名称，不添加_mesh后缀
                
                # 创建/获取材质集合
                collection = bpy.data.collections.get(mat_name)
                if not collection:
                    collection = bpy.data.collections.new(mat_name)
                    # 如果启用了总合集，将新集合放入总合集
                    if total_collection and settings.enable_total_collection:
                        total_collection.children.link(collection)
                    else:
                        context.scene.collection.children.link(collection)
                
                # 移动对象到集合
                for coll in obj.users_collection:
                    coll.objects.unlink(obj)
                collection.objects.link(obj)

            # 清理空集合
            self.cleanup_empty_collections()

        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selected:
                obj.select_set(True)
            context.view_layer.objects.active = original_active

        return {'FINISHED'}

    def cleanup_empty_collections(self):
        """清理所有空集合"""
        empty_collections = [
            coll for coll in bpy.data.collections
            if coll.name != "Collection"
            and not coll.children
            and len(coll.objects) == 0
        ]

        for coll in reversed(empty_collections):
            try:
                for scene in bpy.data.scenes:
                    scene_collection = scene.collection
                    if coll.name in scene_collection.children:
                        scene_collection.children.unlink(coll)
                bpy.data.collections.remove(coll)
            except Exception as e:
                print(f"清理集合时出错: {str(e)}")

# 添加材质列表操作符 
class QSEPARATOR_OT_AddMaterialItem(bpy.types.Operator):
    bl_idname = "qseparator.add_material_item"
    bl_label = "添加材质排除"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        # 获取已选择的材质
        excluded_mats = {item.material for item in settings.excluded_materials if item.material}
        # 检查是否还有未选择的材质
        available_mats = [mat for mat in bpy.data.materials if mat not in excluded_mats]
        
        if available_mats:
            item = settings.excluded_materials.add()
            settings.material_active_index = len(settings.excluded_materials) - 1
        else:
            self.report({'WARNING'}, "没有可用的材质可以添加")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class QSEPARATOR_OT_RemoveMaterialItem(bpy.types.Operator):
    bl_idname = "qseparator.remove_material_item"
    bl_label = "移除材质"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        if 0 <= settings.material_active_index < len(settings.excluded_materials):
            settings.excluded_materials.remove(settings.material_active_index)
            settings.material_active_index = min(settings.material_active_index, len(settings.excluded_materials)-1)
        return {'FINISHED'}

class QSEPARATOR_OT_ClearAllMaterials(bpy.types.Operator):
    bl_idname = "qseparator.clear_all_materials"
    bl_label = "清空材质"
    
    def execute(self, context):
        context.scene.qseparator_settings.excluded_materials.clear()
        return {'FINISHED'}

class QSEPARATOR_OT_OrganizeOutlines(bpy.types.Operator):
    bl_idname = "qseparator.organize_outlines"
    bl_label = "整理描边合集"
    bl_description = "将Outline前缀的合集放入对应的基础合集中"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        collections = bpy.data.collections
        outline_collections = {}
        base_collections = {}
        
        # 分类合集
        for coll in collections:
            if coll.name.startswith("Outline_"):
                # 获取基础名称（去掉Outline_前缀）
                base_name = coll.name[8:]  # 跳过"Outline_"
                outline_collections[base_name] = coll
            else:
                base_collections[coll.name] = coll
        
        processed_count = 0
        
        # 整理描边合集
        for base_name, outline_coll in outline_collections.items():
            # 严格匹配基础名称
            matching_base = base_collections.get(base_name)
            
            if matching_base:
                # 检查描边合集是否已经在正确的位置
                already_child = False
                for child in matching_base.children:
                    if child == outline_coll:
                        already_child = True
                        break
                
                if not already_child:
                    # 从当前父级解除链接
                    for parent_coll in collections:
                        try:
                            if outline_coll.name in parent_coll.children:
                                parent_coll.children.unlink(outline_coll)
                        except:
                            continue
                    
                    # 链接到新的父级
                    try:
                        matching_base.children.link(outline_coll)
                        processed_count += 1
                        print(f"已移动 {outline_coll.name} 到 {matching_base.name}")
                    except Exception as e:
                        print(f"移动合集 {outline_coll.name} 时出错: {str(e)}")
        
        if processed_count > 0:
            self.report({'INFO'}, f"已整理 {processed_count} 个描边合集")
        else:
            self.report({'INFO'}, "没有需要整理的描边合集")
            
        return {'FINISHED'}

class QSEPARATOR_OT_SelectItem(bpy.types.Operator):
    bl_idname = "qseparator.select_item"
    bl_label = "选择列表项"
    index: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.qseparator_settings.active_index = self.index
        return {'FINISHED'}

class QS_UL_ExcludedItems(bpy.types.UIList):
    """优化的排除列表UI"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # 显示对象图标和名称
            if item.target:
                obj = bpy.data.objects.get(item.target)
                if obj:
                    row.label(text="", icon=f'OUTLINER_OB_{obj.type}')
                    row.prop(item, "target", text="", emboss=False)
                    # 显示所属集合
                    if obj.users_collection:
                        row.label(text=f"在 {obj.users_collection[0].name} 中")
                else:
                    row.label(text="无效对象", icon='ERROR')
            else:
                row.label(text="未选择对象", icon='QUESTION')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OBJECT_DATA')

# --------------------------------------------------------------------------
# 工具 2: 快速选择特定名称骨骼
# --------------------------------------------------------------------------

class BONE_OT_SelectBonesByKeyword(bpy.types.Operator):
    bl_idname = "object.select_bones_by_keyword"
    bl_label = "快速根据名称选择骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        keyword = scene.bone_keyword
        case_sensitive = scene.case_sensitive

        if not keyword:
            self.report({'WARNING'}, "关键词不能为空")
            return {'CANCELLED'}

        # 确保我们在对象模式中清除选择
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in bpy.context.object.data.bones:
            bone.select = False

        # 切换到姿态模式以选择骨骼
        bpy.ops.object.mode_set(mode='POSE')

        for bone in bpy.context.object.pose.bones:
            # 根据区分大小写选项比较关键词
            if (keyword in bone.name if case_sensitive else keyword.lower() in bone.name.lower()):
                bone.bone.select = True

        # 返回到姿态模式
        bpy.ops.object.mode_set(mode='POSE')

        self.report({'INFO'}, "已成功选择骨骼")
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 工具 3: 目白麦昆的一键描边插件
# --------------------------------------------------------------------------

def add_outline(context, size, all_objects):
    """实际执行描边操作的函数"""
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    if all_objects:
        objs = [obj for obj in bpy.data.objects if obj.type == 'MESH' and not obj.name.startswith("Outline_")]  # 只选择网格对象，排除描边对象
    else:
        objs = [obj for obj in context.selected_objects if obj.type == 'MESH' and not obj.name.startswith("Outline_")]  # 只选择选中的网格对象，排除描边对象

    outline_mode = context.scene.outline_mode

    for obj in objs:
        # 跳过名称包含 "smd_bone_vis" 的对象
        if "smd_bone_vis" in obj.name.lower():
            print(f"跳过 {obj.name}，因为它与 'smd_bone_vis' 相关。")
            continue

        outline_obj_name = "Outline_" + obj.name

        # 检查是否已有对应的描边对象，避免重复创建
        if bpy.data.objects.get(outline_obj_name):
            print(f"{outline_obj_name} 已存在，跳过描边创建。")
            continue

        outline_obj = obj.copy()
        outline_obj.data = obj.data.copy()  # 复制网格数据
        outline_obj.name = outline_obj_name  # 新对象的名称为 "Outline_原对象名"

        # 根据用户选择的模式放置描边对象到相应的集合中
        if outline_mode == 'ORIGINAL':
            # 放到与原始对象相同的集合
            for collection in obj.users_collection:
                collection.objects.link(outline_obj)
        elif outline_mode == 'SINGLE':
            # 放到统一的集合中
            outline_collection = bpy.data.collections.get("Outline_Collection")
            if not outline_collection:
                outline_collection = bpy.data.collections.new(name="Outline_Collection")
                bpy.context.scene.collection.children.link(outline_collection)
            outline_collection.objects.link(outline_obj)
        elif outline_mode == 'SEPARATE':
            # 为每个描边对象创建单独的集合
            collection_name = outline_obj_name
            if collection_name not in bpy.data.collections:
                new_collection = bpy.data.collections.new(name=collection_name)
                bpy.context.scene.collection.children.link(new_collection)
            new_collection = bpy.data.collections[collection_name]
            new_collection.objects.link(outline_obj)

        obj.select_set(False)

        new_materials = []

        # **执行逻辑 1: 使用特定材质**
        if context.scene.use_named_materials:
            if "hair" in obj.name.lower():
                hair_material = bpy.data.materials.get("Outline_Hair")
                if hair_material is None:
                    hair_material = bpy.data.materials.new(name="Outline_Hair")
                    hair_material.diffuse_color = (0, 0, 0, 1)
                new_materials.append(hair_material)

            elif "face" in obj.name.lower():
                face_material = bpy.data.materials.get("Outline_Face")
                if face_material is None:
                    face_material = bpy.data.materials.new(name="Outline_Face")
                    face_material.diffuse_color = (0, 0, 0, 1)
                new_materials.append(face_material)

            else:
                # 如果既不是 "hair" 也不是 "face"，第一个材质使用 Outline_Base
                outline_base_material = bpy.data.materials.get("Outline_Base")
                if outline_base_material is None:
                    outline_base_material = bpy.data.materials.new(name="Outline_Base")
                    outline_base_material.diffuse_color = (0, 0, 0, 1)
                new_materials.append(outline_base_material)

        # **执行逻辑 2: 使用统一 Outline_Base 材质**
        elif context.scene.use_outline_base:
            outline_base_material = bpy.data.materials.get("Outline_Base")
            if outline_base_material is None:
                outline_base_material = bpy.data.materials.new(name="Outline_Base")
                outline_base_material.diffuse_color = (0, 0, 0, 1)
            new_materials.append(outline_base_material)

        # **执行逻辑 3: 只加 Outline_ 前缀 (当两者关闭时)**
        for mat in obj.data.materials[len(new_materials):]:  # 确保保留其他材质
            new_material = bpy.data.materials.new(name="Outline_" + mat.name)
            new_material.diffuse_color = (0, 0, 0, 1)
            new_materials.append(new_material)

        # 清除并重新分配材质
        outline_obj.data.materials.clear()
        for new_material in new_materials:
            outline_obj.data.materials.append(new_material)

        # 保留原模型的材质分配（即面与材质插槽的关系）
        outline_mesh = outline_obj.data
        for poly in outline_mesh.polygons:
            poly.material_index = obj.data.polygons[poly.index].material_index

        bpy.ops.object.select_all(action='DESELECT')
        outline_obj.select_set(True)
        bpy.context.view_layer.objects.active = outline_obj

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.flip_normals()

        bpy.ops.transform.shrink_fatten(value=size)

        bpy.ops.object.mode_set(mode='OBJECT')

        print(f"已为 {obj.name} 添加描边")

def delete_outline_objects_and_collections(context):
    """删除所有描边对象和相关的集合，并清理孤立数据"""
    outline_objects = [obj for obj in bpy.data.objects if obj.name.startswith("Outline_")]
    outline_collections = [col for col in bpy.data.collections if col.name.startswith("Outline_")]

    if outline_objects:
        bpy.ops.object.select_all(action='DESELECT')  # 清除所有选择
        for obj in outline_objects:
            # 检查对象是否在当前视图层中
            if obj.visible_get():
                obj.select_set(True)  # 选择描边对象
        bpy.ops.object.delete()  # 删除选中的对象

        # 删除空的 Outline_ 开头的集合
        for collection in outline_collections:
            if not collection.objects:  # 只有集合为空时才删除
                bpy.data.collections.remove(collection)

        # 清理孤立数据（孤立的材质、网格、集合等）
        bpy.ops.outliner.orphans_purge(do_recursive=True)

        print("所有描边对象及相关集合已删除，并清理孤立数据。")
    else:
        print("没有找到描边对象或集合。")

def copy_smd_to_clipboard(context):
    """生成 SMD 文本并复制到剪贴板，根据不同模式输出不同的 SMD 内容"""
    smd_export_lines = []
    outline_mode = context.scene.outline_mode
    include_all_models = context.scene.include_all_models

    if outline_mode == 'SINGLE':
        # 统一集合模式，输出单个 $body，集合名为 "Outline_Collection"
        outline_collection = bpy.data.collections.get("Outline_Collection")
        if outline_collection:
            smd_line = f"$body {outline_collection.name} \"{outline_collection.name}.smd\""
            smd_export_lines.append(smd_line)

    elif outline_mode == 'ORIGINAL':
        # 原集合模式，输出每个原模型所在集合
        for obj in bpy.data.objects:
            if obj.name.startswith("Outline_") and obj.type == 'MESH':
                for collection in obj.users_collection:
                    smd_line = f"$body {collection.name} \"{collection.name}.smd\""
                    smd_export_lines.append(smd_line)

    elif outline_mode == 'SEPARATE':
        # 单独集合模式，输出每个描边对象的名称
        for obj in bpy.data.objects:
            if obj.name.startswith("Outline_") and obj.type == 'MESH':
                smd_line = f"$body {obj.name} \"{obj.name}.smd\""
                smd_export_lines.append(smd_line)

    # 如果选择了 "输出全部" 选项，添加原始模型的 SMD 文本
    if include_all_models:
        for obj in bpy.data.objects:
            # 排除名称包含 "smd_bone_vis" 和 "face" 的对象
            if obj.type == 'MESH' and not obj.name.lower().startswith("outline_") and "face" not in obj.name.lower() and "smd_bone_vis" not in obj.name.lower():
                smd_line = f"$body {obj.name} \"{obj.name}.smd\""
                smd_export_lines.append(smd_line)

    # 将生成的 SMD 文本复制到剪贴板
    smd_text = "\n".join(smd_export_lines)
    context.window_manager.clipboard = smd_text
    return smd_text

class OUTLINE_OT_AddAll(bpy.types.Operator):
    """为所有模型对象添加描边"""
    bl_idname = "outline.add_all"
    bl_label = "快速描边"

    def execute(self, context):
        add_outline(context, -abs(context.scene.outline_size), all_objects=True)  # 将输入值转为负值
        return {'FINISHED'}

class OUTLINE_OT_AddSelected(bpy.types.Operator):
    """为选中的模型对象添加描边"""
    bl_idname = "outline.add_selected"
    bl_label = "选择描边"

    def execute(self, context):
        add_outline(context, -abs(context.scene.outline_size), all_objects=False)  # 将输入值转为负值
        bpy.context.space_data.shading.show_backface_culling = True
        return {'FINISHED'}

class OUTLINE_OT_DeleteAll(bpy.types.Operator):
    """删除所有描边对象"""
    bl_idname = "outline.delete_all"
    bl_label = "删除所有描边"

    def execute(self, context):
        delete_outline_objects_and_collections(context)
        return {'FINISHED'}

class OUTLINE_OT_CopySMD(bpy.types.Operator):
    """生成 SMD 文本并复制到剪贴板"""
    bl_idname = "outline.copy_smd"
    bl_label = "复制描边模型文本"

    def execute(self, context):
        smd_text = copy_smd_to_clipboard(context)  # 调用复制到剪贴板的函数
        self.report({'INFO'}, "SMD 文本已复制到剪贴板")
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 工具 4: 清除骨骼自定义形状
# --------------------------------------------------------------------------

class BONE_OT_ClearCustomShapes(bpy.types.Operator):
    bl_idname = "bone.clear_custom_shapes"
    bl_label = "清除自定义形状"
    bl_description = "清除所有骨骼的自定义形状"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # A获取当前选中的骨架
        armature = context.active_object
        
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选择一个骨架")
            return {'CANCELLED'}
            
        # 切换到姿态模式以访问骨骼属性
        original_mode = armature.mode
        bpy.ops.object.mode_set(mode='POSE')
        
        # 清除所有骨骼的自定义形状
        cleared_count = 0
        for bone in armature.pose.bones:
            if bone.custom_shape:
                bone.custom_shape = None
                cleared_count += 1
                
        # 恢复原始模式
        bpy.ops.object.mode_set(mode=original_mode)
        
        self.report({'INFO'}, f"已清除 {cleared_count} 个骨骼的自定义形状")
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 工具 5: VMT材质批量复制工具
# --------------------------------------------------------------------------

def clean_material_name(name):
    """清理材质名称（去除扩展名和数字后缀）"""
    # 去除所有文件扩展名（.png, .vmt等）
    name = re.sub(r'\.[^.]+$', '', name)
    # 去除数字后缀（如.001）
    name = re.sub(r'\.\d+$', '', name)
    return name.lower()  # 转换为小写以进行比较

class MaterialGroupItem(PropertyGroup):
    is_selected: BoolProperty(
        name="选择",
        default=False
    )
    name: StringProperty(name="材质名称")
    source_vmt: StringProperty(
        name="源VMT",
        description="选择源VMT文件",
        subtype='FILE_PATH'
    )

class VMT_OT_RefreshList(Operator):
    bl_idname = "vmt.refresh_list"
    bl_label = "刷新材质列表"
    
    def execute(self, context):
        scene = context.scene
        # 清除现有列表
        scene.material_groups.clear()
        
        if not scene.source_vmt_path:
            self.report({'ERROR'}, "请先选择源VMT文件夹")
            return {'CANCELLED'}
        
        # 获取源文件夹中的材质名称
        source_materials = set()
        if os.path.exists(scene.source_vmt_path):
            for f in os.listdir(scene.source_vmt_path):
                if f.endswith('.vmt'):
                    base_name = clean_material_name(f)
                    source_materials.add(base_name)
                    print(f"Found source material: {base_name}")
        
        # 添加场景中的所有不同名材质到列表
        excluded_keywords = {'点笔划', '点', '笔划', 'stroke', 'dot'}  # 添加更多需要排除的关键词
        for mat in bpy.data.materials:
            # 检查材质名称是否包含任何需要排除的关键词
            should_exclude = any(keyword.lower() in mat.name.lower() for keyword in excluded_keywords)
            if not mat.name.startswith('.') and not should_exclude:
                clean_name = clean_material_name(mat.name)
                print(f"Checking material: {mat.name} (cleaned: {clean_name})")
                if clean_name not in source_materials:
                    item = scene.material_groups.add()
                    item.name = mat.name
                    item.is_selected = False
                    print(f"Added to list: {mat.name}")
        
        if len(scene.material_groups) == 0:
            self.report({'INFO'}, "没有需要处理的新材质")
        else:
            self.report({'INFO'}, f"找到 {len(scene.material_groups)} 个需要处理的材质")
        
        return {'FINISHED'}

class VMT_OT_AssignSource(Operator):
    bl_idname = "vmt.assign_source"
    bl_label = "指定源材质"
    
    filepath: StringProperty(
        name="源VMT文件",
        description="选择要应用的VMT文件",
        subtype='FILE_PATH'
    )
    
    filter_glob: StringProperty(
        default="*.vmt",
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "请选择源VMT文件")
            return {'CANCELLED'}
            
        # 为所有选中项设置源材质
        for item in context.scene.material_groups:
            if item.is_selected:
                item.source_vmt = self.filepath
                item.is_selected = False  # 自动取消选择已指定的材质
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class VMT_OT_CopyMaterials(Operator):
    bl_idname = "vmt.copy_materials"
    bl_label = "复制材质"
    
    def execute(self, context):
        scene = context.scene
        if not scene.target_vmt_path:
            self.report({'ERROR'}, "请先选择目标路径")
            return {'CANCELLED'}
            
        # 将Blender的相对路径转换为绝对路径
        target_path = bpy.path.abspath(scene.target_vmt_path)
        
        # 确保路径格式正确并使用正确的分隔符
        target_path = os.path.normpath(target_path)
        
        # 确保目标路径存在
        try:
            os.makedirs(target_path, exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, f"创建目标路径失败: {str(e)}")
            return {'CANCELLED'}
        
        # 复制材质文件
        copied_count = 0
        for item in scene.material_groups:
            if item.source_vmt and os.path.exists(item.source_vmt):
                # 构建目标文件路径
                target_file = os.path.join(target_path, f"{clean_material_name(item.name)}.vmt")
                try:
                    shutil.copy2(item.source_vmt, target_file)
                    copied_count += 1
                except Exception as e:
                    self.report({'WARNING'}, f"复制材质 {item.name} 时出错: {str(e)}")
        
        self.report({'INFO'}, f"成功复制 {copied_count} 个材质文件")
        return {'FINISHED'}

class VMT_OT_SelectAll(Operator):
    bl_idname = "vmt.select_all"
    bl_label = "全选"
    
    def execute(self, context):
        for item in context.scene.material_groups:
            if not item.source_vmt:  # 只选择未指定源材质的项
                item.is_selected = True
        return {'FINISHED'}

class VMT_OT_DeselectAll(Operator):
    bl_idname = "vmt.deselect_all"
    bl_label = "取消全选"
    
    def execute(self, context):
        for item in context.scene.material_groups:
            item.is_selected = False
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 主面板 - 工具选择器
# --------------------------------------------------------------------------

class MQT_PT_SeparatorPanel(Panel):
    bl_label = "快速拆分助手 Pro"
    bl_idname = "MQT_PT_SeparatorPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.qseparator_settings
        
        # 添加关于信息
        info_box = layout.box()
        info_box.label(text="MQ Tools 版本 1.0.0", icon='INFO')
        info_box.label(text="作者: 地狱酱")
        
        # 只在GLB模式下显示总合集相关设置
        if settings.export_mode == 'GLB':
            box = layout.box()
            box.label(text="总合集设置:", icon='OUTLINER_COLLECTION')
            box.prop(settings, "enable_total_collection")
            if settings.enable_total_collection:
                box.prop(settings, "total_collection_name")
        
        # 主操作区
        main_col = layout.column(align=True)
        main_col.operator(QSEPARATOR_OT_QuickSeparate.bl_idname, icon='MOD_EXPLODE')
        
        # 配置生成区
        config_box = layout.box()
        config_box.label(text="配置生成设置:", icon='SETTINGS')
        config_box.prop(settings, "export_mode", text="输出模式")
        config_box.prop(settings, "affect_output", text="应用排除")
        
        # 操作按钮
        config_box.operator(QSEPARATOR_OT_CopyText.bl_idname, 
                          text="生成QC配置", 
                          icon='TEXT')
        
        # 排除列表管理
        ex_box = layout.box()
        ex_box.label(text="对象排除列表:", icon='CANCEL')
        
        # 列表控制按钮
        ctrl_row = ex_box.row(align=True)
        
        # 检查是否还有可选择的对象
        available_objects = [obj for obj in context.scene.objects 
                           if obj.type == 'MESH' and 
                           obj not in {item.target for item in settings.excluded_items if item.target}]
        
        # 使用子行来控制启用状态
        add_row = ctrl_row.row()
        add_row.enabled = bool(available_objects)
        add_row.operator(QSEPARATOR_OT_AddSearchItem.bl_idname, icon='ADD')
        
        ctrl_row.operator(QSEPARATOR_OT_RemoveSearchItem.bl_idname, icon='REMOVE')
        ctrl_row.operator(QSEPARATOR_OT_ClearAllItems.bl_idname, icon='TRASH')
        
        # 动态列表项
        list_col = ex_box.column(align=True)
        for idx, item in enumerate(settings.excluded_items):
            row = list_col.row(align=True)
            # 只显示未被选择的网格对象
            row.prop_search(
                item, "target",
                context.scene, "objects",
                text="",
                icon='OBJECT_DATA'
            )
            row.operator("qseparator.select_item", 
                        text="", 
                        icon='RADIOBUT_ON' if idx == settings.active_index else 'RADIOBUT_OFF', 
                        emboss=False).index = idx

        # 翻译设置
        translate_box = layout.box()
        translate_box.label(text="翻译设置:", icon='WORLD_DATA')
        translate_box.prop(settings, "translate_mode")
        
        # 仅在选择了需要API的翻译模式时显示API密钥输入框
        if settings.translate_mode != 'NONE':
            translate_box.prop(settings, "api_key")

        # 材质排除列表
        mat_box = layout.box()
        mat_box.label(text="材质排除列表:", icon='MATERIAL')
        mat_box.prop(settings, "affect_materials", text="应用材质排除")
        
        # 检查是否还有可选择的材质
        available_materials = [mat for mat in bpy.data.materials 
                             if mat not in {item.material for item in settings.excluded_materials if item.material}]
        
        # 材质列表控制按钮
        mat_row = mat_box.row(align=True)
        add_mat_row = mat_row.row()
        add_mat_row.enabled = bool(available_materials)
        add_mat_row.operator(QSEPARATOR_OT_AddMaterialItem.bl_idname, icon='ADD')
        
        mat_row.operator(QSEPARATOR_OT_RemoveMaterialItem.bl_idname, icon='REMOVE')
        mat_row.operator(QSEPARATOR_OT_ClearAllMaterials.bl_idname, icon='TRASH')
        
        # 材质列表
        mat_list_col = mat_box.column(align=True)
        for item in settings.excluded_materials:
            row = mat_list_col.row(align=True)
            row.prop_search(item, "material", bpy.data, "materials", text="")

        # 确保描边整理按钮显示
        layout.separator()
        outline_box = layout.box()
        outline_box.label(text="描边整理:", icon='OUTLINER_OB_LIGHT')
        outline_box.operator(QSEPARATOR_OT_OrganizeOutlines.bl_idname, icon='OUTLINER_COLLECTION')

# --------------------------------------------------------------------------
# 骨骼选择器面板
# --------------------------------------------------------------------------
class MQT_PT_BoneSelectorPanel(Panel):
    bl_label = "快速根据名称选择骨骼"
    bl_idname = "MQT_PT_BoneSelectorPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 输入关键字和选项
        layout.prop(scene, "bone_keyword")
        layout.prop(scene, "case_sensitive")
        
        # 选择骨骼按钮
        layout.operator("object.select_bones_by_keyword", text="选择骨骼")

# 描边工具面板
class MQT_PT_OutlinePanel(Panel):
    bl_label = "一键描边"
    bl_idname = "MQT_PT_OutlinePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 描边大小输入框
        layout.prop(scene, "outline_size", text="描边大小 (米)")

        # 描边模式选择
        layout.prop(scene, "outline_mode", text="描边放置模式")

        # 材质开关
        layout.prop(scene, "use_outline_base", text="使用统一 Outline_Base 材质")
        
        # 分类材质开关，禁用状态取决于 use_outline_base 的值
        row = layout.row()
        row.enabled = scene.use_outline_base
        row.prop(scene, "use_named_materials", text="根据名称使用特定材质")

        # 输出全部选项
        layout.prop(scene, "include_all_models", text="输出全部")

        # 快速描边按钮（为所有对象添加描边）
        row = layout.row()
        row.operator("outline.add_all", text="快速描边")

        # 选择描边按钮（只为选中的对象添加描边）
        row = layout.row()
        row.operator("outline.add_selected", text="选择描边")

        # 删除描边按钮
        row = layout.row()
        row.operator("outline.delete_all", text="删除所有描边")

        # 复制描边模型文本按钮
        row = layout.row()
        row.operator("outline.copy_smd", text="复制描边模型文本")

# --------------------------------------------------------------------------
# 工具 4: 清除骨骼自定义形状面板
# --------------------------------------------------------------------------
class MQT_PT_BoneShapePanel(Panel):
    bl_label = "骨骼形状清除工具"
    bl_idname = "MQT_PT_BoneShapePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        
        # 添加操作按钮
        box = layout.box()
        box.operator("bone.clear_custom_shapes", icon='BONE_DATA')
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明:", icon='INFO')
        box.label(text="1. 选择目标骨架")
        box.label(text="2. 点击清除按钮即可")

# --------------------------------------------------------------------------
# VMT材质批量复制工具面板
# --------------------------------------------------------------------------
class MQT_PT_VMTPanel(Panel):
    bl_label = "VMT材质批量复制工具"
    bl_idname = "MQT_PT_VMTPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # 路径设置
        box = layout.box()
        box.label(text="路径设置:")
        box.prop(scene, "source_vmt_path", text="源VMT文件夹")
        box.prop(scene, "target_vmt_path", text="目标VMT路径")
        
        # 刷新按钮
        layout.operator("vmt.refresh_list", text="刷新材质列表", icon='FILE_REFRESH')
        
        # 材质列表
        if len(scene.material_groups) > 0:
            # 未指定源材质的材质列表
            box = layout.box()
            box.label(text="待处理材质:")
            
            # 全选按钮（只针对未指定源材质的材质）
            row = box.row()
            row.operator("vmt.select_all", text="全选")
            row.operator("vmt.deselect_all", text="取消全选")
            
            # 显示未指定源材质的材质
            for item in scene.material_groups:
                if not item.source_vmt:  # 只显示未指定源材质的材质
                    row = box.row()
                    row.prop(item, "is_selected", text="")
                    row.label(text=item.name)
            
            # 已指定源材质的材质列表
            box = layout.box()
            box.label(text="已指定材质:")
            for item in scene.material_groups:
                if item.source_vmt:  # 显示已指定源材质的材质
                    row = box.row()
                    row.label(text=item.name)
                    row.label(text=os.path.basename(item.source_vmt))
            
            # 源材质指定和复制按钮
            row = layout.row()
            row.operator("vmt.assign_source", text="指定源材质")
            row.operator("vmt.copy_materials", text="复制材质")
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明:", icon='INFO')
        box.label(text="1. 设置源VMT文件夹和目标路径")
        box.label(text="2. 点击'刷新材质列表'")
        box.label(text="3. 选择要分组的材质")
        box.label(text="4. 点击'指定源材质'选择VMT文件")
        box.label(text="5. 重复3-4步骤处理其他组")
        box.label(text="6. 点击'复制材质'完成操作")

# --------------------------------------------------------------------------
# 工具 4: 骨骼工具
# --------------------------------------------------------------------------

def transfer_weights(self, from_bone_name, to_bone_name, mesh):
    """
    改进的权重转移函数
    """
    # 确保目标权重组存在
    if to_bone_name not in mesh.vertex_groups:
        mesh.vertex_groups.new(name=to_bone_name)
    
    # 获取源和目标权重组
    from_group = mesh.vertex_groups.get(from_bone_name)
    to_group = mesh.vertex_groups.get(to_bone_name)
    
    if not from_group:
        return
    
    # 存储每个顶点的权重
    weights = {}
    for vertex in mesh.data.vertices:
        try:
            weight = from_group.weight(vertex.index)
            if weight > 0:
                weights[vertex.index] = weight
        except RuntimeError:
            continue
    
    # 转移权重
    if weights:
        # 添加新权重
        for vertex_index, weight in weights.items():
            try:
                current_weight = 0
                try:
                    current_weight = to_group.weight(vertex_index)
                except RuntimeError:
                    pass
                # 使用 'REPLACE' 模式确保权重正确设置
                to_group.add([vertex_index], current_weight + weight, 'REPLACE')
            except RuntimeError:
                continue
    
    # 删除原始权重组
    mesh.vertex_groups.remove(from_group)

class BONE_OT_merge_to_parent(Operator):
    bl_idname = "bone.merge_to_parent"
    bl_label = "合并到父级"
    bl_description = "将选中的骨骼合并到它们的父级骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    @staticmethod
    def transfer_weights(from_bone_name, to_bone_name, mesh):
        """
        改进的权重转移函数
        """
        # 确保目标权重组存在
        if to_bone_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=to_bone_name)
        
        # 获取源和目标权重组
        from_group = mesh.vertex_groups.get(from_bone_name)
        to_group = mesh.vertex_groups.get(to_bone_name)
        
        if not from_group:
            return
        
        # 存储每个顶点的权重
        weights = {}
        for vertex in mesh.data.vertices:
            try:
                weight = from_group.weight(vertex.index)
                if weight > 0:
                    weights[vertex.index] = weight
            except RuntimeError:
                continue
        
        # 转移权重
        if weights:
            # 添加新权重
            for vertex_index, weight in weights.items():
                try:
                    current_weight = 0
                    try:
                        current_weight = to_group.weight(vertex_index)
                    except RuntimeError:
                        pass
                    # 使用 'REPLACE' 模式确保权重正确设置
                    to_group.add([vertex_index], current_weight + weight, 'REPLACE')
                except RuntimeError:
                    continue
        
        # 删除原始权重组
        mesh.vertex_groups.remove(from_group)
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE' and
                context.selected_pose_bones)
    
    def get_final_parent(self, bone, bones_to_process):
        """
        获取骨骼的最终父级（考虑多层级合并）
        """
        current = bone.parent
        while current:
            # 检查当前父级是否也在处理列表中
            is_parent_processed = any(b[0] == current for b in bones_to_process)
            if is_parent_processed:
                current = current.parent
            else:
                break
        return current
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        
        # 存储要处理的骨骼，并按层级深度排序
        bones_to_process = []
        for pose_bone in context.selected_pose_bones:
            if pose_bone.parent:
                # 计算骨骼的层级深度
                depth = 0
                temp_bone = pose_bone
                while temp_bone.parent:
                    depth += 1
                    temp_bone = temp_bone.parent
                bones_to_process.append((pose_bone, pose_bone.parent, depth))
        
        # 按深度从大到小排序（先处理子骨骼）
        bones_to_process.sort(key=lambda x: x[2], reverse=True)
        
        # 切换到对象模式以修改骨骼
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 处理每个选中的骨骼
        for bone, _, _ in bones_to_process:
            # 获取最终的父级骨骼
            final_parent = self.get_final_parent(bone, bones_to_process)
            if not final_parent:
                continue
            
            # 直接转移权重到最终父级
            for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
                self.transfer_weights(bone.name, final_parent.name, mesh)
        
        # 切换到编辑模式删除骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 删除骨骼
        for bone, _, _ in bones_to_process:
            if bone.name in armature.edit_bones:
                edit_bone = armature.edit_bones[bone.name]
                # 如果骨骼有子级，先将子级的父级设置为最终父级
                if edit_bone.children:
                    final_parent = self.get_final_parent(bone, bones_to_process)
                    if final_parent and final_parent.name in armature.edit_bones:
                        for child in edit_bone.children:
                            child.parent = armature.edit_bones[final_parent.name]
                armature.edit_bones.remove(edit_bone)
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        return {'FINISHED'}

class BONE_OT_merge_to_active(Operator):
    bl_idname = "bone.merge_to_active"
    bl_label = "合并到活动骨骼"
    bl_description = "将选中的骨骼合并到活动骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    @staticmethod
    def transfer_weights(from_bone_name, to_bone_name, mesh):
        """
        改进的权重转移函数
        """
        # 确保目标权重组存在
        if to_bone_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=to_bone_name)
        
        # 获取源和目标权重组
        from_group = mesh.vertex_groups.get(from_bone_name)
        to_group = mesh.vertex_groups.get(to_bone_name)
        
        if not from_group:
            return
        
        # 存储每个顶点的权重
        weights = {}
        for vertex in mesh.data.vertices:
            try:
                weight = from_group.weight(vertex.index)
                if weight > 0:
                    weights[vertex.index] = weight
            except RuntimeError:
                continue
        
        # 转移权重
        if weights:
            # 添加新权重
            for vertex_index, weight in weights.items():
                try:
                    current_weight = 0
                    try:
                        current_weight = to_group.weight(vertex_index)
                    except RuntimeError:
                        pass
                    # 使用 'REPLACE' 模式确保权重正确设置
                    to_group.add([vertex_index], current_weight + weight, 'REPLACE')
                except RuntimeError:
                    continue
        
        # 删除原始权重组
        mesh.vertex_groups.remove(from_group)
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_pose_bone and
                len(context.selected_pose_bones) > 1)
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        active_bone = context.active_pose_bone
        
        # 存储要处理的骨骼
        bones_to_process = [bone for bone in context.selected_pose_bones if bone != active_bone]
        
        # 切换到对象模式以修改骨骼
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 处理每个选中的骨骼
        for bone in bones_to_process:
            # 转移权重到活动骨骼
            for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
                self.transfer_weights(bone.name, active_bone.name, mesh)
        
        # 切换到编辑模式删除骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in bones_to_process:
            if bone.name in armature.edit_bones:
                edit_bone = armature.edit_bones[bone.name]
                armature.edit_bones.remove(edit_bone)
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        return {'FINISHED'}

class BONE_OT_remove_zero_weight(Operator):
    bl_idname = "bone.remove_zero_weight"
    bl_label = "清除零权重骨骼"
    bl_description = "删除所有没有权重的骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    include_with_children: BoolProperty(
        name="包含有子级的骨骼",
        description="同时删除带有子骨骼的零权重骨骼",
        default=False
    )
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE')
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        bones_to_remove = []
        
        # 收集所有骨骼的权重信息
        weight_data = {}
        for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
            for vertex_group in mesh.vertex_groups:
                # 初始化权重数据
                if vertex_group.name not in weight_data:
                    weight_data[vertex_group.name] = 0.0
                
                # 计算该骨骼的总权重
                for vertex in mesh.data.vertices:
                    try:
                        weight = vertex_group.weight(vertex.index)
                        weight_data[vertex_group.name] += weight
                    except RuntimeError:
                        continue
        
        # 检查每个骨骼
        for bone in armature.bones:
            # 如果骨骼没有权重组或权重为0
            if bone.name not in weight_data or weight_data[bone.name] < 0.0001:
                # 根据选项决定是否包含有子级的骨骼
                if not bone.children or self.include_with_children:
                    bones_to_remove.append(bone.name)
        
        if not bones_to_remove:
            self.report({'INFO'}, "没有找到零权重骨骼")
            return {'CANCELLED'}
        
        # 切换到编辑模式删除骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 删除收集到的零权重骨骼
        removed_count = 0
        for bone_name in bones_to_remove:
            if bone_name in armature.edit_bones:
                edit_bone = armature.edit_bones[bone_name]
                # 如果骨骼有子级，先将子级的父级设置为当前骨骼的父级
                if self.include_with_children and edit_bone.children:
                    parent = edit_bone.parent
                    for child in edit_bone.children:
                        child.parent = parent
                armature.edit_bones.remove(edit_bone)
                removed_count += 1
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        self.report({'INFO'}, f"已删除 {removed_count} 个零权重骨骼")
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "include_with_children")

class BONE_OT_apply_pose_transform(Operator):
    bl_idname = "bone.apply_pose_transform"
    bl_label = "应用姿态变换"
    bl_description = "将当前姿态设为静止姿态"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE')
    
    def execute(self, context):
        armature_obj = context.active_object
        
        # 存储所有使用该骨架的网格对象及其修改器信息
        mesh_modifiers = []
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object == armature_obj:
                        mesh_modifiers.append((obj, mod.name))
        
        # 切换到物体模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 处理每个网格对象
        for obj, mod_name in mesh_modifiers:
            # 确保网格数据是单独的
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            
            # 如果对象有形态键，我们需要特殊处理
            if obj.data.shape_keys:
                # 存储原始形态键值
                original_values = {}
                for kb in obj.data.shape_keys.key_blocks:
                    original_values[kb.name] = kb.value
                
                # 存储每个形态键的变形位置
                shape_key_positions = {}
                
                # 对每个形态键创建一个临时对象
                for kb in obj.data.shape_keys.key_blocks:
                    if kb.name != "Basis":
                        # 创建临时对象
                        temp_obj = obj.copy()
                        temp_obj.data = obj.data.copy()
                        bpy.context.scene.collection.objects.link(temp_obj)
                        
                        # 重置所有形态键值为0，然后设置当前形态键为1
                        for temp_kb in temp_obj.data.shape_keys.key_blocks:
                            temp_kb.value = 1.0 if temp_kb.name == kb.name else 0.0
                        
                        # 让形态键生效
                        bpy.context.view_layer.update()
                        
                        # 评估修改器
                        depsgraph = bpy.context.evaluated_depsgraph_get()
                        temp_obj_eval = temp_obj.evaluated_get(depsgraph)
                        
                        # 创建一个新的网格数据来存储当前状态
                        temp_mesh = bpy.data.meshes.new_from_object(temp_obj_eval)
                        
                        # 删除原始临时对象
                        bpy.data.objects.remove(temp_obj, do_unlink=True)
                        
                        # 存储变形后的位置
                        shape_key_positions[kb.name] = [v.co.copy() for v in temp_mesh.vertices]
                        
                        # 删除临时网格
                        bpy.data.meshes.remove(temp_mesh)
                
                # 创建基础形状的临时对象
                base_obj = obj.copy()
                base_obj.data = obj.data.copy()
                bpy.context.scene.collection.objects.link(base_obj)
                
                # 重置所有形态键值为0
                for kb in base_obj.data.shape_keys.key_blocks:
                    kb.value = 0
                
                # 让形态键生效
                bpy.context.view_layer.update()
                
                # 评估修改器
                depsgraph = bpy.context.evaluated_depsgraph_get()
                base_obj_eval = base_obj.evaluated_get(depsgraph)
                
                # 创建一个新的网格数据来存储当前状态
                base_mesh = bpy.data.meshes.new_from_object(base_obj_eval)
                
                # 删除原始基础对象
                bpy.data.objects.remove(base_obj, do_unlink=True)
                
                # 存储基础位置
                base_positions = [v.co.copy() for v in base_mesh.vertices]
                
                # 删除基础网格
                bpy.data.meshes.remove(base_mesh)
                
                # 删除原始对象的形态键
                obj.shape_key_clear()
                
                # 应用原始对象的修改器
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.modifier_apply(modifier=mod_name)
                
                # 重新创建形态键
                basis = obj.shape_key_add(name="Basis")
                basis.interpolation = 'KEY_LINEAR'
                
                # 使用存储的位置创建形态键
                for name, positions in shape_key_positions.items():
                    key_block = obj.shape_key_add(name=name)
                    key_block.interpolation = 'KEY_LINEAR'
                    
                    # 直接使用变形后的位置
                    for i, pos in enumerate(positions):
                        key_block.data[i].co = pos
                    
                    # 恢复原始值
                    key_block.value = original_values[name]
                
                # 重新添加骨架修改器
                mod = obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = armature_obj
                mod.use_vertex_groups = True
                mod.use_bone_envelopes = False
                
                obj.select_set(False)
            else:
                # 对于没有形态键的对象，直接应用修改器
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.modifier_apply(modifier=mod_name)
                
                # 重新添加骨架修改器
                mod = obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = armature_obj
                mod.use_vertex_groups = True
                mod.use_bone_envelopes = False
                
                obj.select_set(False)
        
        # 选择骨架对象
        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)
        
        # 切换到姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        # 应用姿态为静止姿态
        bpy.ops.pose.armature_apply(selected=False)
        
        # 切换回物体模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 应用骨架的变换
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        
        # 切换回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        self.report({'INFO'}, "已成功应用姿态变换")
        return {'FINISHED'}

class BONE_OT_GFL2_preprocess(Operator):
    bl_idname = "object.gfl2_preprocess" # 修改 bl_idname 以反映操作对象
    bl_label = "少前2模型一键预处理" # 修改 bl_label
    bl_description = "一键处理少前2模型：缩放，应用姿态和变换，处理特定骨骼，删除lod1模型，处理face模型顶点组，清理零权重骨骼(保留眼睛骨骼)" # 修改 bl_description
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 允许在物体模式或姿态模式下启动，只要活动对象是骨架
        return (context.active_object and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选择一个骨架对象")
            return {'CANCELLED'}

        armature = obj.data
        original_mode = context.mode # 记录原始模式

        try:
            # --- 最终调整后的顺序 --- #

            # --- 1. 删除LOD1模型 (物体模式) --- <--- 使用 bpy.data.objects.remove() 重构
            print("步骤 1: 删除 LOD1 模型 (直接移除)...")
            if context.mode != 'OBJECT': # 确保在物体模式
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT') # 清理选择以防万一

            deleted_lod_count = 0
            # 收集需要删除的对象名称，因为在迭代时直接删除可能导致问题
            objects_to_delete_names = [o.name for o in bpy.data.objects if o.type == 'MESH' and 'lod1' in o.name.lower()]
            
            if objects_to_delete_names:
                print(f"  - 找到 {len(objects_to_delete_names)} 个 LOD1 模型准备删除...")
                for obj_name in objects_to_delete_names:
                    obj_to_delete = bpy.data.objects.get(obj_name)
                    if obj_to_delete: # 确保对象仍然存在
                        try:
                            bpy.data.objects.remove(obj_to_delete, do_unlink=True)
                            print(f"    - 已移除对象: {obj_name}")
                            deleted_lod_count += 1
                        except Exception as e_remove_lod1:
                            print(f"    - 移除对象 '{obj_name}' 时出错 (可能已被删除或有特殊链接): {e_remove_lod1}")
                print(f"  - 完成 LOD1 模型移除尝试，移除了 {deleted_lod_count} 个。")
            else:
                print("  - 未找到 LOD1 模型。")

            # --- 2. 缩放 (物体模式) ---
            print("步骤 2: 缩放骨架...")
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            # 确保只选择骨架
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.transform.resize(value=(1000, 1000, 1000))
            print("  - 骨架缩放完成。")

            # --- 3. 应用姿态为静止姿态 (姿态模式) ---
            print("步骤 3: 应用当前姿态为静止姿态...")
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.select_all(action='SELECT')
            bpy.ops.pose.armature_apply(selected=False)
            bpy.ops.pose.select_all(action='DESELECT')
            print("  - 应用姿态完成。")

            # --- 4. 处理特定骨骼 & Root 合并 (姿态模式) ---
            print("步骤 4: 处理特定骨骼和 Root 合并...")
            if context.mode != 'POSE':
                 bpy.ops.object.mode_set(mode='POSE')
            # ... (骨骼合并逻辑保持不变) ...
            # 合并 "part" 或 "finger4"
            print("  - 检查 'part'/'finger4' 骨骼...")
            bpy.ops.pose.select_all(action='DESELECT')
            found_bones_part1 = False
            bones_to_select_p1 = []
            for pose_bone in obj.pose.bones:
                bone_name_lower = pose_bone.name.lower()
                if ("part" in bone_name_lower or "finger4" in bone_name_lower) and pose_bone.parent:
                    bones_to_select_p1.append(pose_bone.name)
                    found_bones_part1 = True
            if found_bones_part1:
                print(f"    - 找到 {len(bones_to_select_p1)} 个，准备合并到父级...")
                for bone_name in bones_to_select_p1:
                    if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                if context.selected_pose_bones:
                    bpy.ops.bone.merge_to_parent()
                    print("    - 'part'/'finger4' 骨骼合并完成。")
                else:
                    print("    - 警告：选择 'part'/'finger4' 骨骼失败或没有选中项，跳过合并。")
            else:
                print("  - 未找到 'part'/'finger4' 骨骼。")
            # 合并 "skin" (排除特定前缀)
            print("  - 检查 'skin' 骨骼 (排除 'lf', 'rf', 'rt_', 'lt_')...")
            bpy.ops.pose.select_all(action='DESELECT')
            found_bones_part2 = False
            bones_to_select_p2 = []
            exclude_prefixes = ("lf", "rf", "rt_", "lt_")
            for pose_bone in obj.pose.bones:
                bone_name = pose_bone.name.lower()
                if ("skin" in bone_name and
                    not any(bone_name.startswith(prefix) for prefix in exclude_prefixes) and
                    not any(f"_{prefix}" in bone_name for prefix in exclude_prefixes) and
                    pose_bone.parent):
                    bones_to_select_p2.append(pose_bone.name)
                    found_bones_part2 = True
            if found_bones_part2:
                print(f"    - 找到 {len(bones_to_select_p2)} 个，准备合并到父级...")
                for bone_name in bones_to_select_p2:
                    if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                if context.selected_pose_bones:
                    bpy.ops.bone.merge_to_parent()
                    print("    - 'skin' 骨骼合并完成。")
                else:
                    print("    - 警告：选择 'skin' 骨骼失败或没有选中项，跳过合并。")
            else:
                print("  - 未找到符合条件的 'skin' 骨骼。")
            # 合并 "cup"
            print("  - 检查 'cup' 骨骼...")
            bpy.ops.pose.select_all(action='DESELECT')
            found_bones_cup = False
            bones_to_select_cup = []
            for pose_bone in obj.pose.bones:
                bone_name_lower = pose_bone.name.lower()
                if "cup" in bone_name_lower and pose_bone.parent:
                    bones_to_select_cup.append(pose_bone.name)
                    found_bones_cup = True
            if found_bones_cup:
                print(f"    - 找到 {len(bones_to_select_cup)} 个，准备合并到父级...")
                for bone_name in bones_to_select_cup:
                    if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                if context.selected_pose_bones:
                    bpy.ops.bone.merge_to_parent()
                    print("    - 'cup' 骨骼合并完成。")
                else:
                    print("    - 警告：选择 'cup' 骨骼失败或没有选中项，跳过合并。")
            else:
                print("  - 未找到 'cup' 骨骼。")
            # 处理 root 骨骼
            print("  - 处理 Root 骨骼合并...")
            bpy.ops.pose.select_all(action='DESELECT')
            root_bone = None
            for pose_bone in obj.pose.bones:
                if pose_bone.name.lower() == "root":
                    root_bone = pose_bone
                    break
            if root_bone:
                print(f"    - 找到 Root 骨骼: {root_bone.name}")
                try:
                    bpy.ops.pose.select_all(action='DESELECT')
                    obj.data.bones.active = root_bone.bone
                    root_bone.bone.select = True
                except Exception as e_select_root:
                    print(f"    - 警告：选择或设置Root为活动骨骼时出错: {e_select_root}")
                    root_bone = None
                if root_bone:
                    root_parent = root_bone.parent
                    siblings_selected = False
                    bones_to_select_siblings = []
                    if root_parent:
                        print(f"    - 查找 Root 的同层级骨骼 (父级: {root_parent.name})...")
                        for pose_bone in obj.pose.bones:
                            if pose_bone != root_bone and pose_bone.parent == root_parent:
                                bones_to_select_siblings.append(pose_bone.name)
                                siblings_selected = True
                                print(f"      - 待选同层级: {pose_bone.name}")
                    if siblings_selected:
                        print("    - 合并同层级骨骼到 Root...")
                        for bone_name in bones_to_select_siblings:
                            if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                        obj.data.bones.active = root_bone.bone
                        root_bone.bone.select = True 
                        if len(context.selected_pose_bones) > 1:
                            bpy.ops.bone.merge_to_active()
                        else:
                             print("    - 警告：选择同层级骨骼后，选中数量不足以合并。")
                        bpy.ops.pose.select_all(action='DESELECT')
                    if root_parent:
                        print(f"    - 选择 Root 的父级 {root_parent.name} 并合并到 Root...")
                        bpy.ops.pose.select_all(action='DESELECT')
                        root_bone.bone.select = True
                        obj.data.bones.active = root_bone.bone
                        if root_parent.name in obj.pose.bones:
                            obj.pose.bones[root_parent.name].bone.select = True
                            if len(context.selected_pose_bones) == 2:
                                bpy.ops.bone.merge_to_active()
                                print("    - Root 父级合并完成。")
                            else:
                                print("    - 警告：选择父级骨骼后，选中数量不为2，无法合并。")
                        else:
                            print(f"    - 警告: 无法在 Pose 模式下找到父级骨骼 {root_parent.name}。")
                        bpy.ops.pose.select_all(action='DESELECT')
            else:
                print("  - 未找到名为 'root' 的骨骼。")

            # --- 5. 清理零权重骨骼 (物体/编辑模式) ---
            print("步骤 5: 清理零权重骨骼...")
            # ... (清理逻辑保持不变，确保先切到 OBJECT 模式检查权重) ...
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == obj]
            print(f"  - 检查 {len(mesh_objects)} 个当前关联模型的权重...")
            bones_with_weights = set()
            for mesh_obj in mesh_objects:
                 if not mesh_obj.vertex_groups: continue
                 for vgroup in mesh_obj.vertex_groups:
                      if vgroup.name not in armature.bones: continue
                      has_weight = False
                      if vgroup.index in [g.group for v in mesh_obj.data.vertices for g in v.groups]:
                           for vert in mesh_obj.data.vertices:
                                try:
                                     weight = vgroup.weight(vert.index)
                                     if weight > 1e-6:
                                          has_weight = True
                                          break
                                except RuntimeError:
                                     continue
                      if has_weight:
                           bones_with_weights.add(vgroup.name)
            print(f"  - {len(bones_with_weights)} 个骨骼具有有效权重。")
            excluded_bone_names = {"face_eye_l", "face_eye_r", "face_base_eye_l", "face_base_eye_r"}
            bones_to_remove = []
            for bone in armature.bones:
                if (bone.name not in bones_with_weights and
                    bone.name.lower() not in excluded_bone_names):
                    bones_to_remove.append(bone.name)
            print(f"  - 找到 {len(bones_to_remove)} 个零权重骨骼准备删除 (已排除眼睛骨骼)。")
            if bones_to_remove:
                print("  - 切换到编辑模式删除骨骼...")
                bpy.ops.object.mode_set(mode='EDIT')
                removed_count = 0
                for bone_name in bones_to_remove:
                    if bone_name in armature.edit_bones:
                        edit_bone = armature.edit_bones[bone_name]
                        parent = edit_bone.parent
                        children_to_reparent = list(edit_bone.children)
                        if children_to_reparent and parent and parent.name in armature.edit_bones:
                             valid_parent_edit_bone = armature.edit_bones[parent.name]
                             for child in children_to_reparent:
                                  if child.name in armature.edit_bones:
                                       armature.edit_bones[child.name].parent = valid_parent_edit_bone
                        try:
                            armature.edit_bones.remove(edit_bone)
                            removed_count += 1
                        except Exception as e_bone_remove:
                             print(f"      - 删除骨骼 {bone_name} 时出错: {e_bone_remove}")
                print(f"  - 实际删除了 {removed_count} 个零权重骨骼。")
            else:
                print("  - 没有需要删除的零权重骨骼。")

            # --- 6. 应用变换 (物体模式) ---
            print("步骤 6: 应用骨架和剩余子模型变换...")
            # ... (应用变换逻辑保持不变) ...
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            mesh_children_final = []
            for child in obj.children:
                if child.type == 'MESH':
                    child.select_set(True)
                    mesh_children_final.append(child)
            if context.selected_objects:
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                print(f"  - 已对骨架和 {len(mesh_children_final)} 个剩余子模型应用变换。")
            else:
                print("  - 没有选中对象可以应用变换。")
            bpy.ops.object.select_all(action='DESELECT')

            # --- 7. 处理面部模型顶点组 (物体模式) ---
            print("步骤 7: 处理剩余面部模型顶点组...")
            # ... (面部顶点组处理逻辑保持不变) ...
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            face_models_final = [o for o in bpy.data.objects if o.type == 'MESH' and 'face' in o.name.lower()]
            print(f"  - 找到 {len(face_models_final)} 个剩余的面部模型进行顶点组处理...")
            face_models_processed = 0
            for face_model in face_models_final:
                print(f"    - 处理模型: {face_model.name}")
                bpy.ops.object.select_all(action='DESELECT')
                context.view_layer.objects.active = face_model
                face_model.select_set(True)
                print("      - 清除现有顶点组...")
                while face_model.vertex_groups:
                    try:
                         face_model.vertex_groups.remove(face_model.vertex_groups[0])
                    except Exception as e_vg_remove:
                         print(f"        - 删除顶点组时出错 (可能已删除): {e_vg_remove}")
                         break
                print("      - 创建 Head_M, Face_Eye_L, Face_Eye_R 顶点组...")
                head_group = face_model.vertex_groups.new(name="Head_M")
                eye_l_group = face_model.vertex_groups.new(name="Face_Eye_L")
                eye_r_group = face_model.vertex_groups.new(name="Face_Eye_R")
                eye_material_indices = []
                if face_model.data.materials:
                    for i, mat in enumerate(face_model.data.materials):
                        if mat:
                            mat_name_lower = mat.name.lower()
                            if ((("eyenew" in mat_name_lower and "eyenewmu" not in mat_name_lower) or
                                 "eyenewadd" in mat_name_lower) and
                                not any(exclude in mat_name_lower for exclude in ["eyenewmul", "eyenewmult"])):
                                eye_material_indices.append(i)
                print("      - 分配顶点到组...")
                verts_head = []
                verts_eye_l = []
                verts_eye_r = []
                processed_verts = set()
                if not face_model.data.polygons:
                     print("      - 警告: 模型没有面，无法分配顶点组。")
                     continue
                for poly in face_model.data.polygons:
                    is_eye_material = poly.material_index in eye_material_indices
                    for vert_idx in poly.vertices:
                        if vert_idx in processed_verts: continue
                        vert = face_model.data.vertices[vert_idx]
                        processed_verts.add(vert_idx)
                        if is_eye_material:
                            if vert.co.x > 0: verts_eye_l.append(vert_idx)
                            else: verts_eye_r.append(vert_idx)
                        else: verts_head.append(vert_idx)
                if verts_head: head_group.add(verts_head, 1.0, 'REPLACE');
                if verts_eye_l: eye_l_group.add(verts_eye_l, 1.0, 'REPLACE');
                if verts_eye_r: eye_r_group.add(verts_eye_r, 1.0, 'REPLACE');
                face_models_processed += 1
                bpy.ops.object.select_all(action='DESELECT')
            if face_models_processed == 0 and len(face_models_final) > 0:
                print("  - 未成功处理任何面部模型顶点组。")
            elif face_models_processed > 0:
                print(f"  - 已处理 {face_models_processed} 个面部模型顶点组。")

            # --- 8. 完成与报告 --- (旧的步骤7)
            # 切换回原始模式
            bpy.ops.object.mode_set(mode=original_mode if original_mode in {'OBJECT', 'POSE', 'EDIT'} else 'OBJECT') # 确保是有效模式

            # 最终报告
            final_message = "少前2模型预处理完成。"
            self.report({'INFO'}, final_message)
            print(f"\n{final_message}")

        except Exception as e:
            # 发生错误时，尝试恢复原始模式
            try:
                if bpy.context.mode != original_mode:
                   bpy.ops.object.mode_set(mode=original_mode if original_mode in {'OBJECT', 'POSE', 'EDIT'} else 'OBJECT')
            except Exception as mode_restore_error:
                 print(f"尝试恢复原始模式时也发生错误: {mode_restore_error}")
            # 报告错误
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"处理过程中发生错误: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

class BONE_OT_merge_siblings_half(Operator):
    bl_idname = "bone.merge_siblings_half"
    bl_label = "左右对称合并"
    bl_description = "将同层级的骨骼按左右各合并一半（保持圆周分布）"
    bl_options = {'REGISTER', 'UNDO'}
    
    use_global_center: bpy.props.BoolProperty(
        name="使用全局中心",
        description="使用所有选定骨骼的中心作为参考点，保持垂直对齐",
        default=True
    )
    
    include_root_bones: bpy.props.BoolProperty(
        name="包含根骨骼",
        description="同时处理没有父级的根骨骼",
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE' and
                context.selected_pose_bones)
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        
        # 计算全局中心
        global_center = None
        if self.use_global_center:
            all_selected_bones = context.selected_pose_bones
            global_center = sum((b.head for b in all_selected_bones), Vector()) / len(all_selected_bones)
        
        # 收集选中骨骼的层级
        parent_level = {}
        for bone in context.selected_pose_bones:
            # 判断是否处理根骨骼
            if bone.parent or self.include_root_bones:
                # 计算骨骼所在层级深度
                depth = 0
                parent = bone.parent
                while parent:
                    depth += 1
                    parent = parent.parent
                parent_level[depth] = parent_level.get(depth, set())
                parent_level[depth].add(bone)
        
        # 按层级处理骨骼
        for depth, bones in parent_level.items():
            if len(bones) < 2:
                continue
            
            # 将骨骼按圆周顺序排序
            bones_list = list(bones)
            
            # 决定使用哪个中心点
            if self.use_global_center and global_center:
                center = global_center
            else:
                center = sum((b.head for b in bones_list), Vector()) / len(bones_list)
            
            # 计算每个骨骼相对于中心的角度
            def get_angle(bone):
                vec = bone.head - center
                return math.atan2(vec.y, vec.x)
            
            bones_list.sort(key=get_angle)
            
            # 计算需要保留的骨骼数量（总数的一半，向上取整）
            target_count = (len(bones_list) + 1) // 2
            
            # 按圆周均匀选择要保留的骨骼
            bones_to_keep = []
            step = len(bones_list) / target_count
            for i in range(target_count):
                index = int(i * step)
                bones_to_keep.append(bones_list[index])
            
            # 将其他骨骼的权重转移到最近的保留骨骼
            bones_to_remove = [b for b in bones_list if b not in bones_to_keep]
            
            # 切换到对象模式进行权重转移
            bpy.ops.object.mode_set(mode='OBJECT')
            
            for bone in bones_to_remove:
                # 找到最近的保留骨骼
                closest_bone = min(bones_to_keep, 
                                 key=lambda b: (bone.head - b.head).length)
                
                # 转移权重
                for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
                    self.transfer_weights(bone.name, closest_bone.name, mesh)
            
            # 切换到编辑模式删除骨骼
            bpy.ops.object.mode_set(mode='EDIT')
            
            # 删除已合并的骨骼
            for bone in bones_to_remove:
                if bone.name in armature.edit_bones:
                    edit_bone = armature.edit_bones[bone.name]
                    # 如果骨骼有子级，先将子级的父级设置为当前骨骼的父级
                    if edit_bone.children:
                        parent = edit_bone.parent
                        for child in edit_bone.children:
                            child.parent = parent
                    armature.edit_bones.remove(edit_bone)
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_global_center")
        layout.prop(self, "include_root_bones")
        
    @staticmethod
    def transfer_weights(from_bone_name, to_bone_name, mesh):
        """
        改进的权重转移函数
        """
        # 确保目标权重组存在
        if to_bone_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=to_bone_name)
        
        # 获取源和目标权重组
        from_group = mesh.vertex_groups.get(from_bone_name)
        to_group = mesh.vertex_groups.get(to_bone_name)
        
        if not from_group:
            return
        
        # 存储每个顶点的权重
        weights = {}
        for vertex in mesh.data.vertices:
            try:
                weight = from_group.weight(vertex.index)
                if weight > 0:
                    weights[vertex.index] = weight
            except RuntimeError:
                continue
        
        # 转移权重
        if weights:
            # 添加新权重
            for vertex_index, weight in weights.items():
                try:
                    current_weight = 0
                    try:
                        current_weight = to_group.weight(vertex_index)
                    except RuntimeError:
                        pass
                    # 使用 'REPLACE' 模式确保权重正确设置
                    to_group.add([vertex_index], current_weight + weight, 'REPLACE')
                except RuntimeError:
                    continue
        
        # 删除原始权重组
        mesh.vertex_groups.remove(from_group)

class MQT_PT_BoneToolsPanel(Panel):
    bl_label = "骨骼工具"
    bl_idname = "MQT_PT_BoneToolsPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 基本合并功能
        box = layout.box()
        box.label(text="基本合并")
        
        row = box.row()
        row.operator("bone.merge_to_parent", text="合并到父级")
        
        row = box.row()
        row.operator("bone.merge_to_active", text="合并到活动骨骼")
        
        # 高级合并功能
        box = layout.box()
        box.label(text="高级合并")
        
        row = box.row()
        row.operator("bone.merge_siblings_half", text="左右对称合并")
        
        # 预处理工具
        box = layout.box()
        box.label(text="预处理工具")
        
        row = box.row()
        # 使用修改后的 bl_idname
        row.operator("object.gfl2_preprocess", text="少前2模型一键预处理") # 按钮文本可以保持不变或同步修改
        
        # 清理工具
        box = layout.box()
        box.label(text="清理工具")
        
        row = box.row()
        row.operator("bone.remove_zero_weight", text="清除零权重骨骼")
        
        # 变换工具
        box = layout.box()
        box.label(text="变换工具")
        
        row = box.row()
        row.operator("bone.apply_pose_transform", text="应用姿态变换")
        
        # 检查是否选择了骨架来启用按钮（而不是检查模式）
        armature_selected = bool(context.active_object and context.active_object.type == 'ARMATURE')
        layout.enabled = armature_selected

# --------------------------------------------------------------------------
# 工具 6: 一键PBR材质着色工具
# --------------------------------------------------------------------------

# --- Helper Functions for PBR Tool ---

def _find_texture_path(base_dir, output_dir, texture_filename):
    """查找纹理文件的绝对路径"""
    potential_paths = []
    # 优先在输出目录查找（如果指定）
    if output_dir:
        potential_paths.append(os.path.join(output_dir, os.path.basename(texture_filename)))
        potential_paths.append(os.path.join(output_dir, texture_filename)) # In case filename includes relative path parts
    # 在源目录查找
    potential_paths.append(os.path.join(base_dir, os.path.basename(texture_filename)))
    potential_paths.append(os.path.join(base_dir, texture_filename))
    # 直接使用文件名（可能是绝对路径）
    potential_paths.append(texture_filename)

    for p in potential_paths:
        if p and os.path.isfile(p):
            return os.path.normpath(p)
    print(f"警告: 无法找到贴图文件 '{texture_filename}' 在 {base_dir} 或 {output_dir}")
    return None # Corrected indentation

def _cleanup_material_nodes(nodes, links):
    """清理材质节点树，保留Output节点和现有的Normal Map设置"""
    print(f"  - 开始清理节点 (当前 {len(nodes)} 个)...")
    output_node = None
    principled_bsdf_node = None # Find the BSDF connected to output
    normal_map_node = None
    normal_texture_node = None
    nodes_to_remove = []

    # Find the Material Output node first
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
            break # Assume only one output node

    # Find the BSDF connected to the output and check its Normal input
    if output_node and output_node.inputs["Surface"].links:
        link = output_node.inputs["Surface"].links[0]
        if link.from_node.type == 'BSDF_PRINCIPLED':
            principled_bsdf_node = link.from_node
            print(f"    - 找到连接到输出的 Principled BSDF: {principled_bsdf_node.name}")
            # Check Normal input of this existing BSDF
            normal_input = principled_bsdf_node.inputs.get("Normal")
            if normal_input and normal_input.links:
                normal_link = normal_input.links[0]
                if normal_link.from_node.type == 'NORMAL_MAP':
                    normal_map_node = normal_link.from_node
                    print(f"    - 找到连接到法线的 Normal Map 节点: {normal_map_node.name}")
                    # Check the Color input of the Normal Map node
                    color_input = normal_map_node.inputs.get("Color")
                    if color_input and color_input.links:
                        texture_link = color_input.links[0]
                        if texture_link.from_node.type == 'TEX_IMAGE':
                            normal_texture_node = texture_link.from_node
                            print(f"    - 找到连接到 Normal Map 的 Image Texture: {normal_texture_node.name}")

    # Identify nodes to remove
    preserved_nodes = {output_node, principled_bsdf_node, normal_map_node, normal_texture_node}
    for node in nodes:
        if node not in preserved_nodes and node is not None: # Check for None just in case
            nodes_to_remove.append(node)
        elif node == output_node and output_node:
             # Clean input links of the output node EXCEPT the BSDF link if preserved
            for input_socket in node.inputs:
                 if input_socket.name == "Surface" and principled_bsdf_node: continue # Keep BSDF link
                 if input_socket.links:
                     for link in list(input_socket.links):
                         print(f"    - 清理输出连接: {link.from_node.name}.{link.from_socket.name} -> {node.name}.{input_socket.name}")
                         links.remove(link)
        elif node == principled_bsdf_node and principled_bsdf_node:
            # Clean inputs of preserved BSDF EXCEPT the normal link if preserved
            for input_socket in node.inputs:
                 if input_socket.name == "Normal" and normal_map_node: continue # Keep normal link
                 if input_socket.links:
                     for link in list(input_socket.links):
                          print(f"    - 清理保留的BSDF输入连接: {link.from_node.name}.{link.from_socket.name} -> {node.name}.{input_socket.name}")
                          links.remove(link)
        elif node == normal_map_node and normal_map_node:
             # Clean inputs of preserved Normal Map EXCEPT the texture link if preserved
             for input_socket in node.inputs:
                  if input_socket.name == "Color" and normal_texture_node: continue # Keep texture link
                  if input_socket.links:
                      for link in list(input_socket.links):
                           print(f"    - 清理保留的NormalMap输入连接: {link.from_node.name}.{link.from_socket.name} -> {node.name}.{input_socket.name}")
                           links.remove(link)


    removed_count = 0
    if nodes_to_remove:
        print(f"    - 准备删除 {len(nodes_to_remove)} 个旧节点...")
        for node in nodes_to_remove:
            # Ensure node still exists before removing (might have been removed as part of another node's tree)
            if node.name in nodes:
                print(f"      - 删除: {node.name} ({node.type})")
                try:
                    nodes.remove(node)
                    removed_count += 1
                except Exception as remove_err:
                    print(f"      - 删除节点 {node.name} 时出错: {remove_err}")
            else:
                print(f"      - 跳过删除: {node.name} (已不存在)")

    print(f"  - 节点清理完成，删除了 {removed_count} 个。")
    # Return the nodes that were preserved (or None if not found)
    return output_node, principled_bsdf_node, normal_map_node, normal_texture_node

def _create_base_nodes(nodes, links, existing_output, existing_bsdf, existing_normal_map, existing_normal_texture):
    """创建或复用Principled BSDF和Output，并重新连接法线贴图（如果存在）"""
    output_node = existing_output
    if not output_node:
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        # Adjusted location
        output_node.location = (500, 300)
        print(f"  - 创建了新输出节点: {output_node.name}")

    principled_node = existing_bsdf
    if not principled_node:
        principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        # Adjusted location
        principled_node.location = (100, 300)
        print(f"  - 创建了新 Principled BSDF: {principled_node.name}")
        # Connect new BSDF to output if BSDF was newly created
        if output_node.inputs["Surface"].links:
             for link in list(output_node.inputs["Surface"].links): links.remove(link) # Clean first
        links.new(principled_node.outputs["BSDF"], output_node.inputs["Surface"])
        print(f"  - 连接了新 {principled_node.name}.BSDF -> {output_node.name}.Surface")
    else:
         # Ensure the preserved BSDF is still connected to output
         is_connected = False
         if output_node.inputs["Surface"].links:
              if output_node.inputs["Surface"].links[0].from_node == principled_node:
                   is_connected = True
         if not is_connected:
              print(f"  - 重新连接保留的BSDF {principled_node.name} 到输出 {output_node.name}")
              if output_node.inputs["Surface"].links: # Clean if wrongly connected
                  for link in list(output_node.inputs["Surface"].links): links.remove(link)
              links.new(principled_node.outputs["BSDF"], output_node.inputs["Surface"])

    # Reconnect preserved normal map setup if it exists
    if principled_node and existing_normal_map and existing_normal_texture:
        normal_input = principled_node.inputs.get("Normal")
        if normal_input:
            is_normal_connected = False
            if normal_input.links:
                if normal_input.links[0].from_node == existing_normal_map:
                    is_normal_connected = True

            if not is_normal_connected:
                print(f"  - 重新连接保留的法线贴图设置: {existing_normal_texture.name} -> {existing_normal_map.name} -> {principled_node.name}.Normal")
                # Ensure Normal Map color input is linked correctly
                color_input = existing_normal_map.inputs.get("Color")
                if color_input:
                    is_tex_connected = False
                    if color_input.links:
                        if color_input.links[0].from_node == existing_normal_texture:
                             is_tex_connected = True
                    if not is_tex_connected:
                        if color_input.links: # Clean wrong links
                             for link in list(color_input.links): links.remove(link)
                        links.new(existing_normal_texture.outputs["Color"], color_input)
                else: print(f"    - 警告: 保留的 Normal Map 节点 {existing_normal_map.name} 没有 Color 输入?")

                # Link Normal Map output to BSDF Normal input
                if normal_input.links: # Clean wrong links
                    for link in list(normal_input.links): links.remove(link)
                links.new(existing_normal_map.outputs["Normal"], normal_input)
            else:
                 print(f"  - 保留的法线贴图设置已连接。")
        else:
            print(f"  - 警告: 保留的 Principled BSDF {principled_node.name} 没有 Normal 输入?")
    elif existing_normal_map or existing_normal_texture:
         print(f"  - 警告: 法线贴图设置不完整，无法重新连接 (NormalMap: {existing_normal_map}, Texture: {existing_normal_texture})")


    return principled_node, output_node


def _load_texture_node(nodes, texture_path, node_name_prefix, material_name, is_rmo=False):
    """加载纹理到图像节点，使用材质名称重命名数据块，返回图像节点。"""
    # REMOVED: force_unique_datablock parameter and its logic
    logger = logging.getLogger('pbr_materials')

    if not texture_path or not os.path.exists(texture_path):
        # Now log error instead of print
        logger.error(f"错误: 贴图路径无效或文件不存在: {texture_path}")
        return None

    tex_node = nodes.new(type='ShaderNodeTexImage')
    # Use a more robust unique name for the node itself
    unique_node_suffix = str(uuid.uuid4())[:8]
    node_name = f"{node_name_prefix}_{('RMO' if is_rmo else 'Diffuse')}_{unique_node_suffix}"
    tex_node.name = node_name
    tex_node.label = os.path.basename(texture_path) # Set label for readability
    # Adjusted locations for more spacing
    tex_node.location = (-800, 100) if is_rmo else (-800, 500)
    logger.info(f"  - 创建图像节点: {node_name}")

    loaded_image = None
    try:
        # Always use check_existing=True now, let Blender handle sharing based on filepath
        logger.info(f"  - 尝试加载/复用图像: '{os.path.basename(texture_path)}' (check_existing=True)")
        loaded_image = bpy.data.images.load(texture_path, check_existing=True)
        if loaded_image:
            logger.info(f"    - 加载/复用图像成功: Name='{loaded_image.name}', ID={id(loaded_image)}, Path='{loaded_image.filepath}'")
            # --- Rename Data Block Here --- 
            # Check if the loaded image name is already the desired material name
            if loaded_image.name != material_name:
                # Check if the target name already exists
                if material_name in bpy.data.images:
                    logger.warning(f"    - 目标图像数据块名称 '{material_name}' 已存在。将尝试复用现有块。")
                    # If the existing block with the target name points to the SAME file, reuse it
                    existing_image = bpy.data.images[material_name]
                    if existing_image.filepath == loaded_image.filepath:
                        logger.info(f"      - 复用名称为 '{material_name}' 且路径相同的现有数据块。")
                        # If the initially loaded image has no other users, remove it
                        if loaded_image.users <= 1 and loaded_image.name != material_name: # Check users of initially loaded block
                           try:
                                bpy.data.images.remove(loaded_image)
                                logger.info(f"        - 移除了初始加载的、未使用的块 '{loaded_image.name}'")
                           except Exception as remove_err:
                                logger.warning(f"        - 移除初始加载块 '{loaded_image.name}' 时出错: {remove_err}")
                        loaded_image = existing_image # Point to the correctly named existing block
                    else:
                        # Name collision with different file path - append UUID to avoid issues
                        logger.warning(f"      - 名称 '{material_name}' 已被用于不同文件 ('{existing_image.filepath}')。将添加UUID后缀。")
                        unique_mat_name = f"{material_name}_{str(uuid.uuid4())[:4]}"
                        loaded_image.name = unique_mat_name
                        logger.info(f"    - 重命名图像数据块为: '{unique_mat_name}'")
                else:
                    # Target name doesn't exist, safe to rename
                    loaded_image.name = material_name
                    logger.info(f"    - 重命名图像数据块为: '{material_name}'")
            else:
                 logger.info(f"    - 图像数据块名称 '{loaded_image.name}' 已是目标名称 '{material_name}'")

            # Ensure filepath is correct (important if reusing existing block)
            if loaded_image.filepath != texture_path:
                logger.warning(f"    - 修正图像数据块 '{loaded_image.name}' 的文件路径: '{loaded_image.filepath}' -> '{texture_path}'")
                loaded_image.filepath = texture_path
                loaded_image.reload() # Reload to ensure consistency
        else:
            logger.error(f"    - 错误: 加载图像 '{os.path.basename(texture_path)}' 失败")

    except Exception as load_err:
        logger.error(f"错误: 加载或处理图像 '{os.path.basename(texture_path)}' 失败: {load_err}", exc_info=True)
        if tex_node in nodes: nodes.remove(tex_node) # Clean up failed node
        return None

    if loaded_image:
        tex_node.image = loaded_image
        # Set color space AFTER assigning image
        tex_node.image.colorspace_settings.name = 'Non-Color' if is_rmo else 'sRGB'
        logger.info(f"    - 设置色彩空间 for '{loaded_image.name}': {'Non-Color' if is_rmo else 'sRGB'}")
        return tex_node
    else:
        logger.error(f"错误: 最终图像对象为空: {texture_path}")
        if tex_node in nodes: nodes.remove(tex_node)
        return None


def _link_textures_to_principled(nodes, links, principled_node, diffuse_tex, rmo_tex):
    """将纹理节点连接到Principled BSDF"""
    # Check if principled_node is valid
    if not principled_node:
        logger = logging.getLogger('pbr_materials')
        logger.error("_link_textures_to_principled: 无效的 Principled BSDF 节点提供")
        return

    logger = logging.getLogger('pbr_materials') # Get logger instance

    if diffuse_tex and rmo_tex:
        logger.info(f"  - 连接 Diffuse ({diffuse_tex.name}) 和 RMO ({rmo_tex.name})")
        # --- RMO Path ---
        print(f"    - RMO 节点: {rmo_tex.name}, 图像: {rmo_tex.image.name if rmo_tex.image else '无'}, 颜色空间: {rmo_tex.image.colorspace_settings.name if rmo_tex.image else 'N/A'}")
        if rmo_tex.image and rmo_tex.image.colorspace_settings.name != 'Non-Color':
            print(f"    - 警告: RMO 贴图 '{rmo_tex.image.name}' 的颜色空间不是 Non-Color, 应修正。")
        
        separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
        # Adjusted location for more spacing
        separate_rgb.location = (-300, 100)
        print(f"    - 创建 Separate RGB 节点: {separate_rgb.name}")
        
        # Ensure RMO output is connected to Separate RGB input
        if separate_rgb.inputs["Image"].links: # Clean first
             for link in list(separate_rgb.inputs["Image"].links): links.remove(link)
        links.new(rmo_tex.outputs["Color"], separate_rgb.inputs["Image"])
        print(f"    - 连接: {rmo_tex.name}.Color -> {separate_rgb.name}.Image")

        # Connect R, G to Roughness, Metallic
        if principled_node.inputs["Roughness"].links:
             for link in list(principled_node.inputs["Roughness"].links): links.remove(link)
        links.new(separate_rgb.outputs["R"], principled_node.inputs["Roughness"])
        print(f"    - 连接: {separate_rgb.name}.R -> {principled_node.name}.Roughness")
        
        if principled_node.inputs["Metallic"].links:
             for link in list(principled_node.inputs["Metallic"].links): links.remove(link)
        links.new(separate_rgb.outputs["G"], principled_node.inputs["Metallic"])
        print(f"    - 连接: {separate_rgb.name}.G -> {principled_node.name}.Metallic")

        # --- Diffuse + AO Path ---
        print(f"    - Diffuse 节点: {diffuse_tex.name}, 图像: {diffuse_tex.image.name if diffuse_tex.image else '无'}, 颜色空间: {diffuse_tex.image.colorspace_settings.name if diffuse_tex.image else 'N/A'}")

        multiply_node = nodes.new(type='ShaderNodeMixRGB') # Changed to MixRGB for clarity in UI, still use Multiply
        multiply_node.label = "AO Multiply"
        # Adjusted location for more spacing
        multiply_node.location = (-300, 500)
        multiply_node.blend_type = 'MULTIPLY'
        # Set AO Mix Factor to 0.5
        multiply_node.inputs["Fac"].default_value = 0.5
        print(f"    - 创建 MixRGB (Multiply) 节点: {multiply_node.name}")

        # Connect Diffuse to Color1
        if multiply_node.inputs["Color1"].links:
             for link in list(multiply_node.inputs["Color1"].links): links.remove(link)
        links.new(diffuse_tex.outputs["Color"], multiply_node.inputs["Color1"])
        print(f"    - 连接: {diffuse_tex.name}.Color -> {multiply_node.name}.Color1")

        # Connect AO (Blue channel) to Color2
        if multiply_node.inputs["Color2"].links:
             for link in list(multiply_node.inputs["Color2"].links): links.remove(link)
        links.new(separate_rgb.outputs["B"], multiply_node.inputs["Color2"]) # Assuming B channel is AO
        print(f"    - 连接: {separate_rgb.name}.B (AO) -> {multiply_node.name}.Color2")

        # Connect Mix result to Base Color
        if principled_node.inputs["Base Color"].links:
             for link in list(principled_node.inputs["Base Color"].links): links.remove(link)
        links.new(multiply_node.outputs["Color"], principled_node.inputs["Base Color"])
        print(f"    - 连接: {multiply_node.name}.Color -> {principled_node.name}.Base Color")

    elif diffuse_tex:
        # --- Only Diffuse Path ---
        print(f"  - 仅连接 Diffuse ({diffuse_tex.name})")
        print(f"    - Diffuse 节点: {diffuse_tex.name}, 图像: {diffuse_tex.image.name if diffuse_tex.image else '无'}, 颜色空间: {diffuse_tex.image.colorspace_settings.name if diffuse_tex.image else 'N/A'}")
        if principled_node.inputs["Base Color"].links:
             for link in list(principled_node.inputs["Base Color"].links): links.remove(link)
        links.new(diffuse_tex.outputs["Color"], principled_node.inputs["Base Color"])
        print(f"    - 连接: {diffuse_tex.name}.Color -> {principled_node.name}.Base Color")
        # Ensure Roughness/Metallic are default if no RMO
        principled_node.inputs["Roughness"].default_value = 0.5 # Default roughness
        principled_node.inputs["Metallic"].default_value = 0.0 # Default non-metallic

    elif rmo_tex: # If only RMO, connect Roughness/Metallic but leave Base Color default
         # --- Only RMO Path ---
         print(f"  - 仅连接 RMO ({rmo_tex.name})")
         print(f"    - RMO 节点: {rmo_tex.name}, 图像: {rmo_tex.image.name if rmo_tex.image else '无'}, 颜色空间: {rmo_tex.image.colorspace_settings.name if rmo_tex.image else 'N/A'}")
         if rmo_tex.image and rmo_tex.image.colorspace_settings.name != 'Non-Color':
             print(f"    - 警告: RMO 贴图 '{rmo_tex.image.name}' 的颜色空间不是 Non-Color, 应修正。")
         
         separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
         separate_rgb.location = (0, 0)
         print(f"    - 创建 Separate RGB 节点: {separate_rgb.name}")

         if separate_rgb.inputs["Image"].links:
              for link in list(separate_rgb.inputs["Image"].links): links.remove(link)
         links.new(rmo_tex.outputs["Color"], separate_rgb.inputs["Image"])
         print(f"    - 连接: {rmo_tex.name}.Color -> {separate_rgb.name}.Image")

         if principled_node.inputs["Roughness"].links:
              for link in list(principled_node.inputs["Roughness"].links): links.remove(link)
         links.new(separate_rgb.outputs["R"], principled_node.inputs["Roughness"])
         print(f"    - 连接: {separate_rgb.name}.R -> {principled_node.name}.Roughness")

         if principled_node.inputs["Metallic"].links:
              for link in list(principled_node.inputs["Metallic"].links): links.remove(link)
         links.new(separate_rgb.outputs["G"], principled_node.inputs["Metallic"])
         print(f"    - 连接: {separate_rgb.name}.G -> {principled_node.name}.Metallic")
         
         # Leave Base Color at default
         # principled_node.inputs["Base Color"].default_value = default color

    else:
        # No textures connected, set defaults
        print("  - 没有纹理节点连接，设置 BSDF 默认值。")
        principled_node.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0) # Default grey
        principled_node.inputs["Roughness"].default_value = 0.5
        principled_node.inputs["Metallic"].default_value = 0.0


def _handle_alpha_channel(mat, links, principled_node, diffuse_tex):
    """处理Alpha通道连接和材质设置 (使用像素检查)"""
    logger = logging.getLogger('pbr_materials') # Get logger instance
    if not principled_node:
        logger.error("_handle_alpha_channel: 无效的 Principled BSDF 节点提供")
        return
    if not mat:
        logger.error("_handle_alpha_channel: 无效的材质提供")
        return

    if not diffuse_tex or not diffuse_tex.image:
        logger.info("  - 无漫反射贴图，跳过Alpha处理")
        # Ensure OPAQUE if no texture
        mat.blend_method = 'OPAQUE'
        mat.shadow_method = 'OPAQUE'
        return

    image = diffuse_tex.image
    logger.info(f"  - 检查 Alpha for Node: {diffuse_tex.name}, Image: {image.name}")
    has_meaningful_alpha = False # Renamed variable for clarity

    # 首先，检查基本条件：必须有4个通道才可能包含Alpha
    if image.channels == 4:
        logger.info(f"    - 图像有 {image.channels} 个通道，开始像素检查...")
        try:
            # 确保像素数据已加载 (如果图像很大或未完全加载，这步可能会耗时)
            start_load_time = time.time()
            # Accessing pixels implicitly loads them if needed
            pixels = image.pixels[:] # Use slicing to ensure we get a copy, might help with large images
            load_time = time.time() - start_load_time
            if load_time > 0.1: # Log if loading took noticeable time
                 logger.info(f"    - 加载/访问像素耗时: {load_time:.4f} 秒")

            pixel_count = len(pixels) // image.channels # 计算像素总数

            # 检查 Alpha 值 (索引 3, 7, 11, ...)
            # Limit check for performance? For now, check all.
            check_limit = pixel_count # 检查所有像素
            # check_limit = min(pixel_count, 100000) # Example: Limit check

            logger.info(f"    - 准备检查 {check_limit} / {pixel_count} 个像素的 Alpha 值...")
            start_check_time = time.time()
            alpha_step = image.channels # Step should be number of channels

            for i in range(0, check_limit * alpha_step, alpha_step):
                alpha_index = i + 3 # Alpha is the 4th channel (index 3)
                if pixels[alpha_index] < 0.999: # Use a threshold for float comparison
                    has_meaningful_alpha = True
                    logger.info(f"    - 在像素 {i // alpha_step} 发现非不透明 Alpha 值: {pixels[alpha_index]:.4f}")
                    break # 找到一个就足够了

            end_check_time = time.time()
            logger.info(f"    - 像素检查耗时: {end_check_time - start_check_time:.4f} 秒")

            if not has_meaningful_alpha:
                logger.info("    - 所有检查过的像素 Alpha 值均接近 1.0")

        except IndexError as idx_err:
             logger.error(f"    - 检查像素时发生索引错误 (可能图像数据不完整?): {idx_err}")
             has_meaningful_alpha = False # Assume no alpha on error
        except MemoryError as mem_err:
             logger.error(f"    - 检查像素时发生内存错误 (图像可能过大): {mem_err}")
             logger.info(f"    - 跳过 Alpha 像素检查 for {image.name}")
             has_meaningful_alpha = False # Assume no alpha on error
        except Exception as pixel_check_err:
            logger.error(f"    - 检查像素时发生未知错误: {pixel_check_err}")
            import traceback
            traceback.print_exc()
            # 出错时，默认不连接 Alpha
            logger.info("    - 像素检查失败，回退到默认：无有效 Alpha。")
            has_meaningful_alpha = False
    else:
         logger.info(f"    - 图像只有 {image.channels} 个通道，不包含 Alpha。")

    # --- 后续连接逻辑，使用 has_meaningful_alpha ---
    alpha_input = principled_node.inputs.get("Alpha")
    bsdf_alpha_connected = False
    if alpha_input and alpha_input.links:
        bsdf_alpha_connected = True
        logger.info(f"  - 清理旧的 Principled BSDF Alpha 输入连接...")
        for link in list(alpha_input.links):
            logger.info(f"    - 断开 Alpha: {link.from_node.name}.{link.from_socket.name} -> {principled_node.name}.Alpha")
            links.remove(link)

    if has_meaningful_alpha and alpha_input:
        logger.info(f"  - 连接 Alpha: {diffuse_tex.name}.Alpha -> {principled_node.name}.Alpha (基于像素检查)")
        try:
            links.new(diffuse_tex.outputs["Alpha"], alpha_input)
            mat.blend_method = 'HASHED' # Using HASHED for potentially better performance than CLIP
            mat.shadow_method = 'HASHED' # Consistent shadow method
            logger.info(f"  - 设置材质 '{mat.name}' blend/shadow = HASHED")
        except Exception as link_alpha_err:
             logger.error(f"错误: 连接 Alpha 通道失败: {link_alpha_err}")
             # If linking fails, revert blend mode maybe?
             mat.blend_method = 'OPAQUE'
             mat.shadow_method = 'OPAQUE'
    else:
         # If no meaningful alpha, or linking failed, or no alpha input exists
         if bsdf_alpha_connected: # Only log if we previously disconnected something
              logger.info(f"  - 无有效 Alpha 或连接失败，确保材质 '{mat.name}' 为 OPAQUE")
         mat.blend_method = 'OPAQUE'
         mat.shadow_method = 'OPAQUE'


# --- 重构后的 PBR Operator ---

class AUTO_OT_create_pbr_materials(Operator):
    bl_idname = "auto.create_pbr_materials"
    bl_label = "一键PBR材质着色 (重构版)"
    bl_description = "选择贴图文件夹，自动应用PBR材质节点 (已重构)"
    bl_options = {'REGISTER', 'UNDO'}

    # (属性定义保持不变: directory, clean_data, skinuber_cloth_type)
    directory: StringProperty(
        name="贴图文件夹",
        description="选择包含贴图的文件夹",
        subtype='DIR_PATH'
    )
    clean_data: BoolProperty(
        name="清理未使用的数据",
        description="清理未使用的贴图和材质数据，避免.001后缀",
        default=True
    )
    skinuber_cloth_type: EnumProperty(
        name="Skinuber贴图类型",
        description="选择用于skinuber材质的贴图类型",
        items=[
            ('NONE', "不处理", "不处理skinuber材质"),
            ('CLOTH1', "Cloth1贴图", "使用名称中包含cloth1的贴图"),
            ('CLOTH2', "Cloth2贴图", "使用名称中包含cloth2的贴图"),
        ],
        default='CLOTH2' # 默认改为Cloth2试试
    )
    pbr_processing_mode: EnumProperty(
        name="处理模式",
        description="选择 PBR 材质处理模式",
        items=[
            ('FULL', "完整PBR", "处理基础色、RMO和Alpha"),
            ('BASE_ALPHA', "仅基础色+Alpha", "只处理基础色和Alpha，跳过RMO"),
        ],
        default='FULL'
    )
    
    # 添加日志相关属性
    log_to_file: BoolProperty(
        name="输出日志到文件",
        description="将详细执行日志输出到文件中",
        default=True
    )
    log_file_path: StringProperty(
        name="日志文件路径",
        description="指定日志文件输出的路径和文件名",
        subtype='FILE_PATH',
        default="//pbr_material_log.txt"  # 默认在Blender文件同目录
    )
    # 添加复制外部纹理设置
    copy_textures_externally: BoolProperty(
        name="复制纹理到外部文件夹",
        description="为每个材质创建纹理文件的物理副本到指定文件夹，避免导出合并",
        default=False
    )
    external_texture_directory: StringProperty(
        name="外部纹理文件夹",
        description="选择存储复制纹理的目标文件夹",
        subtype='DIR_PATH'
    )

    def invoke(self, context, event):
        """在执行前调用，打开文件选择对话框"""
        # 从场景属性中获取设置
        self.clean_data = context.scene.pbr_clean_data
        self.skinuber_cloth_type = context.scene.pbr_skinuber_cloth_type
        self.processing_mode = context.scene.pbr_processing_mode
        # 获取复制外部纹理设置
        self.copy_textures_externally = context.scene.pbr_copy_textures_externally
        self.external_texture_directory = context.scene.pbr_external_texture_directory
        
        # 从日志设置中获取
        if hasattr(context.scene, "pbr_settings"):
            self.log_to_file = context.scene.pbr_settings.log_to_file
            self.log_file_path = context.scene.pbr_settings.log_file_path
        
        # 打开文件选择对话框
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def setup_single_material(self, mat, diffuse_path, rmo_path, processed_set):
        """设置单个材质的 PBR 节点树 (完整版)"""
        logger = logging.getLogger('pbr_materials')
        logger.info(f"开始设置材质: {mat.name}")
        logger.info(f"  - Diffuse Path: {diffuse_path}")
        logger.info(f"  - RMO Path: {rmo_path}")

        if mat.name in processed_set:
            logger.info(f"材质 '{mat.name}' 已处理，跳过")
            return False # Already processed

        try:
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            # 1. 清理旧节点，保留必要的节点
            logger.info("  - 清理旧节点...")
            existing_output, existing_bsdf, existing_normal_map, existing_normal_texture = _cleanup_material_nodes(nodes, links)
            logger.info(f"    - 保留节点: Output={existing_output}, BSDF={existing_bsdf}, NormalMap={existing_normal_map}, NormalTexture={existing_normal_texture}")

            # 2. 创建或复用基础 BSDF 和 Output 节点
            logger.info("  - 创建/复用基础节点...")
            principled_node, output_node = _create_base_nodes(nodes, links, existing_output, existing_bsdf, existing_normal_map, existing_normal_texture)
            if not principled_node or not output_node:
                 logger.error(f"错误: 无法创建或找到 Principled BSDF 或 Output 节点 for '{mat.name}'")
                 return False

            # 3. 加载纹理节点
            logger.info("  - 加载纹理节点...")
            diffuse_tex_node = None
            rmo_tex_node = None
            mat_base_name = mat.name.split('.')[0] # Get base name for node prefix only

            # --- Diffuse Texture Handling ---
            if diffuse_path:
                final_diffuse_path_for_load = diffuse_path

                logger.info(f"    - 准备加载 Diffuse: '{os.path.basename(final_diffuse_path_for_load)}'")
                # Pass mat.name as material_name argument, REMOVED force_unique_datablock
                diffuse_tex_node = _load_texture_node(nodes, final_diffuse_path_for_load, mat_base_name, mat.name, is_rmo=False)
                if diffuse_tex_node:
                    # actual_diffuse_path = final_diffuse_path_for_load # Not strictly needed anymore
                    logger.info(f"    - Diffuse 节点加载成功: {diffuse_tex_node.name}")
                else:
                     logger.error(f"    - Diffuse 节点加载失败 for: {final_diffuse_path_for_load}")
            else:
                 logger.info("    - 无 Diffuse 路径提供")

            # --- RMO Texture Handling ---
            if self.processing_mode == 'FULL' and rmo_path:
                final_rmo_path_for_load = rmo_path

                logger.info(f"    - 准备加载 RMO: '{os.path.basename(final_rmo_path_for_load)}'")
                # Pass mat.name as material_name argument, REMOVED force_unique_datablock
                rmo_tex_node = _load_texture_node(nodes, final_rmo_path_for_load, mat_base_name, mat.name, is_rmo=True)
                if rmo_tex_node:
                    # actual_rmo_path = final_rmo_path_for_load # Not strictly needed anymore
                    logger.info(f"    - RMO 节点加载成功: {rmo_tex_node.name}")
                else:
                     logger.error(f"    - RMO 节点加载失败 for: {final_rmo_path_for_load}")
            elif self.processing_mode != 'FULL':
                 logger.info("    - 处理模式非 FULL，跳过 RMO 加载")
            else:
                 logger.info("    - 无 RMO 路径提供")

            # 4. 连接纹理到 Principled BSDF
            logger.info("  - 连接纹理到 Principled BSDF...")
            _link_textures_to_principled(nodes, links, principled_node, diffuse_tex_node, rmo_tex_node)

            # 5. 处理 Alpha 通道
            logger.info("  - 处理 Alpha 通道...")
            _handle_alpha_channel(mat, links, principled_node, diffuse_tex_node)

            # --- 特殊处理: eyenewmul 强制透明 ---
            if "eyenewmul" in mat.name.lower():
                logger.info(f"    - 特殊规则: 强制材质 '{mat.name}' (eyenewmul) 为完全透明")
                if principled_node.inputs.get("Alpha"):
                    # 断开可能存在的 Alpha 连接
                    if principled_node.inputs["Alpha"].links:
                        for link in list(principled_node.inputs["Alpha"].links):
                            links.remove(link)
                    # 设置 Alpha 值为 0
                    principled_node.inputs["Alpha"].default_value = 0.0 # 改为 0.0
                mat.blend_method = 'BLEND' # 改为 BLEND
                mat.shadow_method = 'NONE' # 改为 NONE

            # 6. 标记为已处理
            processed_set.add(mat.name)
            logger.info(f"材质 '{mat.name}' 设置成功")
            return True

        except Exception as e:
            logger.error(f"设置材质 '{mat.name}' 时发生严重错误: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return False

    def setup_logger(self):
        """设置日志记录器"""
        # 清除可能存在的handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 创建logger
        logger = logging.getLogger('pbr_materials')
        logger.setLevel(logging.DEBUG) # Set level for the logger itself

        # 创建console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO) # Control console output level

        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        # 添加console handler
        logger.addHandler(console_handler)

        # 如果启用了文件日志
        if self.log_to_file and self.log_file_path:
            try:
                # 解析路径，处理Blender相对路径
                log_path = self.log_file_path
                if log_path.startswith('//'):
                    # 转换到绝对路径
                    log_path = bpy.path.abspath(log_path)

                # 确保目录存在
                log_dir = os.path.dirname(log_path)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)

                # 创建文件handler
                file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
                file_handler.setLevel(logging.DEBUG) # Control file output level
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

                logger.info(f"日志文件已设置: {log_path}")
            except Exception as e:
                logger.error(f"无法设置日志文件: {e}")
                # Use self.report for operator feedback
                self.report({'WARNING'}, f"无法设置日志文件: {e}")
        # Ensure logger propagation is off if desired to avoid duplicate root logger messages
        logger.propagate = False
        return logger

    def _copy_texture_file(self, source_path, target_dir, material_name, suffix):
        """将纹理文件复制到目标目录，并使用材质名和后缀重命名。返回新路径或None。"""
        logger = logging.getLogger('pbr_materials')
        if not source_path or not os.path.exists(source_path):
            logger.error(f"_copy_texture_file: 源文件无效: {source_path}")
            return None
        if not target_dir:
            logger.error(f"_copy_texture_file: 未指定目标目录")
            return None

        try:
            # 确保目标目录存在
            target_dir_abs = bpy.path.abspath(target_dir)
            if not os.path.exists(target_dir_abs):
                os.makedirs(target_dir_abs, exist_ok=True)
                logger.info(f"创建目标目录: {target_dir_abs}")

            # 获取原始文件扩展名
            _, ext = os.path.splitext(source_path)
            if not ext:
                ext = ".png" # 如果没有扩展名，默认使用.png
                logger.warning(f"源文件 '{os.path.basename(source_path)}' 无扩展名，默认使用 '.png'")

            # 构建新文件名 (使用材质名 + 后缀 + 扩展名)
            # 清理材质名中的非法字符，以用于文件名
            safe_material_name = re.sub(r'[^\w\-. ]', '_', material_name) # 允许字母数字、下划线、连字符、点、空格
            new_filename = f"{safe_material_name}{suffix}{ext}"
            target_path = os.path.join(target_dir_abs, new_filename)

            # 执行复制 (shutil.copy2 会保留元数据)
            shutil.copy2(source_path, target_path)
            logger.info(f"复制外部纹理: '{os.path.basename(source_path)}' -> '{new_filename}'")
            return target_path

        except Exception as e:
            logger.error(f"复制外部纹理 '{os.path.basename(source_path)}' 到 '{target_dir}' 失败: {e}", exc_info=True)
            return None

    def execute(self, context):
        # 设置日志记录器
        logger = self.setup_logger()
        logger.info("=" * 50)
        logger.info("开始执行一键PBR材质着色 (重构版)")

        start_time = time.time()
        if not self.directory or not os.path.exists(self.directory):
            logger.error(f"无效的贴图文件夹: {self.directory}")
            self.report({'ERROR'}, "请选择有效的贴图文件夹")
            return {'CANCELLED'}

        # 检查外部复制设置是否有效
        if self.copy_textures_externally and not self.external_texture_directory:
            logger.error("启用了外部复制，但未指定目标文件夹")
            self.report({'ERROR'}, "请指定外部纹理文件夹")
            return {'CANCELLED'}

        # 规范化路径
        self.directory = os.path.normpath(self.directory)
        if self.external_texture_directory:
            self.external_texture_directory = os.path.normpath(bpy.path.abspath(self.external_texture_directory))
            logger.info(f"外部纹理目标目录: {self.external_texture_directory}")
        else:
             logger.info("未启用外部纹理复制")

        logger.info(f"源贴图目录: {self.directory}")
        logger.info(f"创建独立数据块: {self.clean_data}")
        logger.info(f"复制纹理到外部: {self.copy_textures_externally}")
        logger.info(f"清理未使用数据: {self.clean_data}")
        logger.info(f"Skinuber贴图类型: {self.skinuber_cloth_type}")
        logger.info(f"PBR 处理模式: {self.processing_mode}")
        logger.info("=" * 50)

        # 1. 清理未使用数据 (可选)
        if self.clean_data:
            logger.info("开始清理未使用数据")
            try:
                bpy.ops.outliner.orphans_purge(do_recursive=True)
                bpy.ops.outliner.orphans_purge(do_recursive=True) # Run twice for good measure
                logger.info("已执行孤立数据清理")
            except Exception as clean_err:
                 logger.error(f"清理数据时出错: {clean_err}")
            logger.info("清理数据结束")

        # 2. 收集场景材质和贴图文件
        logger.info("开始收集材质和贴图")
        all_materials = {mat.name: mat for mat in bpy.data.materials}
        logger.info(f"找到 {len(all_materials)} 个场景材质")
        for mat_name in all_materials:
            logger.debug(f"材质: {mat_name}")

        texture_files = [f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))]
        logger.info(f"找到 {len(texture_files)} 个文件在源目录")
        for f in texture_files:
            logger.debug(f"文件: {f}")

        # 按基础名称整理贴图 (Diffuse 和 RMO)
        texture_dict = defaultdict(dict)
        special_textures = defaultdict(list) # face, eyeblend, hair, cloth1, cloth2
        # 修改后缀映射，去掉点
        texture_suffix_map = {"_d": "diffuse", "_rmo": "rmo"}

        logger.info("开始识别贴图类型和基础名称")
        for file in texture_files:
            file_path = os.path.join(self.directory, file)
            base_name = file
            texture_type = None

            logger.debug(f"处理文件: {file}")

            # 识别贴图类型和基础名称
            root, ext = os.path.splitext(file)
            for suffix, type_name in texture_suffix_map.items():
                # 修改：检查文件名是否以后缀结尾
                if root.endswith(suffix):
                    # 获取基础名称（去掉后缀）
                    base_name = root[:-len(suffix)] # 使用切片移除后缀
                    texture_type = type_name
                    logger.debug(f"识别到贴图类型: {file} -> 类型={type_name}, 基础名={base_name}")
                    break # 找到主要类型后跳出循环

            if texture_type:
                texture_dict[base_name][texture_type] = file_path
                logger.info(f"识别到贴图: Base='{base_name}', Type='{texture_type}', File='{file}'")

                # 收集特殊用途贴图 (仅Diffuse)
                if texture_type == 'diffuse':
                    name_lower = base_name.lower()
                    special_texture_types = {
                        'face': 'face' in name_lower and 'eyeface' not in name_lower,
                        # 'eyeblend' 由下面的特殊捕获处理
                        'hair': 'hair' in name_lower and 'eyehair' not in name_lower,
                        'cloth1': 'cloth1' in name_lower,
                        'cloth2': 'cloth2' in name_lower
                    }

                    for sp_type, condition in special_texture_types.items():
                        if condition:
                            special_textures[sp_type].append((base_name, file_path))
                            logger.info(f"识别到特殊贴图: {sp_type} -> {file}")

            # 捕获 eyeblend 贴图，无论后缀如何
            if 'eyeblend' in root.lower(): # 在不含扩展名的部分检查
                already_added = any(item[1] == file_path for item in special_textures['eyeblend'])
                if not already_added:
                    # 使用不含扩展名的部分作为基础名
                    eyeblend_base_name = root
                    special_textures['eyeblend'].append((eyeblend_base_name, file_path))
                    logger.info(f"特殊捕获: Eyeblend 贴图 '{file}' (基础名: {eyeblend_base_name})")

        # 打印识别结果总览
        logger.info(f"整理后得到 {len(texture_dict)} 个贴图基础名称")
        logger.info(f"特殊贴图: Face={len(special_textures['face'])}, Eyeblend={len(special_textures['eyeblend'])}, Hair={len(special_textures['hair'])}, Cloth1={len(special_textures['cloth1'])}, Cloth2={len(special_textures['cloth2'])}")

        # 打印详细的texture_dict内容
        logger.info("--- 贴图字典内容 ---")
        for base, types in texture_dict.items():
            logger.info(f"  基础名: {base}")
            for type_name, path in types.items():
                logger.info(f"    - {type_name}: {os.path.basename(path)}")
        logger.info("--- 贴图字典内容结束 ---")

        # 打印特殊贴图字典内容
        logger.info("--- 特殊贴图内容 ---")
        for special_type, items in special_textures.items():
            logger.info(f"  类型: {special_type}")
            for base_name, path in items:
                logger.info(f"    - {base_name}: {os.path.basename(path)}")
        logger.info("--- 特殊贴图内容结束 ---")

        # 3. 处理材质
        logger.info("开始处理材质")
        processed_materials_set = set()
        materials_processed_count = 0
        materials_failed_count = 0
        external_copy_count = 0 # 跟踪外部复制次数

        # --- 特殊规则处理 ---
        logger.info("开始应用特殊材质规则")

        # 缓存特殊贴图路径
        eyeblend_path = special_textures['eyeblend'][0][1] if special_textures['eyeblend'] else None
        face_path = special_textures['face'][0][1] if special_textures['face'] else None
        hair_path = special_textures['hair'][0][1] if special_textures['hair'] else None

        if eyeblend_path: logger.info(f"使用eyeblend贴图: {os.path.basename(eyeblend_path)}")
        if face_path: logger.info(f"使用face贴图: {os.path.basename(face_path)}")
        if hair_path: logger.info(f"使用hair贴图: {os.path.basename(hair_path)}")

        # 缓存 RMO 贴图路径查找函数
        def find_rmo_for_base(base_name):
            rmo = texture_dict.get(base_name, {}).get('rmo')
            logger.debug(f"查找RMO for {base_name}: {'找到' if rmo else '未找到'}")
            return rmo

        # 遍历所有材质，应用特殊规则
        for mat_name, mat in all_materials.items():
            mat_name_lower = mat_name.lower()
            diffuse_to_use = None
            rmo_to_use = None
            # REMOVED: force_unique = False # 不再需要在这里初始化和重置
            rule_applied = True

            logger.info(f"处理材质: {mat_name} (lower: {mat_name_lower})")
            logger.debug(f"规则检查: eyelashuber: {'eyelashuber' in mat_name_lower}")
            logger.debug(f"规则检查: fringeuber: {'fringeuber' in mat_name_lower}")
            logger.debug(f"规则检查: skinuber: {'skinuber' in mat_name_lower}")
            logger.debug(f"规则检查: eyenewadd: {'eyenewadd' in mat_name_lower}")
            logger.debug(f"规则检查: eyenewmul: {'eyenewmul' in mat_name_lower}")

            # 特殊规则应用逻辑 - 保持现有代码逻辑不变，只添加日志记录
            if 'eyelashuber' in mat_name_lower:
                if special_textures['face']:
                    diffuse_to_use = special_textures['face'][0][1]
                    logger.info(f"规则应用: '{mat_name}' (eyelashuber) -> 使用 'face' 贴图")
                else:
                    logger.warning(f"警告: 未找到 'face' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'eyenewadd' in mat_name_lower or 'eyenewmul' in mat_name_lower:
                if eyeblend_path:
                    diffuse_to_use = eyeblend_path
                    # REMOVED: force_unique = self.copy_textures # 不再在这里单独设置
                    logger.info(f"规则应用: '{mat_name}' ({'eyenewadd' if 'add' in mat_name_lower else 'eyenewmul'}) -> 使用 'eyeblend' 贴图 {'(强制唯一副本将由全局设置决定)'}") # Log message updated
                else:
                    logger.warning(f"警告: 未找到 'eyeblend' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'fringeuber' in mat_name_lower:
                 if hair_path:
                    diffuse_to_use = hair_path
                    # 查找对应的 RMO
                    hair_base_name = special_textures['hair'][0][0]
                    rmo_to_use = find_rmo_for_base(hair_base_name)
                    logger.info(f"规则应用: '{mat_name}' (fringeuber) -> 使用 'hair' 贴图 {'和 RMO' if rmo_to_use else ''}")
                 else:
                    logger.warning(f"警告: 未找到 'hair' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'skinuber' in mat_name_lower:
                if self.skinuber_cloth_type != 'NONE':
                    cloth_key = 'cloth1' if self.skinuber_cloth_type == 'CLOTH1' else 'cloth2'
                    logger.info(f"skinuber材质使用{cloth_key}贴图")
                    if special_textures[cloth_key]:
                        diffuse_to_use = special_textures[cloth_key][0][1]
                        # 查找对应的 RMO
                        cloth_base_name = special_textures[cloth_key][0][0]
                        rmo_path = texture_dict.get(cloth_base_name, {}).get('rmo')
                        if rmo_path:
                            rmo_to_use = rmo_path
                        logger.info(f"规则应用: '{mat_name}' (skinuber) -> 使用 '{cloth_key}' 贴图 {'和 RMO' if rmo_to_use else ''}")
                    else:
                        logger.warning(f"警告: 未找到 '{cloth_key}' 贴图用于 '{mat_name}'")
                        rule_applied = False
                else:
                    logger.info(f"跳过skinuber材质处理 (设置为NONE)")
                    rule_applied = False
            else:
                logger.info(f"材质 '{mat_name}' 不适用特殊规则")
                rule_applied = False

            # 如果应用了特殊规则，并且找到了贴图
            if rule_applied and diffuse_to_use:
                # *** 修改: 外部复制逻辑 ***
                final_diffuse_path = diffuse_to_use
                final_rmo_path = rmo_to_use
                # mat_base_name = mat_name.split('.')[0] # Use full material name for copying

                logger.info(f"应用特殊规则 '{mat_name}':")
                logger.info(f"  - 初始Diffuse: '{os.path.basename(diffuse_to_use) if diffuse_to_use else 'None'}'")
                logger.info(f"  - 初始RMO: '{os.path.basename(rmo_to_use) if rmo_to_use else 'None'}'")
                logger.info(f"  - 复制外部选项: {self.copy_textures_externally}")
                logger.info(f"  - 独立数据块选项: {self.clean_data}")

                # --- 外部复制处理 --- 
                if self.copy_textures_externally and self.external_texture_directory:
                    if diffuse_to_use:
                        copied_d_path = self._copy_texture_file(diffuse_to_use, self.external_texture_directory, mat_name, "_d")
                        if copied_d_path:
                            final_diffuse_path = copied_d_path
                            external_copy_count += 1
                        else:
                            logger.error(f"无法复制漫反射贴图 '{os.path.basename(diffuse_to_use)}' 到外部目录，将使用原始路径")
                    
                    if rmo_to_use and self.processing_mode == 'FULL': # Only copy RMO if processing it
                        copied_rmo_path = self._copy_texture_file(rmo_to_use, self.external_texture_directory, mat_name, "_rmo")
                        if copied_rmo_path:
                            final_rmo_path = copied_rmo_path
                            external_copy_count += 1 # Count RMO copies too if needed
                        else:
                            logger.error(f"无法复制RMO贴图 '{os.path.basename(rmo_to_use)}' 到外部目录，将使用原始路径")
                # --- 外部复制处理结束 --- 

                # 调用材质设置函数 - force_unique 由 self.copy_textures 控制 (独立数据块)
                try:
                    logger.info(f"  - 设置材质: {mat_name}")
                    logger.info(f"  - 使用Diffuse路径: '{final_diffuse_path if final_diffuse_path else 'None'}'")
                    logger.info(f"  - 使用RMO路径: '{final_rmo_path if final_rmo_path else 'None'}'")

                    # 传递最终的文件路径和独立数据块设置
                    if self.setup_single_material(mat, final_diffuse_path, final_rmo_path, processed_materials_set):
                        materials_processed_count += 1
                        logger.info(f"材质 '{mat_name}' 处理成功")
                    else:
                        materials_failed_count += 1
                        logger.warning(f"材质 '{mat_name}' 处理失败")
                except Exception as e:
                    materials_failed_count += 1
                    logger.error(f"设置材质 '{mat_name}' 时发生错误: {e}")
                # else: # Original logic had an else block here, seems it was meant for when rules didn't apply or diffuse wasn't found
                    # This part seems less relevant now, as materials not handled by special rules fall through to regular matching.
                    # If you need to log something specific here, you can add it. Example:
                    # elif not rule_applied:
                    #     logger.info(f"材质 '{mat_name}' 未应用特殊规则，将尝试常规匹配")
                    # elif not diffuse_to_use:
                    #     logger.warning(f"材质 '{mat_name}' 应用规则但未找到漫反射贴图")


        # --- 常规智能匹配处理 ---
        logger.info("\n--- 开始常规智能匹配 ---")
        # (收集所有未被特殊规则处理的材质)
        remaining_materials = {name: mat for name, mat in all_materials.items() if name not in processed_materials_set}
        logger.info(f"剩余 {len(remaining_materials)} 个材质待智能匹配")

        for base_name, textures in texture_dict.items():
            # 跳过没有漫反射的组
            diffuse_path = textures.get('diffuse')
            if not diffuse_path:
                logger.debug(f"跳过贴图组 '{base_name}' (无漫反射贴图)")
                continue

            rmo_path = textures.get('rmo')
            logger.info(f"尝试为贴图组 '{base_name}' 匹配材质...")

            best_match_name = None
            best_score = 0

            # Iterate over a copy of the keys to allow deletion within the loop
            for mat_name in list(remaining_materials):
                score = 0
                mat_name_lower = mat_name.lower()
                base_name_lower = base_name.lower()

                mat_base_lower = mat_name_lower
                if mat_base_lower.endswith('_uber'):
                    mat_base_lower = mat_base_lower[:-5]

                if mat_base_lower == base_name_lower:
                    score = 100
                elif mat_base_lower.startswith(base_name_lower):
                    score = len(base_name_lower) + 10
                elif base_name_lower.startswith(mat_base_lower):
                    score = len(mat_base_lower)
                # Consider adding fuzzy matching score here if needed

                logger.debug(f"匹配比较: 贴图基础名='{base_name_lower}', 材质基础名='{mat_base_lower}', 得分={score}")

                if score > best_score:
                    best_score = score
                    best_match_name = mat_name

                # 修改匹配阈值：从 >= 100 改为 >= 30
                if best_match_name and best_score >= 30:
                    # *** ADD CHECK HERE: Ensure the best match wasn't processed in a previous outer loop iteration ***
                    if best_match_name in remaining_materials:
                        mat = remaining_materials[best_match_name]
                        logger.info(f"智能匹配成功: 贴图 '{base_name}' -> 材质 '{best_match_name}' (Score: {best_score})")

                        # *** 修改: 外部复制逻辑 ***
                        final_diffuse_path = diffuse_path
                        final_rmo_path = rmo_path

                        logger.info(f"智能匹配 '{best_match_name}':")
                        logger.info(f"  - 初始Diffuse: '{os.path.basename(diffuse_path) if diffuse_path else 'None'}'")
                        logger.info(f"  - 初始RMO: '{os.path.basename(rmo_path) if rmo_path else 'None'}'")
                        logger.info(f"  - 复制外部选项: {self.copy_textures_externally}")
                        logger.info(f"  - 独立数据块选项: {self.clean_data}")
                        
                        # --- 外部复制处理 ---
                        if self.copy_textures_externally and self.external_texture_directory:
                            if diffuse_path:
                                copied_d_path = self._copy_texture_file(diffuse_path, self.external_texture_directory, best_match_name, "_d")
                                if copied_d_path:
                                    final_diffuse_path = copied_d_path
                                    external_copy_count += 1
                                else:
                                    logger.error(f"无法复制漫反射贴图 '{os.path.basename(diffuse_path)}' 到外部目录，将使用原始路径")
                            
                            if rmo_path and self.processing_mode == 'FULL': # Only copy RMO if processing it
                                copied_rmo_path = self._copy_texture_file(rmo_path, self.external_texture_directory, best_match_name, "_rmo")
                                if copied_rmo_path:
                                    final_rmo_path = copied_rmo_path
                                    external_copy_count += 1
                                else:
                                    logger.error(f"无法复制RMO贴图 '{os.path.basename(rmo_path)}' 到外部目录，将使用原始路径")
                        # --- 外部复制处理结束 ---

                        # 处理材质 - force_unique 由 self.copy_textures 控制
                        try:
                            logger.info(f"  - 设置材质: {best_match_name} (常规匹配)")
                            logger.info(f"  - 使用Diffuse路径: '{final_diffuse_path if final_diffuse_path else 'None'}'")
                            logger.info(f"  - 使用RMO路径: '{final_rmo_path if final_rmo_path else 'None'}'")
                            
                            # 传递最终的文件路径和独立数据块设置
                            if self.setup_single_material(mat, final_diffuse_path, final_rmo_path, processed_materials_set):
                                materials_processed_count += 1
                                logger.info(f"材质 '{best_match_name}' 处理成功")
                                del remaining_materials[best_match_name]
                            else:
                                materials_failed_count += 1
                                # Log failure here if setup_single_material returned False
                                logger.warning(f"材质 '{best_match_name}' (常规匹配) setup_single_material 返回 False")
                        except Exception as e:
                            materials_failed_count += 1
                            logger.error(f"设置材质 '{best_match_name}' (常规匹配) 时发生错误: {e}", exc_info=True)
                    else:
                        # Log that the best match was found but already processed earlier
                        logger.warning(f"贴图组 '{base_name}' 的最佳匹配 '{best_match_name}' 已在之前的迭代中处理，跳过")
                else:
                     # 仅在 best_match_name 存在但分数不够时记录更详细的信息
                     if best_match_name:
                         logger.info(f"贴图组 '{base_name}' 找到潜在匹配 '{best_match_name}' 但分数 ({best_score}) 不足 30")
                     else:
                         logger.info(f"贴图组 '{base_name}' 未找到任何常规材质匹配")


        # 打印最终未处理的材质
        if remaining_materials:
            logger.warning("--- 以下材质未找到匹配的贴图或未被处理 ---")
            for mat_name in remaining_materials:
                logger.warning(f"- {mat_name}")
            logger.warning("--- 未处理材质列表结束 ---")

        # 完成处理，记录统计信息
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info("=" * 50)
        logger.info(f"PBR材质处理完成，耗时 {elapsed_time:.2f} 秒")
        logger.info(f"处理成功: {materials_processed_count} 个材质")
        logger.info(f"处理失败/跳过: {materials_failed_count} 个材质")
        if self.copy_textures_externally:
            logger.info(f"外部复制: {external_copy_count} 个纹理文件") # Log external copy count
        logger.info("=" * 50)

        # --- 新的清理位置：在所有处理完成后执行 ---
        if self.clean_data:
            logger.info("开始清理未使用数据 (最终)")
            try:
                # 确保在 Object 模式下执行清理
                if bpy.context.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.outliner.orphans_purge(do_recursive=True)
                bpy.ops.outliner.orphans_purge(do_recursive=True) # 多执行一次确保清理干净
                logger.info("已执行最终孤立数据清理")
            except Exception as clean_err:
                 logger.error(f"最终清理数据时出错: {clean_err}")
            logger.info("最终清理数据结束")

        return {'FINISHED'}

    # ...【保留类中的其他方法】...

# 修改面板类，添加日志选项
class MQT_PT_PBRMaterialPanel(Panel):
    bl_label = "一键PBR材质着色"
    bl_idname = "MQT_PT_PBRMaterialPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 添加操作按钮
        box = layout.box()
        row = box.row()
        # 注意：这里的 bl_idname 要与重构后的 Operator 类名一致
        row.operator(AUTO_OT_create_pbr_materials.bl_idname, icon='NODE_MATERIAL')
        
        # 添加属性设置
        props = box.column()
        props.label(text="内部设置:")
        # Removed output directory setting
        props.prop(context.scene, "pbr_clean_data")
        props.prop(context.scene, "pbr_skinuber_cloth_type", text="Skinuber贴图类型")
        # Add the processing mode selector
        props.prop(context.scene, "pbr_processing_mode", text="处理模式")

        # 添加复制外部纹理设置
        props.separator()
        props.label(text="外部复制设置 (防合并):")
        row = props.row()
        row.prop(context.scene, "pbr_copy_textures_externally")
        row = props.row()
        row.enabled = context.scene.pbr_copy_textures_externally # 仅在启用时可选路径
        row.prop(context.scene, "pbr_external_texture_directory")

        # 添加日志设置UI
        box = layout.box()
        box.label(text="日志设置:")
        row = box.row()
        row.prop(context.scene.pbr_settings, "log_to_file")
        if context.scene.pbr_settings.log_to_file:
            row = box.row()
            row.prop(context.scene.pbr_settings, "log_file_path")
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明:", icon='INFO')
        box.label(text="1. 确保材质已存在于场景中")
        box.label(text="2. 将贴图命名为类似于材质名称的格式")
        box.label(text="3. 漫反射贴图添加_d后缀")
        box.label(text="4. RMO贴图添加_rmo后缀")
        box.label(text="5. 设置输出文件夹(可选)")
        box.label(text="6. 智能匹配贴图到材质")
        
        # 特殊规则说明
        special_box = layout.box()
        special_box.label(text="特殊规则:", icon='INFO')
        special_box.label(text="* eyelashuber → face贴图")
        special_box.label(text="* eyenewadd → eyeblend贴图(复制+独立)")
        special_box.label(text="* eyenewmul → eyeblend贴图(复制+独立)")
        special_box.label(text="* fringeuber → hair贴图(复制)")
        special_box.label(text="* skinuber → 根据选择使用cloth1/cloth2贴图")

# --------------------------------------------------------------------------
# 类注册和注销
# --------------------------------------------------------------------------

# (其他类的注册保持不变)

classes = (
    # 快速拆分助手相关类
    ExcludedItem,
    ExcludedMaterial,
    QSeparatorSettings,
    QSEPARATOR_OT_CopyText,
    QSEPARATOR_OT_AddSearchItem,
    QSEPARATOR_OT_RemoveSearchItem,
    QSEPARATOR_OT_ClearAllItems,
    QSEPARATOR_OT_QuickSeparate,
    QSEPARATOR_OT_SelectItem,
    QSEPARATOR_OT_AddMaterialItem,
    QSEPARATOR_OT_RemoveMaterialItem,
    QSEPARATOR_OT_ClearAllMaterials,
    QSEPARATOR_OT_OrganizeOutlines,
    MQT_PT_SeparatorPanel,
    QS_UL_ExcludedItems,
    
    # 快速选择骨骼相关类
    BONE_OT_SelectBonesByKeyword,
    MQT_PT_BoneSelectorPanel,
    
    # 一键描边相关类
    OUTLINE_OT_AddAll,
    OUTLINE_OT_AddSelected,
    OUTLINE_OT_DeleteAll,
    OUTLINE_OT_CopySMD,
    MQT_PT_OutlinePanel,
    
    # 清除骨骼形状相关类
    BONE_OT_ClearCustomShapes,
    MQT_PT_BoneShapePanel,
    
    # VMT材质批量复制工具相关类
    MaterialGroupItem,
    VMT_OT_RefreshList,
    VMT_OT_AssignSource,
    VMT_OT_CopyMaterials,
    VMT_OT_SelectAll,
    VMT_OT_DeselectAll,
    MQT_PT_VMTPanel,
    
    # 骨骼工具相关类
    BONE_OT_merge_to_parent,
    BONE_OT_merge_to_active,
    BONE_OT_merge_siblings_half,
    BONE_OT_remove_zero_weight,
    BONE_OT_apply_pose_transform,
    BONE_OT_GFL2_preprocess,
    MQT_PT_BoneToolsPanel,
    
    # 一键PBR材质着色工具相关类 (使用重构后的 Operator)
    PBRMaterialSettings,  # 添加PBR设置属性组
    AUTO_OT_create_pbr_materials,
    MQT_PT_PBRMaterialPanel,
)

def register():
    # (其他类的注册保持不变)
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # 注册快速拆分助手设置
    bpy.types.Scene.qseparator_settings = bpy.props.PointerProperty(type=QSeparatorSettings)
    
    # 注册骨骼选择器设置
    bpy.types.Scene.bone_keyword = bpy.props.StringProperty(
        name="关键词",
        description="输入关键词搜索骨骼",
        default=""
    )
    bpy.types.Scene.case_sensitive = bpy.props.BoolProperty(
        name="区分大小写搜索骨骼",
        description="区分大小写搜索骨骼",
        default=False
    )
    
    # 注册描边设置
    bpy.types.Scene.outline_size = bpy.props.FloatProperty(
        name="描边大小",
        description="设置描边的大小（米），沿法线方向缩放，输入正值，自动转为负值",
        default=0.05,
        min=0.001,
        soft_min=0.001,
        soft_max=1.0
    )
    bpy.types.Scene.use_outline_base = bpy.props.BoolProperty(
        name="使用统一 Outline_Base 材质",
        description="如果开启，第一个材质槽将使用 Outline_Base 材质，其他槽保留原材质但添加前缀",
        default=True
    )
    bpy.types.Scene.use_named_materials = bpy.props.BoolProperty(
        name="根据名称使用特定材质",
        description="如果开启，根据模型名称分配描边材质，如 Outline_Hair 或 Outline_Face",
        default=True
    )
    bpy.types.Scene.outline_mode = bpy.props.EnumProperty(
        name="描边放置模式",
        description="选择描边对象的放置模式",
        items=[
            ('ORIGINAL', "原集合", "描边对象和原对象放在相同的集合中"),
            ('SINGLE', "统一集合", "所有描边对象放在一个统一的集合中"),
            ('SEPARATE', "单独集合", "每个描边对象放在单独的集合中")
        ],
        default='SEPARATE'  # 默认放在单独集合中
    )
    bpy.types.Scene.include_all_models = bpy.props.BoolProperty(
        name="输出全部",
        description="是否输出原模型与描边模型，排除名称为 'Face' 和 'smd_bone_vis' 的对象",
        default=False
    )
    
    # 注册VMT材质批量复制工具设置
    bpy.types.Scene.material_groups = bpy.props.CollectionProperty(type=MaterialGroupItem)
    bpy.types.Scene.source_vmt_path = bpy.props.StringProperty(
        name="源VMT文件夹",
        description="选择包含源VMT文件的文件夹",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.target_vmt_path = bpy.props.StringProperty(
        name="目标VMT路径",
        description="选择VMT文件复制的目标文件夹",
        subtype='DIR_PATH'
    )
    
    # 注册一键PBR材质工具设置
    # REMOVED: bpy.types.Scene.pbr_output_directory
    bpy.types.Scene.pbr_clean_data = bpy.props.BoolProperty(
        name="清理未使用的数据",
        description="清理未使用的贴图和材质数据，避免.001后缀",
        default=True
    )
    bpy.types.Scene.pbr_skinuber_cloth_type = bpy.props.EnumProperty(
        name="Skinuber贴图类型",
        description="选择用于skinuber材质的贴图类型",
        items=[
            ('NONE', "不处理", "不处理skinuber材质"),
            ('CLOTH1', "Cloth1贴图", "使用名称中包含cloth1的贴图"),
            ('CLOTH2', "Cloth2贴图", "使用名称中包含cloth2的贴图"),
        ],
        default='CLOTH2'
    )
    bpy.types.Scene.pbr_processing_mode = bpy.props.EnumProperty(
        name="处理模式",
        description="选择 PBR 材质处理模式",
        items=[
            ('FULL', "完整PBR", "处理基础色、RMO和Alpha"),
            ('BASE_ALPHA', "仅基础色+Alpha", "只处理基础色和Alpha，跳过RMO"),
        ],
        default='FULL'
    )
    # 注册复制外部纹理设置
    bpy.types.Scene.pbr_copy_textures_externally = bpy.props.BoolProperty(
        name="复制纹理到外部文件夹",
        description="为每个材质创建纹理文件的物理副本到指定文件夹，避免导出合并",
        default=False
    )
    bpy.types.Scene.pbr_external_texture_directory = bpy.props.StringProperty(
        name="外部纹理文件夹",
        description="选择存储复制纹理的目标文件夹",
        subtype='DIR_PATH'
    )

    # 注册PBR日志设置
    bpy.types.Scene.pbr_settings = bpy.props.PointerProperty(type=PBRMaterialSettings)

def unregister():
    # (其他类的注销保持不变)

    # 注销一键PBR材质工具设置 (保持不变)
    # REMOVED: del bpy.types.Scene.pbr_output_directory
    del bpy.types.Scene.pbr_clean_data
    del bpy.types.Scene.pbr_skinuber_cloth_type
    del bpy.types.Scene.pbr_processing_mode
    # 注销复制外部纹理设置
    del bpy.types.Scene.pbr_copy_textures_externally
    del bpy.types.Scene.pbr_external_texture_directory

    # 注销PBR日志设置
    del bpy.types.Scene.pbr_settings
    
    # 注销所有类 (包括重构后的 PBR Operator)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

# 主函数 (保持不变)
if __name__ == "__main__":
    register()