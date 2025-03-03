from typing import Dict, Set, List, Optional
from dataclasses import dataclass
from collections import defaultdict

bl_info = {
    "name": "快速拆分助手 Pro",
    "author": "你的名字",
    "version": (3, 2),
    "blender": (4, 2, 0),
    "location": "View3D > UI > 快速拆分助手",
    "description": "增强版智能拆分工具，基于集合生成SMD配置",
    "category": "Object",
}

import bpy
import time
import requests  # 确保导入requests库

# ------------------------- 属性定义 -------------------------
class ExcludedItem(bpy.types.PropertyGroup):
    target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="排除对象",
        description="选择要排除的网格对象",
        poll=lambda self, obj: obj.type == 'MESH'
    )

class ExcludedMaterial(bpy.types.PropertyGroup):
    material: bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="排除材质",
        description="选择要排除的材质"
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
    
    if translate_mode in {'CH2EN', 'AI_CH2EN'}:
        # 中译英模式：bodygroup使用原始中文名称，InNode使用翻译后的英文名称
        translated_name = translate_text(original_name, translate_mode)
        display_name = original_name  # bodygroup显示原始中文
        node_name = translated_name   # InNode使用翻译后的英文
    else:
        # 其他模式：正常翻译处理
        display_name = translate_text(original_name, translate_mode) if translate_mode != 'NONE' else original_name
        node_name = original_name
    
    # 根据是否包含blank调整缩进
    indent = "    " if include_blank else "        "
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
    elif export_mode == 'GLB':
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio $custom_model$ InNode {node_name}\n'
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
        
        self.report({'INFO'}, f"预处理完成：已整理 {len(context.scene.objects)} 个对象")
        return {'FINISHED'}
        
    except Exception as e:
        self.report({'ERROR'}, f"预处理失败：{str(e)}")
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

# 添加材质列表操作符 - 确保在QSEPARATOR_PT_MainPanel之前定义
class QSEPARATOR_OT_AddMaterialItem(bpy.types.Operator):
    bl_idname = "qseparator.add_material_item"
    bl_label = "添加材质排除"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        settings.excluded_materials.add()
        settings.material_active_index = len(settings.excluded_materials) - 1
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
        # 获取所有合集
        collections = bpy.data.collections
        outline_collections = {}
        base_collections = {}
        
        # 分类合集
        for coll in collections:
            if coll.name.startswith("Outline"):
                # 获取基础名称（去掉Outline前缀和第一个下划线）
                base_name = coll.name.split('_', 1)[1] if '_' in coll.name else coll.name[7:]
                # 如果基础名称还包含"_mesh"后缀，去掉它
                if base_name.endswith("_mesh"):
                    base_name = base_name[:-5]
                outline_collections[base_name] = coll
            else:
                # 如果集合名称以"_mesh"结尾，去掉这个后缀用于匹配
                match_name = coll.name[:-5] if coll.name.endswith("_mesh") else coll.name
                base_collections[match_name] = coll
        
        # 记录处理数量
        processed_count = 0
        
        # 整理描边合集
        for base_name, outline_coll in outline_collections.items():
            # 检查是否存在对应的基础合集
            matching_base = None
            for name, coll in base_collections.items():
                # 检查基础名称是否匹配（忽略大小写）
                if base_name.lower() in name.lower() or name.lower() in base_name.lower():
                    matching_base = coll
                    break
            
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
                        print(f"已移动 {outline_coll.name} 到 {matching_base.name}")  # 调试信息
                    except Exception as e:
                        print(f"移动合集 {outline_coll.name} 时出错: {str(e)}")
        
        # 报告结果
        if processed_count > 0:
            self.report({'INFO'}, f"已整理 {processed_count} 个描边合集")
        else:
            self.report({'INFO'}, "没有需要整理的描边合集")
            
        return {'FINISHED'}

# ------------------------- 界面面板 -------------------------
class QSEPARATOR_PT_MainPanel(bpy.types.Panel):
    bl_label = "快速拆分助手 Pro"
    bl_idname = "QSEPARATOR_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "快速拆分助手"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.qseparator_settings
        
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
        ctrl_row.operator(QSEPARATOR_OT_AddSearchItem.bl_idname, icon='ADD')
        ctrl_row.operator(QSEPARATOR_OT_RemoveSearchItem.bl_idname, icon='REMOVE')
        ctrl_row.operator(QSEPARATOR_OT_ClearAllItems.bl_idname, icon='TRASH')
        
        # 动态列表项
        list_col = ex_box.column(align=True)
        for idx, item in enumerate(settings.excluded_items):
            row = list_col.row(align=True)
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

        # 添加材质排除列表
        mat_box = layout.box()
        mat_box.label(text="材质排除列表:", icon='MATERIAL')
        mat_box.prop(settings, "affect_materials", text="应用材质排除")
        
        # 材质列表控制按钮
        mat_row = mat_box.row(align=True)
        mat_row.operator(QSEPARATOR_OT_AddMaterialItem.bl_idname, icon='ADD')
        mat_row.operator(QSEPARATOR_OT_RemoveMaterialItem.bl_idname, icon='REMOVE')
        mat_row.operator(QSEPARATOR_OT_ClearAllMaterials.bl_idname, icon='TRASH')
        
        # 材质列表
        for item in settings.excluded_materials:
            row = mat_box.row(align=True)
            row.prop_search(item, "material", bpy.data, "materials", text="")

        # 添加整理描边按钮
        outline_box = layout.box()
        outline_box.label(text="描边整理:", icon='OUTLINER_OB_LIGHT')
        outline_box.operator(QSEPARATOR_OT_OrganizeOutlines.bl_idname, icon='OUTLINER_COLLECTION')

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

def draw_excluded_list(self, context):
    """绘制优化后的排除列表面板"""
    layout = self.layout
    settings = context.scene.qseparator_settings
    
    row = layout.row()
    row.template_list(
        "QS_UL_ExcludedItems",
        "",
        settings,
        "excluded_items",
        settings,
        "excluded_items_index",
        rows=3
    )
    
    col = row.column(align=True)
    col.operator("qseparator.add_excluded_item", icon='ADD', text="")
    col.operator("qseparator.remove_excluded_item", icon='REMOVE', text="")
    col.operator("qseparator.clear_excluded_items", icon='X', text="")
    
    # 显示排除项统计
    if settings.excluded_items:
        layout.label(text=f"共 {len(settings.excluded_items)} 个排除项")

# ------------------------- 注册 -------------------------
classes = (
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
    QSEPARATOR_PT_MainPanel,
    QS_UL_ExcludedItems,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.qseparator_settings = bpy.props.PointerProperty(type=QSeparatorSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.qseparator_settings

if __name__ == "__main__":
    register()
