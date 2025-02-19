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

# ------------------------- 属性定义 -------------------------
class ExcludedItem(bpy.types.PropertyGroup):
    target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="排除对象",
        description="选择要排除的网格对象",
        poll=lambda self, obj: obj.type == 'MESH'
    )

class QSeparatorSettings(bpy.types.PropertyGroup):
    excluded_items: bpy.props.CollectionProperty(type=ExcludedItem)
    active_index: bpy.props.IntProperty(default=-1)
    affect_output: bpy.props.BoolProperty(
        name="应用排除列表",
        default=True,
        description="启用时排除列表会影响所有生成内容"
    )
    export_smd: bpy.props.BoolProperty(
        name="生成SMD配置",
        default=True,
        description="启用时基于集合生成SMD配置"
    )

# ------------------------- 核心逻辑 -------------------------
def generate_bodygroups(context):
    settings = context.scene.qseparator_settings
    excluded_objects = {item.target for item in settings.excluded_items if item.target} if settings.affect_output else set()
    
    config_entries = []
    
    for coll in bpy.data.collections:
        # 跳过默认集合和空集合
        if coll.name == "Collection" or not coll.objects:
            continue
        
        # 检查集合是否包含排除对象
        if settings.affect_output and any(obj in excluded_objects for obj in coll.objects):
            continue

        # 根据模式生成不同配置
        if settings.export_smd:
            # SMD模式生成
            config_entries.append(
                f'$bodygroup "{coll.name}"\n'
                '{\n'
                f'    studio "{coll.name}.smd"\n'
                '    blank\n'
                '}\n'
            )
        else:
            # GLB模式生成
            config_entries.append(
                f'$bodygroup "{coll.name}"\n'
                '{\n'
                f'    studio $custom_model$ InNode {coll.name}\n'
                '    blank\n'
                '}\n'
            )
    
    return '\n'.join(config_entries) if config_entries else "// 没有可生成的配置内容"

# ------------------------- 操作符 -------------------------
class QSEPARATOR_OT_CopyText(bpy.types.Operator):
    bl_idname = "qseparator.copy_text"
    bl_label = "复制配置文本"
    
    def execute(self, context):
        text = generate_bodygroups(context)
        context.window_manager.clipboard = text
        count = text.count('$bodygroup')
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
                obj.name = f"{mat_name}_mesh"
                
                # 创建/获取材质集合
                collection = bpy.data.collections.get(mat_name)
                if not collection:
                    collection = bpy.data.collections.new(mat_name)
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
        
        # 主操作区
        main_col = layout.column(align=True)
        main_col.operator(QSEPARATOR_OT_QuickSeparate.bl_idname, icon='MOD_EXPLODE')
        
        # 配置生成区
        config_box = layout.box()
        config_box.label(text="配置生成设置:", icon='SETTINGS')
        config_box.prop(settings, "export_smd", text="SMD模式")
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

class QSEPARATOR_OT_SelectItem(bpy.types.Operator):
    bl_idname = "qseparator.select_item"
    bl_label = "选择列表项"
    index: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.qseparator_settings.active_index = self.index
        return {'FINISHED'}

# ------------------------- 注册 -------------------------
classes = (
    ExcludedItem,
    QSeparatorSettings,
    QSEPARATOR_OT_CopyText,
    QSEPARATOR_OT_AddSearchItem,
    QSEPARATOR_OT_RemoveSearchItem,
    QSEPARATOR_OT_ClearAllItems,
    QSEPARATOR_OT_QuickSeparate,
    QSEPARATOR_PT_MainPanel,
    QSEPARATOR_OT_SelectItem,
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
