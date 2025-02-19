bl_info = {
    "name": "快速根据名称选择骨骼",
    "blender": (3, 0, 0),
    "category": "Object",
    "author": "地狱酱",
    "description": "根据关键词以及它们的大小写搜索骨骼",
}

import bpy

class BoneSelectorPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "快速根据名称选择骨骼"
    bl_idname = "OBJECT_PT_bone_selector"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "快速根据名称选择骨骼"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Input field for the keyword
        layout.prop(scene, "bone_keyword")
        # Checkbox for case sensitivity
        layout.prop(scene, "case_sensitive")
        # Select bones button
        layout.operator("object.select_bones_by_keyword", text="Select Bones")

class SelectBonesByKeywordOperator(bpy.types.Operator):
    bl_idname = "object.select_bones_by_keyword"
    bl_label = "快速根据名称选择骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        keyword = scene.bone_keyword
        case_sensitive = scene.case_sensitive

        if not keyword:
            self.report({'WARNING'}, "Keyword cannot be empty")
            return {'CANCELLED'}

        # Ensure we are in Object mode before clearing selection
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in bpy.context.object.data.bones:
            bone.select = False

        # Switch to Pose mode for selecting bones
        bpy.ops.object.mode_set(mode='POSE')

        for bone in bpy.context.object.pose.bones:
            # Compare keyword with case sensitivity option
            if (keyword in bone.name if case_sensitive else keyword.lower() in bone.name.lower()):
                bone.bone.select = True

        # Return to Pose mode
        bpy.ops.object.mode_set(mode='POSE')

        self.report({'INFO'}, "Bones selected successfully")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(BoneSelectorPanel)
    bpy.utils.register_class(SelectBonesByKeywordOperator)
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

def unregister():
    bpy.utils.unregister_class(BoneSelectorPanel)
    bpy.utils.unregister_class(SelectBonesByKeywordOperator)
    del bpy.types.Scene.bone_keyword
    del bpy.types.Scene.case_sensitive

if __name__ == "__main__":
    register()
