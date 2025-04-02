import bpy
import os
import time
import requests
import shutil
import re
import math
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
                    # 从当前父集合中解除链接
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
        
        # 在非姿态模式下禁用按钮
        if context.mode != 'POSE':
            layout.enabled = False

# --------------------------------------------------------------------------
# 类注册和注销
# --------------------------------------------------------------------------

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
    BONE_OT_merge_siblings_half,  # 确保这行被添加
    BONE_OT_remove_zero_weight,
    BONE_OT_apply_pose_transform,
    MQT_PT_BoneToolsPanel,
)

def register():
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

def unregister():
    # 注销VMT材质批量复制工具设置
    del bpy.types.Scene.target_vmt_path
    del bpy.types.Scene.source_vmt_path
    del bpy.types.Scene.material_groups
    
    # 注销描边设置
    del bpy.types.Scene.include_all_models
    del bpy.types.Scene.outline_mode
    del bpy.types.Scene.use_named_materials
    del bpy.types.Scene.use_outline_base
    del bpy.types.Scene.outline_size
    
    # 注销骨骼选择器设置
    del bpy.types.Scene.case_sensitive
    del bpy.types.Scene.bone_keyword
    
    # 注销快速拆分助手设置
    del bpy.types.Scene.qseparator_settings
    
    # 注销所有类
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

# 主函数
if __name__ == "__main__":
    register()