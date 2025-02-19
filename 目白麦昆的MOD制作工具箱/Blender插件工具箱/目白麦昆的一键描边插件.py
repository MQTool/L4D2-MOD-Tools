import bpy

bl_info = {
    "name": "一键描边",  # 插件名称
    "blender": (2, 80, 0),  # 适用于Blender 2.80及以上版本
    "category": "Object",  # 分类：对象操作
    "author": "地狱酱",
    "description": "执行特定的描边操作",
}


class OBJECT_OT_add_outline_all(bpy.types.Operator):
    """为所有模型对象添加描边"""
    bl_idname = "object.add_outline_all"
    bl_label = "快速描边"

    def execute(self, context):
        add_outline(context, -abs(context.scene.outline_size), all_objects=True)  # 将输入值转为负值
        return {'FINISHED'}


class OBJECT_OT_add_outline_selected(bpy.types.Operator):
    """为选中的模型对象添加描边"""
    bl_idname = "object.add_outline_selected"
    bl_label = "选择描边"

    def execute(self, context):
        add_outline(context, -abs(context.scene.outline_size), all_objects=False)  # 将输入值转为负值
        bpy.context.space_data.shading.show_backface_culling = True
        return {'FINISHED'}


class OBJECT_OT_delete_outline_all(bpy.types.Operator):
    """删除所有描边对象"""
    bl_idname = "object.delete_outline_all"
    bl_label = "删除所有描边"

    def execute(self, context):
        delete_outline_objects_and_collections(context)
        return {'FINISHED'}


class OBJECT_OT_copy_smd_to_clipboard(bpy.types.Operator):
    """生成 SMD 文本并复制到剪贴板"""
    bl_idname = "object.copy_smd_to_clipboard"
    bl_label = "复制描边模型文本"

    def execute(self, context):
        smd_text = copy_smd_to_clipboard(context)  # 调用复制到剪贴板的函数
        self.report({'INFO'}, "SMD 文本已复制到剪贴板")
        return {'FINISHED'}


class OutlinePanel(bpy.types.Panel):
    """在3D视图的侧边栏中创建一个面板"""
    bl_label = "一键描边"
    bl_idname = "OBJECT_PT_outline"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "一键描边"

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
        row.operator("object.add_outline_all", text="快速描边")

        # 选择描边按钮（只为选中的对象添加描边）
        row = layout.row()
        row.operator("object.add_outline_selected", text="选择描边")

        # 删除描边按钮
        row = layout.row()
        row.operator("object.delete_outline_all", text="删除所有描边")

        # 复制描边模型文本按钮
        row = layout.row()
        row.operator("object.copy_smd_to_clipboard", text="复制描边模型文本")


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
    print("SMD 文本已复制到剪贴板")


def register():
    bpy.utils.register_class(OBJECT_OT_add_outline_all)
    bpy.utils.register_class(OBJECT_OT_add_outline_selected)
    bpy.utils.register_class(OBJECT_OT_delete_outline_all)
    bpy.utils.register_class(OBJECT_OT_copy_smd_to_clipboard)
    bpy.utils.register_class(OutlinePanel)

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

    # 添加描边放置模式的属性
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

    # 添加输出全部的布尔选项
    bpy.types.Scene.include_all_models = bpy.props.BoolProperty(
        name="输出全部",
        description="是否输出原模型与描边模型，排除名称为 'Face' 和 'smd_bone_vis' 的对象",
        default=False
    )


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_add_outline_all)
    bpy.utils.unregister_class(OBJECT_OT_add_outline_selected)
    bpy.utils.unregister_class(OBJECT_OT_delete_outline_all)
    bpy.utils.unregister_class(OBJECT_OT_copy_smd_to_clipboard)
    bpy.utils.unregister_class(OutlinePanel)
    del bpy.types.Scene.outline_size
    del bpy.types.Scene.use_outline_base
    del bpy.types.Scene.use_named_materials
    del bpy.types.Scene.outline_mode  # 删除 outline_mode 属性
    del bpy.types.Scene.include_all_models  # 删除 include_all_models 属性


if __name__ == "__main__":
    register()
