import bpy
from bpy.types import Operator, Panel, Node, NodeTree

bl_info = {
    "name": "骨骼结构视图",
    "blender": (3, 6, 0),
    "category": "动画",
    "author": "地狱酱",
    "description": "以树结构显示骨骼的关系，并与姿态模式和编辑模式手动同步"
}

# 自定义 NodeTree
class BoneSchematicNodeTree(NodeTree):
    bl_idname = "BoneSchematicNodeTree"
    bl_label = "骨骼结构视图"
    bl_icon = "NODETREE"

# 自定义 Node
class BoneNode(Node):
    bl_idname = "BoneNode"
    bl_label = "骨骼节点"
    
    bone_name: bpy.props.StringProperty(name="骨骼名称", default="")
    parent_bone: bpy.props.StringProperty(name="父骨骼", default="")

    def init(self, context):
        self.outputs.new("NodeSocketString", "子节点")
        self.inputs.new("NodeSocketString", "父节点")

    def draw_buttons(self, context, layout):
        layout.label(text=f"骨骼: {self.bone_name}")
        layout.prop_search(self, "parent_bone", context.object.data, "bones", text="父骨骼")
        layout.operator("object.change_bone_parent", text="更新父级关系").bone_name = self.bone_name

# 更新父子关系的操作类
class ChangeBoneParentOperator(Operator):
    bl_idname = "object.change_bone_parent"
    bl_label = "更新骨骼父级关系"
    bl_description = "根据节点设置更新骨骼的父子关系"

    bone_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'WARNING'}, "请选中一个骨骼对象！")
            return {'CANCELLED'}

        armature = obj.data
        node_tree = bpy.data.node_groups.get("骨骼结构")
        if not node_tree:
            self.report({'WARNING'}, "未找到骨骼结构节点树！")
            return {'CANCELLED'}

        node = node_tree.nodes.get(self.bone_name)
        if not node:
            self.report({'WARNING'}, f"未找到名为 {self.bone_name} 的节点！")
            return {'CANCELLED'}

        # 获取骨骼
        bone_name = self.bone_name
        new_parent_name = node.parent_bone

        # 在姿态模式下更新父子关系
        armature = context.object.data
        bpy.ops.object.mode_set(mode='EDIT')  # 切换到编辑模式

        edit_bone = armature.edit_bones.get(bone_name)
        if not edit_bone:
            self.report({'WARNING'}, f"未找到名为 {bone_name} 的骨骼！")
            bpy.ops.object.mode_set(mode='POSE')  # 切回姿态模式
            return {'CANCELLED'}

        if new_parent_name:
            new_parent_bone = armature.edit_bones.get(new_parent_name)
            if new_parent_bone:
                edit_bone.parent = new_parent_bone
                self.report({'INFO'}, f"骨骼 {bone_name} 的父级已更改为 {new_parent_name}")
            else:
                self.report({'WARNING'}, f"未找到名为 {new_parent_name} 的父骨骼！")
        else:
            edit_bone.parent = None
            self.report({'INFO'}, f"骨骼 {bone_name} 的父级已清除")

        bpy.ops.object.mode_set(mode='POSE')  # 切回姿态模式

        # 刷新节点树，更新父子节点关系
        if node_tree:
            self.update_node_tree(node_tree)

        return {'FINISHED'}

    def update_node_tree(self, node_tree):
        # 更新节点树中的连接关系
        armature = bpy.context.object.data
        nodes = {node.bone_name: node for node in node_tree.nodes}
        
        # 删除旧的连接
        for link in node_tree.links:
            node_tree.links.remove(link)

        # 根据父子关系重新连接
        for bone in armature.bones:
            if bone.parent:
                parent_node = nodes.get(bone.parent.name)
                child_node = nodes.get(bone.name)
                if parent_node and child_node:
                    node_tree.links.new(parent_node.outputs["子节点"], child_node.inputs["父节点"])
        return {'FINISHED'}

# 同步骨骼到节点选择
class SyncBoneSelectionOperator(Operator):
    bl_idname = "object.sync_bone_selection"
    bl_label = "同步骨骼选择到节点图"

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'WARNING'}, "请在姿态模式下选择骨骼对象！")
            return {'CANCELLED'}

        armature = obj.data
        node_tree = bpy.data.node_groups.get("骨骼结构")
        if not node_tree:
            self.report({'WARNING'}, "未找到骨骼结构节点树！")
            return {'CANCELLED'}

        # 获取当前模式
        current_mode = obj.mode

        # 切换到姿态模式，以便选择骨骼
        if current_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='POSE')

        for node in node_tree.nodes:
            bone = armature.bones.get(node.bone_name)
            if bone and bone.select:
                node.select = True
                node_tree.nodes.active = node
            else:
                node.select = False

        # 如果之前在编辑模式中，切回编辑模式
        if current_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

# 同步节点到骨骼选择
class SyncNodeSelectionOperator(Operator):
    bl_idname = "object.sync_node_selection"
    bl_label = "同步节点选择到骨骼视图"

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'WARNING'}, "请在姿态模式下选择骨骼对象！")
            return {'CANCELLED'}

        armature = obj.data
        node_tree = bpy.data.node_groups.get("骨骼结构")
        if not node_tree:
            self.report({'WARNING'}, "未找到骨骼结构节点树！")
            return {'CANCELLED'}

        # 获取当前模式
        current_mode = obj.mode

        # 切换到姿态模式，以便选择骨骼
        if current_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='POSE')

        for node in node_tree.nodes:
            bone = armature.bones.get(node.bone_name)
            if bone and node.select:
                bone.select = True
            elif bone:
                bone.select = False

        # 如果之前在编辑模式中，切回编辑模式
        if current_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

# 生成骨骼图解视图
class GenerateBoneSchematicOperator(Operator):
    bl_idname = "object.generate_bone_schematic"
    bl_label = "生成骨骼结构视图"
    bl_description = "生成所选骨骼对象的结构视图"

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'WARNING'}, "请选中一个骨骼对象！")
            return {'CANCELLED'}

        armature = obj.data

        # 创建或清空 Node Tree
        if "骨骼结构" not in bpy.data.node_groups:
            tree = bpy.data.node_groups.new("骨骼结构", "BoneSchematicNodeTree")
        else:
            tree = bpy.data.node_groups["骨骼结构"]
        tree.nodes.clear()

        nodes = {}

        x_spacing = 300  # 水平间距
        y_spacing = 200  # 垂直间距

        def calculate_subtree_width(bone):
            children = [b for b in armature.bones if b.parent and b.parent.name == bone.name]
            if not children:
                return x_spacing
            return sum(calculate_subtree_width(child) for child in children) + (len(children) - 1) * x_spacing

        def layout_node(bone, x, y):
            node = tree.nodes.new("BoneNode")
            node.name = bone.name
            node.label = bone.name
            node.bone_name = bone.name
            node.parent_bone = bone.parent.name if bone.parent else ""
            node.location = (x, y)
            nodes[bone.name] = node

            children = [b for b in armature.bones if b.parent and b.parent.name == bone.name]
            if children:
                total_width = sum(calculate_subtree_width(child) for child in children) + (len(children) - 1) * x_spacing
                current_x = x - total_width / 2
                for child in children:
                    subtree_width = calculate_subtree_width(child)
                    layout_node(child, current_x + subtree_width / 2, y - y_spacing)
                    current_x += subtree_width + x_spacing

        roots = [b for b in armature.bones if b.parent is None]
        total_width = sum(calculate_subtree_width(root) for root in roots) + (len(roots) - 1) * x_spacing
        start_x = -total_width / 2
        for root in roots:
            subtree_width = calculate_subtree_width(root)
            layout_node(root, start_x + subtree_width / 2, 0)
            start_x += subtree_width + x_spacing

        for bone in armature.bones:
            if bone.parent and bone.parent.name in nodes:
                tree.links.new(nodes[bone.parent.name].outputs["子节点"], nodes[bone.name].inputs["父节点"])

        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.spaces.active.node_tree = tree
                break

        self.report({'INFO'}, "骨骼结构已生成！")
        return {'FINISHED'}

# 自定义面板
class BoneSchematicPanel3D(Panel):
    bl_label = "骨骼结构视图"
    bl_idname = "VIEW3D_PT_bone_schematic"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "骨骼结构"

    def draw(self, context):
        layout = self.layout
        layout.label(text="骨骼结构视图")
        layout.operator("object.generate_bone_schematic", text="生成骨骼结构节点图")
        layout.operator("object.sync_bone_selection", text="同步骨骼选择到节点图")
        layout.operator("object.sync_node_selection", text="同步节点选择到骨骼视图")


class BoneSchematicPanelNodeEditor(Panel):
    bl_label = "骨骼结构视图"
    bl_idname = "NODE_EDITOR_PT_bone_schematic"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "骨骼结构"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.sync_bone_selection", text="同步骨骼选择到节点图")
        layout.operator("object.sync_node_selection", text="同步节点选择到骨骼视图")


# 注册
classes = [
    BoneSchematicNodeTree,
    BoneNode,
    GenerateBoneSchematicOperator,
    ChangeBoneParentOperator,
    SyncBoneSelectionOperator,
    SyncNodeSelectionOperator,
    BoneSchematicPanel3D,
    BoneSchematicPanelNodeEditor
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()