-- SMD插件检测脚本
-- 作者: Claude
-- 用途: 检测3ds Max是否安装了SMD相关插件

fn checkSMDPlugins = (
    -- 获取Max安装路径下的Plugins文件夹
    local pluginsPath = (getDir #maxroot) + "plugins\\"
    
    -- 需要检查的插件文件列表
    local pluginFiles = #(
        "SMDImporter.dli",
        "VTAExporter.dle", 
        "SMDExporter.dle"
    )
    
    -- 存储缺失的插件
    local missingPlugins = #()
    
    -- 检查每个插件文件是否存在
    for pluginFile in pluginFiles do (
        local filePath = pluginsPath + pluginFile
        if not (doesFileExist filePath) then (
            missingPlugins[missingPlugins.count + 1] = pluginFile
        )
    )
    
    -- 返回检测结果
    return #(missingPlugins.count == 0, missingPlugins)
)

-- 在工具箱的主UI创建之前添加检测代码
global SMDPluginCheckResult = checkSMDPlugins()
if not SMDPluginCheckResult[1] then (
    -- 构建缺失插件的消息
    global SMDPluginCheckMessage = "检测到以下SMD插件缺失:\n\n"
    for pluginFile in SMDPluginCheckResult[2] do (
        SMDPluginCheckMessage += pluginFile + "\n"
    )
    SMDPluginCheckMessage += "\n工具箱需要SMD插件支持"
    
    -- 显示警告消息
    messageBox SMDPluginCheckMessage title:"插件检测失败" beep:true
    
    -- 关闭所有已打开的工具箱窗口
    try(cui.unRegisterDialogBar 你的工具箱RolloutName)catch()
    try(destroyDialog 你的工具箱RolloutName)catch()
    
    -- 清理并强制终止脚本
    clearListener()
    gc()
    execute "undefined"
)

fn BoneNameLister = 
(
    try(destroyDialog boneListerRollout)catch()

    rollout boneListerRollout "骨骼名称列表工具"
    (
        local getAllBones, getAllObjects, updateBoneList
        
        dotNetControl txtBones "System.Windows.Forms.RichTextBox" width:300 height:340 pos:[10,10]
        checkbox chkShowOthers "显示其他对象" pos:[10,360]
        button btnList "列出所有骨骼" width:140 height:30 pos:[10,390]
        button btnCopy "复制到剪贴板" width:140 height:30 pos:[160,390]
        
        fn getAllBones = 
        (
            local boneNames = #()
            for obj in objects do
            (
                if isKindOf obj BoneObj do
                (
                    append boneNames obj.name
                )
            )
            return boneNames
        )

        fn getAllObjects = 
        (
            local objNames = #()
            for obj in objects do
            (
                if not (isKindOf obj BoneObj) do
                (
                    append objNames obj.name
                )
            )
            return objNames
        )
        
        fn updateBoneList = 
        (
            local bones = getAllBones()
            local outputStr = ""
            
            if bones.count == 0 then
            (
                outputStr = "场景中未找到任何骨骼！\n"
            )
            else
            (
                outputStr = "场景中的骨骼名称：\n\n"
                for i = 1 to bones.count do
                (
                    outputStr += (i as string) + ". " + bones[i] + "\n"
                )
            )
            
            if chkShowOthers.checked then
            (
                local objects = getAllObjects()
                if objects.count > 0 then
                (
                    outputStr += "\n其他对象名称：\n\n"
                    for i = 1 to objects.count do
                    (
                        outputStr += (i as string) + ". " + objects[i] + "\n"
                    )
                )
                else
                (
                    outputStr += "\n场景中未找到其他对象！\n"
                )
            )
            
            txtBones.text = outputStr
        )
        
        on boneListerRollout open do
        (
            txtBones.multiline = true
            txtBones.wordWrap = true
            txtBones.scrollbars = txtBones.scrollbars.vertical
            txtBones.readonly = true
            txtBones.font = dotNetObject "System.Drawing.Font" "Microsoft YaHei" 10
            updateBoneList()
        )
        
        on btnList pressed do
        (
            updateBoneList()
        )
        
        on btnCopy pressed do
        (
            if txtBones.text.count > 0 then
            (
                setClipboardText txtBones.text
                messageBox "已复制到剪贴板！" title:"提示"
            )
        )
        
        on chkShowOthers changed state do
        (
            updateBoneList()
        )
    )
    
    createDialog boneListerRollout 320 450
)

global mainDialog

fn toggleMainDialogVisibility = (
    if mainDialog != undefined do (
        if mainDialog.isVisible() then (
            mainDialog.close()
        ) else (
            mainDialog.open()
        )
    )
)

global setHelpers

fn setHelpers arrayHelper caption =
(
    arrayHelper = selection as array
    messageBox (caption + " 已选择 " + arrayHelper.count as string + " 个对象")
    return arrayHelper
)

fn exportGeometryWithAllBonesAndHelpers =
(
    global eyeballTrackingObject
    global startFrame = 0
    global endFrame = 100
    global useEyeballTrackingObject = false
    global exportAnimation = false -- 控制是否导出动作的开关
    
    fn showEyeballTrackingSelection =
    (
        rollout eyeballRollout "一键导出" width:300 height:240
        (
            checkbox chk_useEyeballTrackingObject "启用眼球追踪对象" checked:useEyeballTrackingObject align:#center
            button btn_saveLoadEyeball "存取眼球追踪网格" width:180 height:30 align:#center enabled:useEyeballTrackingObject
            checkbox chk_exportAnimation "导出动作SMD" checked:exportAnimation align:#center
            spinner spn_startFrame "起始帧数" range:[0,999,0] type:#integer width:180 align:#center enabled:exportAnimation
            spinner spn_endFrame "结束帧数" range:[0,999,100] type:#integer width:180 align:#center enabled:exportAnimation
            button btn_select "确定" width:180 height:30 align:#center
    
            -- 当"启用眼球追踪对象"的勾选状态发生变化时
            on chk_useEyeballTrackingObject changed state do
            (
                useEyeballTrackingObject = state
                btn_saveLoadEyeball.enabled = state  -- 控制按钮可用状态
            )
    
            -- 当"导出动作SMD"的勾选状态发生变化时，启用或禁用帧数设置
            on chk_exportAnimation changed state do
            (
                exportAnimation = state
                spn_startFrame.enabled = state
                spn_endFrame.enabled = state
            )
    
            -- 起始帧数变化时更新全局变量
            on spn_startFrame changed val do
            (
                startFrame = val
            )
            
            -- 结束帧数变化时更新全局变量
            on spn_endFrame changed val do
            (
                endFrame = val
            )
    
            -- 当点击"存取眼球追踪网格"时，处理对象选择
            on btn_saveLoadEyeball pressed do
            (
                if selection.count == 1 and (isKindOf selection[1] Editable_Mesh or isKindOf selection[1] Editable_Poly) then
                (
                    eyeballTrackingObject = selection[1]
                    messageBox ("已存取眼球追踪对象: " + eyeballTrackingObject.name) title:"存取成功"
                )
                else
                (
                    messageBox "请选择一个可编辑网格对象。" title:"错误"
                )
            )
    
            -- 当点击"确定"时的逻辑
            on btn_select pressed do
            (
                if useEyeballTrackingObject and eyeballTrackingObject == undefined then
                (
                    messageBox "请先存取一个眼球追踪对象。" title:"提示"
                )
                else
                (
                    destroyDialog eyeballRollout
                    exportGeometryWithAllBonesAndHelpers()
                )
            )
        )
        createdialog eyeballRollout
    )
    
    fn exportGeometryWithAllBonesAndHelpers =
    (
        local exportPath = getSavePath caption:"选择导出路径"
        if exportPath != undefined then
        (
            local exportList = "" -- 初始化exportList变量
            local allGeometries = for obj in geometry where 
            (
                -- 检查是否为可编辑网格/多边形或具有相应修改器
                isKindOf obj Editable_Mesh or 
                isKindOf obj Editable_Poly or
                (obj.modifiers.count > 0 and 
                    (
                        -- 检查是否有蒙皮修改器
                        local hasSkin = (for m in obj.modifiers where classOf m == Skin collect m).count > 0
                        -- 检查是否有编辑类修改器或本身就是可编辑类型
                        local hasEditMod = (for m in obj.modifiers where (classOf m == Edit_Mesh or classOf m == Edit_Poly) collect m).count > 0
                        hasSkin or hasEditMod
                    )
                )
            ) collect obj
            local allBonesAndHelpers = for obj in objects where (isKindOf obj Helper) or (classOf obj == BoneGeometry) collect obj
    
            -- 获取场景中任意模型的名称并立即添加到exportList
            local randomModel = if allGeometries.count > 0 then allGeometries[1].name else "default_model"
            exportList = "$DefineVariable custom_model \"" + randomModel + ".smd\"\n" + exportList
    
            -- 导出所有几何体和辅助对象
            for geo in allGeometries do
            (
                if not useEyeballTrackingObject or geo != eyeballTrackingObject then
                (
                    clearSelection()
                    select geo
                    selectMore allBonesAndHelpers
    
                    -- 如果是head或face，将眼球追踪对象一起选择
                    local isHeadOrFace = matchPattern geo.name pattern:"head" ignoreCase:true or matchPattern geo.name pattern:"face" ignoreCase:true
                    if isHeadOrFace then
                    (
                        if useEyeballTrackingObject and eyeballTrackingObject != undefined do selectMore eyeballTrackingObject
                    )
    
                    local filename = exportPath + "\\" + geo.name + ".smd"
                    local exportResult = WBSMDExport filename true 0 false 1 0 0 false false false false
    
                    -- 只有非head/face的对象才添加到exportList中
                    if exportResult == "OK" and not isHeadOrFace then
                    (
                        exportList += "$body " + geo.name + " \"" + geo.name + ".smd\"\n"
                    )
                    else if exportResult != "OK" and not isHeadOrFace then
                    (
                        exportList += "导出失败: " + geo.name + "\n错误信息: " + exportResult + "\n"
                    )
                )
            )
    
            -- 如果勾选了导出动画，才导出动作SMD
            if exportAnimation then
            (
                clearSelection()
                select allGeometries
    
                local filename = exportPath + "\\pps.smd"
                local exportResult = WBSMDExport filename true 1 false 1 startFrame endFrame false false false false
    
                if exportResult != "OK" then
                (
                    exportList += "导出失败: animation\n错误信息: " + exportResult + "\n"
                )
            )
    
            -- 显示导出结果
            if exportList != "" then
            (
                rollout exportRollout "导出列表" width:500 height:300
                (
                    edittext edt_exportList "导出列表:" width:480 height:260 multiline:true readOnly:true
                    button btn_close "关闭" width:60 height:20 align:#right
                    on btn_close pressed do
                    (
                        destroyDialog exportRollout
                    )
                )
                createdialog exportRollout
                exportRollout.edt_exportList.text = exportList
            )
            else
            (
                messagebox "没有找到可导出的几何体。"
            )
        )
        else
        (
            messagebox "导出被取消。"
        )
    )
    
    showEyeballTrackingSelection()
     
)

fn TPosePresetManager = 
(
    try(destroyDialog TPosePresetRollout) catch()
    
    global TPosePresetRollout
    global presetFilePath = ((getDir #userScripts) + "\\TPosePresets.ini")
    
    rollout TPosePresetRollout "T-Pose预设管理器" width:300
    (
        dropdownList ddlPresets "预设列表:" items:#() width:280
        editText edtNewPreset "新预设名称:" text:"" width:280
        
        group "操作"
        (
            button btnSetTargets "设置目标对象" width:135
            button btnApply "应用预设" width:135
            button btnSave "保存预设" width:135
            button btnDelete "删除预设" width:135
        )
        
        local targetObjects = #()
        
        -- 预设管理函数
        fn savePreset presetName targets =
        (
            local str = ""
            for t in targets do
            (
                str += t[1] + "," + t[2] as string + "," + t[3] as string + "," + t[4] as string + ";"
            )
            setINISetting presetFilePath presetName "Targets" str
        )

        fn loadPreset presetName =
        (
            local targets = #()
            local targetsStr = getINISetting presetFilePath presetName "Targets"
            local pairs = filterString targetsStr ";"
            for p in pairs where p.count > 0 do
            (
                local data = filterString p ","
                if data.count == 4 do
                (
                    append targets #(data[1], data[2] as float, data[3] as float, data[4] as float)
                )
            )
            targets
        )

        fn getAllPresets =
        (
            local presets = #()
            if doesFileExist presetFilePath then
            (
                local sections = getINISetting presetFilePath
                for s in sections do append presets s
            )
            presets
        )

        fn refreshPresetList =
        (
            ddlPresets.items = getAllPresets()
        )
        
        fn rotateTargetObjects targets =
        (
            for obj in objects do
            (
                for target in targets do
                (
                    if obj.name == target[1] do
                    (
                        local pos = obj.position
                        local scale = obj.scale
                        obj.rotation = eulerAngles target[2] target[3] target[4]
                        obj.position = pos
                        obj.scale = scale
                        format "已旋转对象: %\n" obj.name
                    )
                )
            )
        )
        
        on TPosePresetRollout open do
        (
            refreshPresetList()
        )
        
        on btnSetTargets pressed do
        (
            targetObjects = #()
            local sel = getCurrentSelection()
            if sel.count > 0 then
            (
                for obj in sel do
                (
                    local rot = obj.rotation as eulerAngles
                    append targetObjects #(obj.name, rot.x, rot.y, rot.z)
                )
                messageBox ("已设置" + sel.count as string + "个目标对象") title:"成功"
            )
            else
                messageBox "请先选择目标对象!" title:"错误"
        )
        
        on btnApply pressed do
        (
            if ddlPresets.selected != undefined do
            (
                local presetData = loadPreset ddlPresets.selected
                if presetData.count > 0 then
                (
                    rotateTargetObjects presetData
                    messageBox ("已应用预设: " + ddlPresets.selected) title:"成功"
                )
                else
                    messageBox "预设数据无效!" title:"错误"
            )
        )
        
        on btnSave pressed do
        (
            local newName = edtNewPreset.text
            if newName.count > 0 then
            (
                if targetObjects.count > 0 then
                (
                    savePreset newName targetObjects
                    refreshPresetList()
                    messageBox ("已保存预设: " + newName) title:"成功"
                )
                else
                    messageBox "请先设置目标对象!" title:"错误"
            )
            else
                messageBox "请输入预设名称!" title:"错误"
        )
        
        on btnDelete pressed do
        (
            if ddlPresets.selected != undefined do
            (
                local selectedPreset = ddlPresets.selected  -- 保存要删除的预设名称
                delINISetting presetFilePath selectedPreset
                refreshPresetList()
                messageBox ("已删除预设: " + selectedPreset) title:"成功"
            )
        )
    )
    
    createDialog TPosePresetRollout
)

fn vrdActionScript = (
    try (destroyDialog vrdScriptDialog) catch()

    global frontHelpers = #()
    global sideHelpers = #()
    global backHelpers = #()
    global wristHelpers = #()
    
    fn setHelpers arrayHelper caption =
    (
        arrayHelper = selection as array
        messageBox (caption + " 已选择 " + arrayHelper.count as string + " 个对象")
        return arrayHelper
    )
    
    global generateOutputText
    
    fn generateOutputText cancel40Frame cancelSkirtVRD =
    (
        local outputText = ""
        local boneNames = #("ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_R_Thigh", "ValveBiped.Bip01_L_Hand", "ValveBiped.Bip01_R_Hand")
    
        for i = 1 to boneNames.count do
        (
            -- 如果取消裙子VRD，跳过腿部骨骼
            if cancelSkirtVRD and (boneNames[i] == "ValveBiped.Bip01_L_Thigh" or boneNames[i] == "ValveBiped.Bip01_R_Thigh") then
            (
                continue
            )
    
            outputText += "$NekoDriverBone \"" + boneNames[i] + "\" {\n"
            outputText += "\tpose \"VRD.smd\"\n"
    
            -- 左腿骨骼的特殊处理
            if boneNames[i] == "ValveBiped.Bip01_L_Thigh" and not cancel40Frame then
            (
                outputText += "\t  trigger 90 0\n"
                outputText += "\t  trigger 45 10\n" -- 第10帧的触发值为45
                outputText += "\t  trigger 90 20\n"
                outputText += "\t  trigger 90 30\n"
                outputText += "\t  trigger 25 40\n" -- 第40帧的触发值为25
            )
            else -- 其他骨骼的文本生成
            (
                outputText += "\t  trigger 90 0\n"
                outputText += "\t  trigger 90 10\n"
                outputText += "\t  trigger 90 20\n"
                if i <= 2 then
                (
                    outputText += "\t  trigger 90 30\n"
                )
            )
    
            local uniqueHelpers = #()
            for helper in (if i > 2 then wristHelpers else (frontHelpers + sideHelpers + backHelpers)) do
            (
                -- 判断骨骼是左侧还是右侧
                local isLeftBone = (findString boneNames[i] "_L") != undefined
                local isRightBone = (findString boneNames[i] "_R") != undefined
    
                -- 判断辅助对象是左侧还是右侧
                if helper.position.x > 0 and isLeftBone then
                (
                    appendIfUnique uniqueHelpers helper
                )
                else if helper.position.x < 0 and isRightBone then
                (
                    appendIfUnique uniqueHelpers helper
                )
            )
    
            for helper in uniqueHelpers do
            (
                outputText += "\t  " + helper.name + "\n"
            )
    
            outputText += "}\n\n"
        )
        
        return outputText
    )
    
    rollout vrdScriptDialog "一键VRD动作脚本"
    (
        -- 添加输入框
        spinner spnFront "前辅助对象旋转角度：" range:[-180, 180, 65] type:#integer
        spinner spnSide "侧辅助对象旋转角度：" range:[-180, 180, 75] type:#integer
        spinner spnBack "后辅助对象旋转角度：" range:[-180, 180, 60] type:#integer
        spinner spnWrist "手腕辅助对象旋转角度：" range:[-180, 180, 75] type:#integer -- 新的旋转角度输入框
        spinner spnFrontLeft40 "[深蹲防穿模][实验]：" range:[-180, 180, 120] type:#integer -- 新增输入框
    
        checkbox chkCancel40Frame "取消深蹲防穿模动作"
        checkbox chkCancelSkirtVRD "取消裙子VRD"
    
        button btnSelectFront "拾取前辅助对象" width:200 align:#center
        button btnSelectSide "拾取侧边辅助对象" width:200 align:#center
        button btnSelectBack "拾取后辅助对象" width:200 align:#center
        button btnSelectWrist "拾取手腕辅助对象" width:200 align:#center -- 新按钮
        button btnExecute "执行" width:200 align:#center
        button btnGenerateOutput "生成输出文本" width:200 align:#center -- 新按钮
        button btnExport "导出SMD" width:200 align:#center -- 导出按钮
    
        editText edtOutput "" width:280 height:150 readOnly:true -- 文本显示框
    
        -- 当勾选“取消裙子VRD”时，强制勾选并禁用“取消第40帧动作”以及前中后辅助对象角度输入框和拾取按钮
        on chkCancelSkirtVRD changed state do
        (
            if state then
            (
                chkCancel40Frame.checked = true
                chkCancel40Frame.enabled = false -- 禁用“取消第40帧动作”
                spnFront.enabled = false -- 禁用前辅助对象旋转角度
                spnSide.enabled = false -- 禁用侧辅助对象旋转角度
                spnBack.enabled = false -- 禁用后辅助对象旋转角度
                spnFrontLeft40.enabled = false -- 禁用“[深蹲防穿模][实验]”旋转角度
                btnSelectFront.enabled = false -- 禁用“拾取前辅助对象”按钮
                btnSelectSide.enabled = false -- 禁用“拾取侧边辅助对象”按钮
                btnSelectBack.enabled = false -- 禁用“拾取后辅助对象”按钮
            )
            else
            (
                chkCancel40Frame.enabled = true -- 启用“取消第40帧动作”
                spnFront.enabled = true -- 启用前辅助对象旋转角度
                spnSide.enabled = true -- 启用侧辅助对象旋转角度
                spnBack.enabled = true -- 启用后辅助对象旋转角度
                btnSelectFront.enabled = true -- 启用“拾取前辅助对象”按钮
                btnSelectSide.enabled = true -- 启用“拾取侧边辅助对象”按钮
                btnSelectBack.enabled = true -- 启用“拾取后辅助对象”按钮
                if not chkCancel40Frame.checked then spnFrontLeft40.enabled = true -- 启用“[深蹲防穿模][实验]”旋转角度
            )
        )
    
        -- 当勾选“取消第40帧动作”时，使“[深蹲防穿模][实验]”变灰无法使用
        on chkCancel40Frame changed state do
        (
            if state then
            (
                spnFrontLeft40.enabled = false -- 禁用“[深蹲防穿模][实验]”旋转角度
            )
            else if not chkCancelSkirtVRD.checked then
            (
                spnFrontLeft40.enabled = true -- 启用“[深蹲防穿模][实验]”旋转角度
            )
        )
    
        on btnSelectFront pressed do
        (
            frontHelpers = setHelpers frontHelpers "前辅助对象"
        )
    
        on btnSelectSide pressed do
        (
            sideHelpers = setHelpers sideHelpers "侧边辅助对象"
        )
    
        on btnSelectBack pressed do
        (
            backHelpers = setHelpers backHelpers "后辅助对象"
        )
    
        on btnSelectWrist pressed do -- 新按钮的事件处理
        (
            wristHelpers = setHelpers wristHelpers "手腕辅助对象"
        )
    
        on btnExecute pressed do
        (
            local thighBones = #("ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_R_Thigh")
            local handBones = #("ValveBiped.Bip01_L_Hand", "ValveBiped.Bip01_R_Hand")
            
            -- 获取输入的旋转角度
            local frontAngle = -spnFront.value -- 前辅助对象旋转角度加负号
            local sideAngle = spnSide.value
            local backAngle = spnBack.value
            local wristAngle = spnWrist.value
            local frontLeftAngle40 = spnFrontLeft40.value -- 获取前左辅助对象第40帧旋转角度
    
            -- 获取复选框状态
            local cancel40Frame = chkCancel40Frame.checked
            local cancelSkirtVRD = chkCancelSkirtVRD.checked
    
            -- 开始动画模式
            animate on
            (
                -- 始终在第0、10、20帧为手腕骨骼和手腕辅助对象创建空关键帧和旋转关键帧
                for frame in #(0, 10, 20) do
                (
                    sliderTime = frame
                    for obj in wristHelpers do
                    (
                        obj.rotation.controller = Euler_XYZ()
                        addNewKey obj.rotation.controller frame
                    )
                    for boneName in handBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            obj.rotation.controller = Euler_XYZ()
                            addNewKey obj.rotation.controller frame
                        )
                    )
                )
    
                -- 第10帧手腕旋转
                sliderTime = 10
                for obj in wristHelpers do
                (
                    rotate obj (angleaxis wristAngle [1, 0, 0])
                    addNewKey obj.rotation.controller 10
                )
                for boneName in handBones do
                (
                    local obj = getNodeByName boneName
                    if obj != undefined do
                    (
                        if boneName == "ValveBiped.Bip01_L_Hand" then
                            in coordsys local rotate obj (eulerAngles 90 0 0)
                        else if boneName == "ValveBiped.Bip01_R_Hand" then
                            in coordsys local rotate obj (eulerAngles -90 0 0)
                        addNewKey obj.rotation.controller 10
                    )
                )
    
                -- 第20帧手腕旋转
                sliderTime = 20
                for obj in wristHelpers do
                (
                    rotate obj (angleaxis (-wristAngle) [1, 0, 0])
                    addNewKey obj.rotation.controller 20
                )
                for boneName in handBones do
                (
                    local obj = getNodeByName boneName
                    if obj != undefined do
                    (
                        if boneName == "ValveBiped.Bip01_L_Hand" then
                            in coordsys local rotate obj (eulerAngles -90 0 0)
                        else if boneName == "ValveBiped.Bip01_R_Hand" then
                            in coordsys local rotate obj (eulerAngles 90 0 0)
                        addNewKey obj.rotation.controller 10
                    )
                )
    
                -- 根据选项条件创建前中后辅助对象和腿部骨骼的关键帧
                if cancelSkirtVRD then
                (
                    -- 取消裙子VRD时，不创建前中后辅助对象和腿部骨骼的关键帧
                    return()
                )
                else if cancel40Frame then
                (
                    -- 取消第40帧动作时，在第0、10、20、30帧创建空关键帧，在第10、20、30帧创建旋转关键帧
                    for frame in #(0, 10, 20, 30) do
                    (
                        sliderTime = frame
                        for obj in (frontHelpers + sideHelpers + backHelpers) do
                        (
                            obj.rotation.controller = Euler_XYZ()
                            addNewKey obj.rotation.controller frame
                        )
                        for boneName in thighBones do
                        (
                            local obj = getNodeByName boneName
                            if obj != undefined do
                            (
                                obj.rotation.controller = Euler_XYZ()
                                addNewKey obj.rotation.controller frame
                            )
                        )
                    )
    
                    -- 第10帧前辅助对象和腿部旋转
                    sliderTime = 10
                    for obj in frontHelpers do
                    (
                        rotate obj (angleaxis frontAngle [1, 0, 0])
                        addNewKey obj.rotation.controller 10
                    )
                    for boneName in thighBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            in coordsys local rotate obj (eulerAngles 0 0 -90)
                            addNewKey obj.rotation.controller 10
                        )
                    )
    
                    -- 第20帧侧辅助对象和腿部旋转
                    sliderTime = 20
                    for obj in sideHelpers do
                    (
                        if obj.position.x > 0 then
                            rotate obj (angleaxis frontAngle [0, 1, 0])
                        else
                            rotate obj (angleaxis -frontAngle [0, 1, 0])
                        addNewKey obj.rotation.controller 20
                    )
                    for boneName in thighBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            if boneName == "ValveBiped.Bip01_L_Thigh" then
                                in coordsys local rotate obj (eulerAngles 0 -90 0)
                            else if boneName == "ValveBiped.Bip01_R_Thigh" then
                                in coordsys local rotate obj (eulerAngles 0 90 0)
                            addNewKey obj.rotation.controller 20
                        )
                    )
    
                    -- 第30帧后辅助对象和腿部旋转
                    sliderTime = 30
                    for obj in backHelpers do
                    (
                        rotate obj (angleaxis backAngle [1, 0, 0])
                        addNewKey obj.rotation.controller 30
                    )
                    for boneName in thighBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            in coordsys local rotate obj (eulerAngles 0 0 90)
                            addNewKey obj.rotation.controller 30
                        )
                    )
                )
                else
                (
                    -- 没有取消任何选项时，在第0、10、20、30帧创建空关键帧和旋转关键帧
                    for frame in #(0, 10, 20, 30, 40) do
                    (
                        sliderTime = frame
                        for obj in (frontHelpers + sideHelpers + backHelpers) do
                        (
                            obj.rotation.controller = Euler_XYZ()
                            addNewKey obj.rotation.controller frame
                        )
                        for boneName in thighBones do
                        (
                            local obj = getNodeByName boneName
                            if obj != undefined do
                            (
                                obj.rotation.controller = Euler_XYZ()
                                addNewKey obj.rotation.controller frame
                            )
                        )
                    )
    
                    -- 第40帧左腿和前左辅助对象空关键帧和旋转关键帧
                    for frame in #(40) do
                    (
                        sliderTime = frame
                        for obj in frontHelpers where obj.position.x > 0 do
                        (
                            obj.rotation.controller = Euler_XYZ()
                            addNewKey obj.rotation.controller frame
                        )
                        local leftThigh = getNodeByName "ValveBiped.Bip01_L_Thigh"
                        if leftThigh != undefined do
                        (
                            leftThigh.rotation.controller = Euler_XYZ()
                            addNewKey leftThigh.rotation.controller frame
                        )
                    )
    
                    -- 第10帧前辅助对象和腿部旋转
                    sliderTime = 10
                    for obj in frontHelpers do
                    (
                        rotate obj (angleaxis frontAngle [1, 0, 0])
                        addNewKey obj.rotation.controller 10
                    )
                    for boneName in thighBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            in coordsys local rotate obj (eulerAngles 0 0 -90)
                            addNewKey obj.rotation.controller 10
                        )
                    )
    
                    -- 第20帧侧辅助对象和腿部旋转
                    sliderTime = 20
                    for obj in sideHelpers do
                    (
                        if obj.position.x > 0 then
                            rotate obj (angleaxis frontAngle [0, 1, 0])
                        else
                            rotate obj (angleaxis -frontAngle [0, 1, 0])
                        addNewKey obj.rotation.controller 20
                    )
                    for boneName in thighBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            if boneName == "ValveBiped.Bip01_L_Thigh" then
                                in coordsys local rotate obj (eulerAngles 0 -90 0)
                            else if boneName == "ValveBiped.Bip01_R_Thigh" then
                                in coordsys local rotate obj (eulerAngles 0 90 0)
                            addNewKey obj.rotation.controller 20
                        )
                    )
    
                    -- 第30帧后辅助对象和腿部旋转
                    sliderTime = 30
                    for obj in backHelpers do
                    (
                        rotate obj (angleaxis backAngle [1, 0, 0])
                        addNewKey obj.rotation.controller 30
                    )
                    for boneName in thighBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            in coordsys local rotate obj (eulerAngles 0 0 90)
                            addNewKey obj.rotation.controller 30
                        )
                    )
    
                    -- 第40帧左腿和前左辅助对象旋转
                    sliderTime = 40
                    local leftThigh = getNodeByName "ValveBiped.Bip01_L_Thigh"
                    if leftThigh != undefined do
                    (
                        in coordsys local rotate leftThigh (eulerAngles 0 0 -120)
                        addNewKey leftThigh.rotation.controller 40
                    )
                    for obj in frontHelpers where obj.position.x > 0 do
                    (
                        rotate obj (angleaxis frontLeftAngle40 [-1, 0, 0])
                        addNewKey obj.rotation.controller 40
                    )
                )
            )
            
            messageBox "已为辅助对象和骨骼创建关键帧，并在各帧进行了相应的旋转。" title:"操作完成"
        )
        
        on btnGenerateOutput pressed do
        (
            local cancel40Frame = chkCancel40Frame.checked
            local cancelSkirtVRD = chkCancelSkirtVRD.checked
    
            local outputText = generateOutputText cancel40Frame cancelSkirtVRD
            edtOutput.text = outputText
        )
        
        on btnExport pressed do -- 新增的导出功能按钮事件
        (
            local exportPath = getSaveFileName caption:"选择导出路径" types:"SMD(*.smd)|*.smd|所有文件(*.*)|*.*"
            if exportPath != undefined do
            (
                local cancel40Frame = chkCancel40Frame.checked
                local cancelSkirtVRD = chkCancelSkirtVRD.checked
                local maxFrame = if cancelSkirtVRD then 20 else (if cancel40Frame then 30 else 40)
                local result = WBSMDExport exportPath false 1 false 1 0 maxFrame false false false false
                if result == "OK" then
                    messageBox "导出成功！" title:"导出完成"
                else
                    messageBox ("导出失败：" + result) title:"导出错误"
            )
        )
    )
    
    createDialog vrdScriptDialog 300 700
      
)

fn toggleSkinDeform = (
    for obj in objects do (
        if (classof obj.modifiers[#Skin] == Skin) then (
            obj.modifiers[#Skin].always_deform = not obj.modifiers[#Skin].always_deform
        )
    )
    
)

fn setMorpherKeyframes = (
    (
        -- 设置要操作的模型名称
        local modelName = "Face"
        local totalFrames = 27  -- 设置总帧数
    
        -- 定义每帧要设置的变形器通道及其值，包括多个可能的通道名称和不同的值
        local frameSettings = #(
            #(1, #(#("ウィンク２右", 100), #("Placeholders", 50))),
            #(2, #(#("びっくり右", 100), #("Placeholders", 100))),
            #(3, #(#("ウィンク２", 100), #("Placeholders", 100))),
            #(4, #(#("びっくり左", 100), #("Placeholders", 100))),
            #(5, #(#("困る", 100), #("Placeholders", 100))),
            #(6, #(#("怒り", 100), #("Placeholders", 100))),
            #(7, #(#("下", 100), #("Placeholders", 100))),
            #(8, #(#("上", 100), #("Placeholders", 100))),
            #(9, #(#("口角上げ", 33), #("Placeholders", 33))),
            #(10, #(#("口角上げ", 66), #("Placeholders", 66))),
            #(11, #(#("あ２", 100), #("Placeholders", 100))),
            #(12, #(#("口角下げ", 50), #("Placeholders", 50))),
            #(13, #(#("口角下げ", 100), #("Placeholders", 100))),
            #(14, #(#("口角上げ", 100), #("Placeholders", 100))),
            #(15, #(#("あ２", 50), #("Placeholders", 50))),
            #(16, #(#("え２", 100), #("歯無し", 100))),
            #(17, #(#("う", 50), #("Placeholders", 50))),
            #(18, #(#("口横広げ", 100), #("Placeholders", 100))),
            #(19, #(#("う", 100), #("Placeholders", 100))),
            #(21, #(#("お", 100), #("Placeholders", 100))),
            #(25, #(#("あ２", 100), #("Placeholders", 100))),
            #(26, #(#("あ３", 100), #("Placeholders", 100)))
        )
    
        -- 定义需要空关键帧的帧
        local emptyFrames = #(0, 20, 22, 23, 24, 27)
        
        -- 定义屏蔽词列表
        local blockedKeywords = #("歯")
    
        -- 检查通道名是否包含屏蔽词
        fn isBlockedChannel channelName blockedKeywords =
        (
            for keyword in blockedKeywords do
            (
                if matchPattern channelName pattern:("*" + keyword + "*") then
                    return true
            )
            return false
        )
    
        -- 查找名为 "Face" 的对象
        local faceObject = getNodeByName modelName
    
        if faceObject != undefined then
        (
            -- 检查对象是否为可编辑网格
            if isKindOf faceObject Editable_mesh then
            (
                -- 选择该对象
                select faceObject
                format "对象 '%' 已选择。\n" modelName
                
                -- 遍历对象的修改器
                local modifierFound = false
                for mod in faceObject.modifiers do
                (
                    -- 检查是否为 Morpher 修改器
                    if isKindOf mod Morpher then
                    (
                        -- 选择该修改器
                        max modify mode
                        modPanel.setCurrentObject mod
                        modifierFound = true
                        format "修改器 'Morpher' 已选择。\n"
    
                        -- 记录带有屏蔽词的通道
                        local blockedChannels = #()
                        for j = 1 to mod.NumSubs do
                        (
                            local subAnimName = getSubAnimName mod j
                            for keyword in blockedKeywords do
                            (
                                if matchPattern subAnimName pattern:("*" + keyword + "*") then
                                (
                                    append blockedChannels subAnimName
                                    format "通道 '%' 被屏蔽。\n" subAnimName
                                    exit
                                )
                            )
                        )
    
                        -- 打开自动关键点
                        animate on
                        (
                            -- 存储多字通道的名称
                            local multiCharChannels = #()
    
                            -- 依次设置每一帧的多字通道（屏蔽词除外）
                            for i = 1 to frameSettings.count do
                            (
                                local frame = frameSettings[i][1]
                                local channels = frameSettings[i][2]
    
                                -- 设置当前帧
                                sliderTime = frame
    
                                -- 清零所有通道值
                                for j = 1 to mod.NumSubs do
                                (
                                    WM3_MC_SetValue mod j 0.0
                                )
    
                                -- 遍历每个通道数据以设置多字通道的值
                                for k = 1 to channels.count do
                                (
                                    local channelData = channels[k]
                                    local channelName = channelData[1]
                                    local value = channelData[2] as float
    
                                    -- 检查通道名的长度以决定是多字还是单字
                                    if channelName.count > 1 then
                                    (
                                        -- 处理多字通道
                                        local channelSet = false
                                        for j = 1 to mod.NumSubs while not channelSet do
                                        (
                                            local subAnimName = getSubAnimName mod j
                                            if matchPattern subAnimName pattern:("*" + channelName + "*") then
                                            (
                                                if findItem blockedChannels subAnimName == 0 then
                                                (
                                                    -- 设置通道值
                                                    WM3_MC_SetValue mod j value
                                                    append multiCharChannels subAnimName
                                                    format "在帧 % 设置多字通道 '%' 的值为 %。\n" frame channelName value
                                                    channelSet = true
                                                )
                                            )
                                        )
                                    )
                                )
                            )
    
                            -- 依次设置每一帧的单字通道（屏蔽词除外）
                            for i = 1 to frameSettings.count do
                            (
                                local frame = frameSettings[i][1]
                                local channels = frameSettings[i][2]
    
                                -- 设置当前帧
                                sliderTime = frame
    
                                -- 遍历每个通道数据以设置单字通道的值
                                for k = 1 to channels.count do
                                (
                                    local channelData = channels[k]
                                    local channelName = channelData[1]
                                    local value = channelData[2] as float
    
                                    -- 检查通道名的长度以决定是多字还是单字
                                    if channelName.count == 1 then
                                    (
                                        -- 处理单字通道
                                        local channelSet = false
                                        for j = 1 to mod.NumSubs while not channelSet do
                                        (
                                            local subAnimName = getSubAnimName mod j
                                            if matchPattern subAnimName pattern:("*" + channelName + "*") then
                                            (
                                                if findItem blockedChannels subAnimName == 0 and findItem multiCharChannels subAnimName == 0 then
                                                (
                                                    -- 设置通道值
                                                    WM3_MC_SetValue mod j value
                                                    format "在帧 % 设置单字通道 '%' 的值为 %。\n" frame channelName value
                                                    channelSet = true
                                                )
                                            )
                                        )
                                    )
                                )
                            )
    
                            -- 设置空关键帧
                            for k = 1 to emptyFrames.count do
                            (
                                local frame = emptyFrames[k]
    
                                -- 设置当前帧
                                sliderTime = frame
    
                                -- 清零所有通道值
                                for j = 1 to mod.NumSubs do
                                (
                                    WM3_MC_SetValue mod j 0.0
                                )
                                format "在帧 % 创建了空关键帧。\n" frame
                            )
                        )
    
                        -- 重新设置屏蔽词通道
                        for i = 1 to frameSettings.count do
                        (
                            local frame = frameSettings[i][1]
                            local channels = frameSettings[i][2]
    
                            -- 设置当前帧
                            sliderTime = frame
    
                            -- 遍历每个通道数据以设置屏蔽词通道的值
                            for k = 1 to channels.count do
                            (
                                local channelData = channels[k]
                                local channelName = channelData[1]
                                local value = channelData[2] as float
    
                                if isBlockedChannel channelName blockedKeywords do
                                (
                                    -- 处理屏蔽词通道
                                    local channelSet = false
                                    for j = 1 to mod.NumSubs while not channelSet do
                                    (
                                        local subAnimName = getSubAnimName mod j
                                        if matchPattern subAnimName pattern:("*" + channelName + "*") then
                                        (
                                            -- 设置通道值
                                            WM3_MC_SetValue mod j value
                                            format "在帧 % 设置屏蔽词通道 '%' 的值为 %。\n" frame channelName value
                                            channelSet = true
                                        )
                                    )
                                )
                            )
                        )
    
                        -- 关闭自动关键点
                        animate off
                        format "所有帧的设置已完成。\n"
    
                        exit -- 退出循环
                    )
                )
    
                if not modifierFound then
                (
                    format "对象 '%' 没有找到 Morpher 修改器。\n" modelName
                )
            )
            else
            (
                format "对象 '%' 存在，但不是可编辑网格。\n" modelName
            )
        )
        else
        (
            format "对象 '%' 不存在。\n" modelName
        )
    )
    
)

fn createSkirtHelperDialog = (
    try(destroyDialog SkirtHelperDialog) catch()

    global SkirtHelperDialog
    rollout SkirtHelperDialog "一键嫁接" width:200
    (
        checkbox chkUmaMode "赛马娘模式" width:180
        button btnSelectSkirtHelpers "存取辅助对象" width:180
        button btnExecute "执行" width:180
    
        local skirtHelpers = #()
        local originalHiddenState = #()
        
        -- 定义两种模式的连接数组
        local normalConnections = #(
            #("Right toe", "ValveBiped.Bip01_R_Toe0"),
            #("Right_ankle", "ValveBiped.Bip01_R_Foot"),
            #("Right knee", "ValveBiped.Bip01_R_Calf"),
            #("Right leg", "ValveBiped.Bip01_R_Thigh"),
            #("Left toe", "ValveBiped.Bip01_L_Toe0"),
            #("Left_ankle", "ValveBiped.Bip01_L_Foot"),
            #("Left knee", "ValveBiped.Bip01_L_Calf"),
            #("Left leg", "ValveBiped.Bip01_L_Thigh"),
            #("RingFinger3_R", "ValveBiped.Bip01_R_Finger32"),
            #("RingFinger2_R", "ValveBiped.Bip01_R_Finger31"),
            #("RingFinger1_R", "ValveBiped.Bip01_R_Finger3"),
            #("LittleFinger3_R", "ValveBiped.Bip01_R_Finger42"),
            #("LittleFinger2_R", "ValveBiped.Bip01_R_Finger41"),
            #("LittleFinger1_R", "ValveBiped.Bip01_R_Finger4"),
            #("IndexFinger3_R", "ValveBiped.Bip01_R_Finger12"),
            #("IndexFinger2_R", "ValveBiped.Bip01_R_Finger11"),
            #("IndexFinger1_R", "ValveBiped.Bip01_R_Finger1"),
            #("MiddleFinger3_R", "ValveBiped.Bip01_R_Finger22"),
            #("MiddleFinger2_R", "ValveBiped.Bip01_R_Finger21"),
            #("MiddleFinger1_R", "ValveBiped.Bip01_R_Finger2"),
            #("Thumb2_R", "ValveBiped.Bip01_R_Finger02"),
            #("Thumb1_R", "ValveBiped.Bip01_R_Finger01"),
            #("Thumb0_R", "ValveBiped.Bip01_R_Finger0"),
            #("Right wrist", "ValveBiped.Bip01_R_Hand"),
            #("Right_elbow", "ValveBiped.Bip01_R_Forearm"),
            #("ZHandTwist_R", "ValveBiped.Bip01_R_Forearm"),
            #("Right arm", "ValveBiped.Bip01_R_UpperArm"),
            #("Right shoulder", "ValveBiped.Bip01_R_Clavicle"),
            #("Head", "ValveBiped.Bip01_Head1"),
            #("Neck", "ValveBiped.Bip01_Neck1"),
            #("Chest", "ValveBiped.Bip01_Spine4"),
            #("Spine", "ValveBiped.Bip01_Spine"),
            #("Hips", "ValveBiped.Bip01_Pelvis"),
            #("RingFinger3_L", "ValveBiped.Bip01_L_Finger32"),
            #("RingFinger2_L", "ValveBiped.Bip01_L_Finger31"),
            #("RingFinger1_L", "ValveBiped.Bip01_L_Finger3"),
            #("LittleFinger3_L", "ValveBiped.Bip01_L_Finger42"),
            #("LittleFinger2_L", "ValveBiped.Bip01_L_Finger41"),
            #("LittleFinger1_L", "ValveBiped.Bip01_L_Finger4"),
            #("IndexFinger3_L", "ValveBiped.Bip01_L_Finger12"),
            #("IndexFinger2_L", "ValveBiped.Bip01_L_Finger11"),
            #("IndexFinger1_L", "ValveBiped.Bip01_L_Finger1"),
            #("MiddleFinger3_L", "ValveBiped.Bip01_L_Finger22"),
            #("MiddleFinger2_L", "ValveBiped.Bip01_L_Finger21"),
            #("MiddleFinger1_L", "ValveBiped.Bip01_L_Finger2"),
            #("Thumb2_L", "ValveBiped.Bip01_L_Finger02"),
            #("Thumb1_L", "ValveBiped.Bip01_L_Finger01"),
            #("Thumb0_L", "ValveBiped.Bip01_L_Finger0"),
            #("Left wrist", "ValveBiped.Bip01_L_Hand"),
            #("Left_elbow", "ValveBiped.Bip01_L_Forearm"),
            #("ZHandTwist_L", "ValveBiped.Bip01_L_Forearm"),
            #("Left arm", "ValveBiped.Bip01_L_UpperArm"),
            #("Left shoulder", "ValveBiped.Bip01_L_Clavicle")
        )
        
        local umaConnections = #(
            #("Toe_R", "ValveBiped.Bip01_R_Toe0"),
            #("Right_ankle", "ValveBiped.Bip01_R_Foot"),
            #("Right knee", "ValveBiped.Bip01_R_Calf"),
            #("Right leg", "ValveBiped.Bip01_R_Thigh"),
            #("Left toe", "ValveBiped.Bip01_L_Toe0"),
            #("Left_ankle", "ValveBiped.Bip01_L_Foot"),
            #("Left knee", "ValveBiped.Bip01_L_Calf"),
            #("Left leg", "ValveBiped.Bip01_L_Thigh"),
            #("RingFinger3_R", "ValveBiped.Bip01_R_Finger32"),
            #("RingFinger2_R", "ValveBiped.Bip01_R_Finger31"),
            #("RingFinger1_R", "ValveBiped.Bip01_R_Finger3"),
            #("LittleFinger3_R", "ValveBiped.Bip01_R_Finger42"),
            #("LittleFinger2_R", "ValveBiped.Bip01_R_Finger41"),
            #("LittleFinger1_R", "ValveBiped.Bip01_R_Finger4"),
            #("IndexFinger3_R", "ValveBiped.Bip01_R_Finger12"),
            #("IndexFinger2_R", "ValveBiped.Bip01_R_Finger11"),
            #("IndexFinger1_R", "ValveBiped.Bip01_R_Finger1"),
            #("MiddleFinger3_R", "ValveBiped.Bip01_R_Finger22"),
            #("MiddleFinger2_R", "ValveBiped.Bip01_R_Finger21"),
            #("MiddleFinger1_R", "ValveBiped.Bip01_R_Finger2"),
            #("Thumb2_R", "ValveBiped.Bip01_R_Finger02"),
            #("Thumb1_R", "ValveBiped.Bip01_R_Finger01"),
            #("Thumb0_R", "ValveBiped.Bip01_R_Finger0"),
            #("Right wrist", "ValveBiped.Bip01_R_Hand"),
            #("Right_elbow", "ValveBiped.Bip01_R_Forearm"),
            #("ZHandTwist_R", "ValveBiped.Bip01_R_Forearm"),
            #("Right arm", "ValveBiped.Bip01_R_UpperArm"),
            #("Right shoulder", "ValveBiped.Bip01_R_Clavicle"),
            #("Head", "ValveBiped.Bip01_Head1"),
            #("Neck", "ValveBiped.Bip01_Neck1"),
            #("Chest", "ValveBiped.Bip01_Spine4"),
            #("Spine", "ValveBiped.Bip01_Spine"),
            #("Hips", "ValveBiped.Bip01_Pelvis"),
            #("RingFinger3_L", "ValveBiped.Bip01_L_Finger32"),
            #("RingFinger2_L", "ValveBiped.Bip01_L_Finger31"),
            #("RingFinger1_L", "ValveBiped.Bip01_L_Finger3"),
            #("LittleFinger3_L", "ValveBiped.Bip01_L_Finger42"),
            #("LittleFinger2_L", "ValveBiped.Bip01_L_Finger41"),
            #("LittleFinger1_L", "ValveBiped.Bip01_L_Finger4"),
            #("IndexFinger3_L", "ValveBiped.Bip01_L_Finger12"),
            #("IndexFinger2_L", "ValveBiped.Bip01_L_Finger11"),
            #("IndexFinger1_L", "ValveBiped.Bip01_L_Finger1"),
            #("MiddleFinger3_L", "ValveBiped.Bip01_L_Finger22"),
            #("MiddleFinger2_L", "ValveBiped.Bip01_L_Finger21"),
            #("MiddleFinger1_L", "ValveBiped.Bip01_L_Finger2"),
            #("Thumb2_L", "ValveBiped.Bip01_L_Finger02"),
            #("Thumb1_L", "ValveBiped.Bip01_L_Finger01"),
            #("Thumb0_L", "ValveBiped.Bip01_L_Finger0"),
            #("Left wrist", "ValveBiped.Bip01_L_Hand"),
            #("Left_elbow", "ValveBiped.Bip01_L_Forearm"),
            #("ZHandTwist_L", "ValveBiped.Bip01_L_Forearm"),
            #("Left arm", "ValveBiped.Bip01_L_UpperArm"),
            #("Left shoulder", "ValveBiped.Bip01_L_Clavicle"),
            #("Shoulder_L", "ValveBiped.Bip01_L_Clavicle")
        )
    
        on btnSelectSkirtHelpers pressed do
        (
            -- 打开选择对话框，选择辅助对象
            selectObjects = getCurrentSelection()
            if selectObjects.count > 0 then (
                skirtHelpers = #()
                originalHiddenState = #()
                for obj in selectObjects do (
                    append skirtHelpers obj.name
                    append originalHiddenState #(obj.name, obj.isHidden)
                    obj.isHidden = false  -- 取消隐藏
                )
                format "Selected Helpers: %\n" skirtHelpers
            ) else (
                skirtHelpers = #()
                format "No Helpers selected.\n"
            )
        )
    
        on btnExecute pressed do
        (
            -- 根据模式选择连接数组
            global connections = if chkUmaMode.checked then umaConnections else normalConnections
            
            -- 检查是否是同一节点或祖先节点
            fn isDescendantOrSelf node ancestor =
            (
                if node == undefined or ancestor == undefined then return false
                if node == ancestor then return true
                local current = node.parent
                while current != undefined do (
                    if current == ancestor then return true
                    current = current.parent
                )
                return false
            )
    
            -- 第一步：连接辅助对象到骨骼
            for i = connections.count to 1 by -1 do (
                local conn = connections[i]
                local helper = getNodeByName conn[1]
                local bone = getNodeByName conn[2]
                
                if helper != undefined and bone != undefined then (
                    format "Connecting helper '%' to bone '%'\n" helper.name bone.name
                    if not isDescendantOrSelf helper bone then (
                        helper.parent = bone
                        format "Successfully connected '%' to '%'\n" helper.name bone.name
                    ) else (
                        format "Invalid parent assignment: '%' cannot be a parent of '%'.\n" helper.name bone.name
                    )
                ) else (
                    if helper == undefined then format "Helper '%' not found.\n" conn[1]
                    if bone == undefined then format "Bone '%' not found.\n" conn[2]
                )
            )
    
            -- 第二步：还原骨骼层级
            local boneHierarchy = #(
                -- 主干
                #("ValveBiped.Bip01_Pelvis", "Armature"),
                #("ValveBiped.Bip01_Spine", "ValveBiped.Bip01_Pelvis"),
                #("ValveBiped.Bip01_Spine1", "ValveBiped.Bip01_Spine"),
                #("ValveBiped.Bip01_Spine2", "ValveBiped.Bip01_Spine1"),
                #("ValveBiped.Bip01_Spine4", "ValveBiped.Bip01_Spine2"),
                #("ValveBiped.Bip01_Neck1", "ValveBiped.Bip01_Spine4"),
                #("ValveBiped.Bip01_Head1", "ValveBiped.Bip01_Neck1"),
                
                -- 左臂
                #("ValveBiped.Bip01_L_Clavicle", "ValveBiped.Bip01_Spine4"),
                #("ValveBiped.Bip01_L_UpperArm", "ValveBiped.Bip01_L_Clavicle"),
                #("ValveBiped.Bip01_L_Forearm", "ValveBiped.Bip01_L_UpperArm"),
                #("ValveBiped.Bip01_L_Hand", "ValveBiped.Bip01_L_Forearm"),
                
                -- 左手指
                #("ValveBiped.Bip01_L_Finger0", "ValveBiped.Bip01_L_Hand"),
                #("ValveBiped.Bip01_L_Finger01", "ValveBiped.Bip01_L_Finger0"),
                #("ValveBiped.Bip01_L_Finger02", "ValveBiped.Bip01_L_Finger01"),
                #("ValveBiped.Bip01_L_Finger1", "ValveBiped.Bip01_L_Hand"),
                #("ValveBiped.Bip01_L_Finger11", "ValveBiped.Bip01_L_Finger1"),
                #("ValveBiped.Bip01_L_Finger12", "ValveBiped.Bip01_L_Finger11"),
                #("ValveBiped.Bip01_L_Finger2", "ValveBiped.Bip01_L_Hand"),
                #("ValveBiped.Bip01_L_Finger21", "ValveBiped.Bip01_L_Finger2"),
                #("ValveBiped.Bip01_L_Finger22", "ValveBiped.Bip01_L_Finger21"),
                #("ValveBiped.Bip01_L_Finger3", "ValveBiped.Bip01_L_Hand"),
                #("ValveBiped.Bip01_L_Finger31", "ValveBiped.Bip01_L_Finger3"),
                #("ValveBiped.Bip01_L_Finger32", "ValveBiped.Bip01_L_Finger31"),
                #("ValveBiped.Bip01_L_Finger4", "ValveBiped.Bip01_L_Hand"),
                #("ValveBiped.Bip01_L_Finger41", "ValveBiped.Bip01_L_Finger4"),
                #("ValveBiped.Bip01_L_Finger42", "ValveBiped.Bip01_L_Finger41"),
                
                -- 右臂
                #("ValveBiped.Bip01_R_Clavicle", "ValveBiped.Bip01_Spine4"),
                #("ValveBiped.Bip01_R_UpperArm", "ValveBiped.Bip01_R_Clavicle"),
                #("ValveBiped.Bip01_R_Forearm", "ValveBiped.Bip01_R_UpperArm"),
                #("ValveBiped.Bip01_R_Hand", "ValveBiped.Bip01_R_Forearm"),
                
                -- 右手指
                #("ValveBiped.Bip01_R_Finger0", "ValveBiped.Bip01_R_Hand"),
                #("ValveBiped.Bip01_R_Finger01", "ValveBiped.Bip01_R_Finger0"),
                #("ValveBiped.Bip01_R_Finger02", "ValveBiped.Bip01_R_Finger01"),
                #("ValveBiped.Bip01_R_Finger1", "ValveBiped.Bip01_R_Hand"),
                #("ValveBiped.Bip01_R_Finger11", "ValveBiped.Bip01_R_Finger1"),
                #("ValveBiped.Bip01_R_Finger12", "ValveBiped.Bip01_R_Finger11"),
                #("ValveBiped.Bip01_R_Finger2", "ValveBiped.Bip01_R_Hand"),
                #("ValveBiped.Bip01_R_Finger21", "ValveBiped.Bip01_R_Finger2"),
                #("ValveBiped.Bip01_R_Finger22", "ValveBiped.Bip01_R_Finger21"),
                #("ValveBiped.Bip01_R_Finger3", "ValveBiped.Bip01_R_Hand"),
                #("ValveBiped.Bip01_R_Finger31", "ValveBiped.Bip01_R_Finger3"),
                #("ValveBiped.Bip01_R_Finger32", "ValveBiped.Bip01_R_Finger31"),
                #("ValveBiped.Bip01_R_Finger4", "ValveBiped.Bip01_R_Hand"),
                #("ValveBiped.Bip01_R_Finger41", "ValveBiped.Bip01_R_Finger4"),
                #("ValveBiped.Bip01_R_Finger42", "ValveBiped.Bip01_R_Finger41"),
                
                -- 左腿
                #("ValveBiped.Bip01_L_Thigh", "ValveBiped.Bip01_Pelvis"),
                #("ValveBiped.Bip01_L_Calf", "ValveBiped.Bip01_L_Thigh"),
                #("ValveBiped.Bip01_L_Foot", "ValveBiped.Bip01_L_Calf"),
                #("ValveBiped.Bip01_L_Toe0", "ValveBiped.Bip01_L_Foot"),
                
                -- 右腿
                #("ValveBiped.Bip01_R_Thigh", "ValveBiped.Bip01_Pelvis"),
                #("ValveBiped.Bip01_R_Calf", "ValveBiped.Bip01_R_Thigh"),
                #("ValveBiped.Bip01_R_Foot", "ValveBiped.Bip01_R_Calf"),
                #("ValveBiped.Bip01_R_Toe0", "ValveBiped.Bip01_R_Foot")
            )
    
            -- 执行骨骼层级还原
            for pair in boneHierarchy do (
                local child = getNodeByName pair[1]
                local parent = getNodeByName pair[2]
                
                if child != undefined and parent != undefined then (
                    if not isDescendantOrSelf parent child then (
                        child.parent = parent
                        format "Connected bone '%' to '%'\n" child.name parent.name
                    ) else (
                        format "Invalid bone hierarchy: '%' cannot be a parent of '%'\n" parent.name child.name
                    )
                ) else (
                    if child == undefined then format "Bone '%' not found.\n" pair[1]
                    if parent == undefined then format "Bone '%' not found.\n" pair[2]
                )
            )
    
            -- 处理裙子辅助对象
            if skirtHelpers.count > 0 then (
                local pelvis = getNodeByName "ValveBiped.Bip01_Pelvis"
                if pelvis != undefined then (
                    for helperName in skirtHelpers do (
                        local helper = getNodeByName helperName
                        if helper != undefined then (
                            format "Processing skirt helper '%'\n" helper.name
                            -- 先断开当前的父级连接
                            helper.parent = undefined
                            -- 再连接到 ValveBiped.Bip01_Pelvis
                            if not isDescendantOrSelf helper pelvis then (
                                helper.parent = pelvis
                                format "Successfully connected '%' to pelvis\n" helper.name
                            ) else (
                                format "Invalid parent assignment: '%' cannot be a parent of '%'\n" helper.name pelvis.name
                            )
                        ) else (
                            format "Helper '%' not found.\n" helperName
                        )
                    )
                ) else (
                    format "Pelvis bone not found.\n"
                )
            )
    
            -- 恢复原来的隐藏状态
            for state in originalHiddenState do (
                local obj = getNodeByName state[1]
                if obj != undefined then (
                    obj.isHidden = state[2]
                )
            )
        )
    )
    
    createDialog SkirtHelperDialog
)

fn BoneAlignmentToolManager = (
    -- 创建工具结构体
    struct BoneAlignToolStruct (
        -- 成员变量
        boneAlignToolRollout,
        
        -- 查找节点函数
        fn findNodeByName nodeName = (
            for obj in objects where matchPattern obj.name pattern:nodeName do (
                return obj
            )
            return undefined
        ),
        
        -- 安全对齐函数
        fn safeAlign sourceObj targetObj = (
            if sourceObj != undefined and targetObj != undefined then (
                sourceObj.position = targetObj.position
            )
        ),
        
        -- 基础对骨函数
        fn alignAndScaleBones = (
            try (
                -- 1. 首先找到所有必要的节点
                local armature = this.findNodeByName "Armature"
                if armature == undefined do throw "找不到名为 'Armature' 的对象"

                local leftLeg = this.findNodeByName "ValveBiped.Bip01_L_Thigh"
                local rightLeg = this.findNodeByName "ValveBiped.Bip01_R_Thigh"
                local pelvis = this.findNodeByName "ValveBiped.Bip01_Pelvis"
                local customLeftLeg = this.findNodeByName "Left leg"
                local customRightLeg = this.findNodeByName "Right leg"
                local spine = this.findNodeByName "ValveBiped.Bip01_Spine"
                local spine1 = this.findNodeByName "ValveBiped.Bip01_Spine1"
                local spine2 = this.findNodeByName "ValveBiped.Bip01_Spine2"
                local spine4 = this.findNodeByName "ValveBiped.Bip01_Spine4"
                local neck = this.findNodeByName "ValveBiped.Bip01_Neck1"
                local head = this.findNodeByName "ValveBiped.Bip01_Head1"
                local customSpine = this.findNodeByName "Spine"
                local chest = this.findNodeByName "Chest"
                local customNeck = this.findNodeByName "Neck"
                local customHead = this.findNodeByName "Head"
                local leftClavicle = this.findNodeByName "ValveBiped.Bip01_L_Clavicle"
                local leftUpperArm = this.findNodeByName "ValveBiped.Bip01_L_UpperArm"
                local leftForearm = this.findNodeByName "ValveBiped.Bip01_L_Forearm"
                local rightClavicle = this.findNodeByName "ValveBiped.Bip01_R_Clavicle"
                local rightUpperArm = this.findNodeByName "ValveBiped.Bip01_R_UpperArm"
                local rightForearm = this.findNodeByName "ValveBiped.Bip01_R_Forearm"
                local customLeftShoulder = this.findNodeByName "Left shoulder"
                local customLeftArm = this.findNodeByName "Left arm"
                local customLeftElbow = this.findNodeByName "Left_elbow"
                local customLeftWrist = this.findNodeByName "Left wrist"
                local customRightShoulder = this.findNodeByName "Right shoulder"
                local customRightArm = this.findNodeByName "Right arm"
                local customRightElbow = this.findNodeByName "Right_elbow"
                local customRightWrist = this.findNodeByName "Right wrist"
                local rightKnee = this.findNodeByName "Right knee"
                local leftKnee = this.findNodeByName "Left knee"
                local rightAnkle = this.findNodeByName "Right_ankle"
                local leftAnkle = this.findNodeByName "Left_ankle"
                local rightCalf = this.findNodeByName "ValveBiped.Bip01_R_Calf"
                local leftCalf = this.findNodeByName "ValveBiped.Bip01_L_Calf"
                local rightFoot = this.findNodeByName "ValveBiped.Bip01_R_Foot"
                local leftFoot = this.findNodeByName "ValveBiped.Bip01_L_Foot"

                -- 手指的骨骼和辅助对象
                local fingerBonesAndHelpers = #(
                    #("ValveBiped.Bip01_L_Finger4", "LittleFinger1_L", "ValveBiped.Bip01_L_Finger41", "LittleFinger2_L", "ValveBiped.Bip01_L_Finger42", "LittleFinger3_L"),
                    #("ValveBiped.Bip01_L_Finger3", "RingFinger1_L", "ValveBiped.Bip01_L_Finger31", "RingFinger2_L", "ValveBiped.Bip01_L_Finger32", "RingFinger3_L"),
                    #("ValveBiped.Bip01_L_Finger2", "MiddleFinger1_L", "ValveBiped.Bip01_L_Finger21", "MiddleFinger2_L", "ValveBiped.Bip01_L_Finger22", "MiddleFinger3_L"),
                    #("ValveBiped.Bip01_L_Finger1", "IndexFinger1_L", "ValveBiped.Bip01_L_Finger11", "IndexFinger2_L", "ValveBiped.Bip01_L_Finger12", "IndexFinger3_L"),
                    #("ValveBiped.Bip01_R_Finger4", "LittleFinger1_R", "ValveBiped.Bip01_R_Finger41", "LittleFinger2_R", "ValveBiped.Bip01_R_Finger42", "LittleFinger3_R"),
                    #("ValveBiped.Bip01_R_Finger3", "RingFinger1_R", "ValveBiped.Bip01_R_Finger31", "RingFinger2_R", "ValveBiped.Bip01_R_Finger32", "RingFinger3_R"),
                    #("ValveBiped.Bip01_R_Finger2", "MiddleFinger1_R", "ValveBiped.Bip01_R_Finger21", "MiddleFinger2_R", "ValveBiped.Bip01_R_Finger22", "MiddleFinger3_R"),
                    #("ValveBiped.Bip01_R_Finger1", "IndexFinger1_R", "ValveBiped.Bip01_R_Finger11", "IndexFinger2_R", "ValveBiped.Bip01_R_Finger12", "IndexFinger3_R")
                )

                -- 大拇指的骨骼和辅助对象
                local thumbBonesAndHelpers = #(
                    #("ValveBiped.Bip01_L_Finger0", "Thumb0_L", "ValveBiped.Bip01_L_Finger01", "Thumb1_L", "ValveBiped.Bip01_L_Finger02", "Thumb2_L"),
                    #("ValveBiped.Bip01_R_Finger0", "Thumb0_R", "ValveBiped.Bip01_R_Finger01", "Thumb1_R", "ValveBiped.Bip01_R_Finger02", "Thumb2_R")
                )

                -- 检查必要对象是否存在
                if (
                    leftLeg == undefined or rightLeg == undefined or pelvis == undefined or 
                    customLeftLeg == undefined or customRightLeg == undefined or spine == undefined or 
                    spine1 == undefined or spine2 == undefined or spine4 == undefined or neck == undefined or 
                    head == undefined or customSpine == undefined or chest == undefined or customNeck == undefined or 
                    customHead == undefined or leftClavicle == undefined or leftUpperArm == undefined or 
                    leftForearm == undefined or rightClavicle == undefined or rightUpperArm == undefined or 
                    rightForearm == undefined or customLeftShoulder == undefined or customLeftArm == undefined or 
                    customLeftElbow == undefined or customLeftWrist == undefined or customRightShoulder == undefined or 
                    customRightArm == undefined or customRightElbow == undefined or customRightWrist == undefined or
                    rightKnee == undefined or leftKnee == undefined or rightAnkle == undefined or leftAnkle == undefined or
                    rightCalf == undefined or leftCalf == undefined or rightFoot == undefined or leftFoot == undefined
                ) then (
                    throw "找不到一个或多个必要的对象"
                )

                -- 2. 计算并应用整体缩放
                local targetHeight = (leftLeg.position.z + rightLeg.position.z) / 2
                local customHeight = (customLeftLeg.position.z + customRightLeg.position.z) / 2
                local scaleFactor = targetHeight / customHeight
                scale armature [scaleFactor, scaleFactor, scaleFactor]

                -- 3. 调整Armature对象的Y轴位置
                local yOffset = ((leftLeg.position.y + rightLeg.position.y) / 2) - ((customLeftLeg.position.y + customRightLeg.position.y) / 2)
                armature.position.y += yOffset

                -- 4. 断开主要骨骼的父子关系
                leftLeg.parent = undefined
                rightLeg.parent = undefined
                spine.parent = undefined
                spine1.parent = undefined
                spine2.parent = undefined
                spine4.parent = undefined
                neck.parent = undefined
                head.parent = undefined
                leftClavicle.parent = undefined
                leftUpperArm.parent = undefined
                rightClavicle.parent = undefined
                rightUpperArm.parent = undefined
                rightCalf.parent = undefined
                leftCalf.parent = undefined
                rightFoot.parent = undefined
                leftFoot.parent = undefined

                -- 5. 对齐主要骨骼
                this.safeAlign leftLeg customLeftLeg
                this.safeAlign rightLeg customRightLeg
                this.safeAlign spine customSpine
                this.safeAlign spine1 spine
                this.safeAlign spine2 spine1
                this.safeAlign spine4 chest
                this.safeAlign neck customNeck
                this.safeAlign head customHead
                this.safeAlign leftClavicle customLeftShoulder
                this.safeAlign leftUpperArm customLeftArm
                this.safeAlign rightClavicle customRightShoulder
                this.safeAlign rightUpperArm customRightArm
                this.safeAlign rightCalf rightKnee
                this.safeAlign leftCalf leftKnee
                this.safeAlign rightFoot rightAnkle
                this.safeAlign leftFoot leftAnkle

                -- 6. 处理手臂和前臂的缩放
                -- 缩放左上臂，使其末端位置与左肘辅助对象的位置一致
                local leftUpperArmEndPos = leftForearm.position
                local customLeftElbowPos = customLeftElbow.position
                local leftUpperArmLength = distance leftUpperArm.position leftUpperArmEndPos
                local customLeftUpperArmLength = distance customLeftArm.position customLeftElbowPos
                local leftUpperArmScaleFactor = customLeftUpperArmLength / leftUpperArmLength
                scale leftUpperArm [leftUpperArmScaleFactor, leftUpperArmScaleFactor, leftUpperArmScaleFactor]

                -- 缩放右上臂，使其末端位置与右肘辅助对象的位置一致
                local rightUpperArmEndPos = rightForearm.position
                local customRightElbowPos = customRightElbow.position
                local rightUpperArmLength = distance rightUpperArm.position rightUpperArmEndPos
                local customRightUpperArmLength = distance customRightArm.position customRightElbowPos
                local rightUpperArmScaleFactor = customRightUpperArmLength / rightUpperArmLength
                scale rightUpperArm [rightUpperArmScaleFactor, rightUpperArmScaleFactor, rightUpperArmScaleFactor]

                -- 7. 等待一帧以确保缩放和位置更新
                completeRedraw()
                
                -- 8. 现在处理手指和手腕
                -- 手腕对齐
                local leftHand = this.findNodeByName "ValveBiped.Bip01_L_Hand"
                local rightHand = this.findNodeByName "ValveBiped.Bip01_R_Hand"

                if leftHand != undefined and customLeftWrist != undefined then (
                    local originalParent = leftHand.parent
                    leftHand.parent = undefined
                    -- 获取缩放后的辅助对象位置
                    local scaledWristPos = customLeftWrist.position
                    leftHand.position = scaledWristPos
                    leftHand.parent = originalParent
                )

                if rightHand != undefined and customRightWrist != undefined then (
                    local originalParent = rightHand.parent
                    rightHand.parent = undefined
                    local scaledWristPos = customRightWrist.position
                    rightHand.position = scaledWristPos
                    rightHand.parent = originalParent
                )

                -- 9. 处理手指
                for i = 1 to fingerBonesAndHelpers.count do (
                    local firstBoneName = fingerBonesAndHelpers[i][1]
                    local firstHelperName = fingerBonesAndHelpers[i][2]
                    local secondBoneName = fingerBonesAndHelpers[i][3]
                    local secondHelperName = fingerBonesAndHelpers[i][4]
                    local thirdBoneName = fingerBonesAndHelpers[i][5]
                    local thirdHelperName = fingerBonesAndHelpers[i][6]

                    local firstBone = this.findNodeByName firstBoneName
                    local firstHelper = this.findNodeByName firstHelperName
                    local secondBone = this.findNodeByName secondBoneName
                    local secondHelper = this.findNodeByName secondHelperName
                    local thirdBone = this.findNodeByName thirdBoneName
                    local thirdHelper = this.findNodeByName thirdHelperName

                    if (firstBone != undefined and firstHelper != undefined and 
                        secondBone != undefined and secondHelper != undefined and 
                        thirdBone != undefined and thirdHelper != undefined) then (
                        
                        -- 保存原始父对象
                        local originalParent = firstBone.parent
                        local secondOriginalParent = secondBone.parent
                        local thirdOriginalParent = thirdBone.parent
                        
                        -- 临时断开父子关系
                        firstBone.parent = undefined
                        secondBone.parent = undefined
                        thirdBone.parent = undefined
                        
                        -- 使用缩放后的辅助对象位置进行对齐
                        firstBone.position = firstHelper.position
                        secondBone.position = secondHelper.position
                        thirdBone.position = thirdHelper.position
                        
                        -- 计算缩放后的长度并应用缩放
                        local firstBoneLength = distance firstBone.position secondBone.position
                        local firstHelperLength = distance firstHelper.position secondHelper.position
                        local firstBoneScaleFactor = firstHelperLength / firstBoneLength
                        scale firstBone [firstBoneScaleFactor, firstBoneScaleFactor, firstBoneScaleFactor]
                        
                        local secondBoneLength = distance secondBone.position thirdBone.position
                        local secondHelperLength = distance secondHelper.position thirdHelper.position
                        local secondBoneScaleFactor = secondHelperLength / secondBoneLength
                        scale secondBone [secondBoneScaleFactor, secondBoneScaleFactor, secondBoneScaleFactor]
                        
                        -- 恢复父子关系
                        firstBone.parent = originalParent
                        secondBone.parent = secondOriginalParent
                        thirdBone.parent = thirdOriginalParent
                    )
                )

                -- 10. 处理大拇指
                for i = 1 to thumbBonesAndHelpers.count do (
                    local firstBoneName = thumbBonesAndHelpers[i][1]
                    local firstHelperName = thumbBonesAndHelpers[i][2]
                    local secondBoneName = thumbBonesAndHelpers[i][3]
                    local secondHelperName = thumbBonesAndHelpers[i][4]
                    local thirdBoneName = thumbBonesAndHelpers[i][5]
                    local thirdHelperName = thumbBonesAndHelpers[i][6]

                    local firstBone = this.findNodeByName firstBoneName
                    local firstHelper = this.findNodeByName firstHelperName
                    local secondBone = this.findNodeByName secondBoneName
                    local secondHelper = this.findNodeByName secondHelperName
                    local thirdBone = this.findNodeByName thirdBoneName
                    local thirdHelper = this.findNodeByName thirdHelperName

                    if (firstBone != undefined and firstHelper != undefined and 
                        secondBone != undefined and secondHelper != undefined and 
                        thirdBone != undefined and thirdHelper != undefined) then (
                        
                        -- 断开第一根大拇指骨骼的父子关系
                        local originalParent = firstBone.parent
                        firstBone.parent = undefined

                        -- 先对齐位置
                        local originalPos = firstHelper.position
                        this.safeAlign firstBone firstHelper

                        -- 计算骨骼和辅助对象的方向向量
                        local boneDir = normalize (secondBone.position - firstBone.position)
                        local helperDir = normalize (secondHelper.position - firstHelper.position)

                        -- 计算旋转轴和角度
                        local rotationAxis = cross boneDir helperDir
                        local rotationAngle = acos(dot boneDir helperDir)

                        -- 如果旋转轴接近零向量，说明方向相反
                        if (length rotationAxis) < 0.001 then (
                            rotationAxis = cross boneDir [0,0,1]
                            if (length rotationAxis) < 0.001 then (
                                rotationAxis = cross boneDir [0,1,0]
                            )
                            rotationAngle = 180
                        )

                        -- 应用旋转，保持位置不变
                        local currentPos = firstBone.position
                        in coordsys world (
                            rotate firstBone (angleaxis rotationAngle (normalize rotationAxis))
                        )
                        firstBone.position = currentPos

                        -- 计算缩放因子
                        local firstBoneEndPos = secondBone.position
                        local firstHelperEndPos = secondHelper.position
                        local firstBoneLength = distance firstBone.position firstBoneEndPos
                        local firstHelperLength = distance firstHelper.position firstHelperEndPos
                        local firstBoneScaleFactor = firstHelperLength / firstBoneLength
                        scale firstBone [firstBoneScaleFactor, firstBoneScaleFactor, firstBoneScaleFactor]

                        -- 重新连接第一根大拇指骨骼的父子关系
                        firstBone.parent = originalParent

                        -- 计算第二根骨骼的缩放因子
                        local secondBoneEndPos = thirdBone.position
                        local secondHelperEndPos = thirdHelper.position
                        local secondBoneLength = distance secondBone.position secondBoneEndPos
                        local secondHelperLength = distance secondHelper.position secondHelperEndPos
                        local secondBoneScaleFactor = secondHelperLength / secondBoneLength
                        scale secondBone [secondBoneScaleFactor, secondBoneScaleFactor, secondBoneScaleFactor]
                    )
                )

                -- 11. 最后重新建立骨骼的父子关系
                leftLeg.parent = spine
                rightLeg.parent = spine
                spine.parent = pelvis
                spine1.parent = spine
                spine2.parent = spine1
                spine4.parent = spine2
                neck.parent = spine
                head.parent = neck
                leftClavicle.parent = spine
                leftUpperArm.parent = spine
                rightClavicle.parent = spine
                rightUpperArm.parent = spine
                rightCalf.parent = rightLeg
                leftCalf.parent = leftLeg
                rightFoot.parent = rightLeg
                leftFoot.parent = leftLeg

                format "基础模型骨骼对齐和缩放完成。\n"
                return true

            ) catch (
                format "发生错误: %\n" (getCurrentException())
                return false
            )
        ),
        
        -- 赛马娘专用对骨函数
        fn alignAndScaleBones_UMA = (
            try (
                -- 找到所有必要的节点
                local armature = this.findNodeByName "Armature"
                if armature == undefined do throw "找不到名为 'Armature' 的对象"
            
                local leftLeg = this.findNodeByName "ValveBiped.Bip01_L_Thigh"
                local rightLeg = this.findNodeByName "ValveBiped.Bip01_R_Thigh"
                local pelvis = this.findNodeByName "ValveBiped.Bip01_Pelvis"
                local customLeftLeg = this.findNodeByName "Thigh_L"
                local customRightLeg = this.findNodeByName "Thigh_R"
                local spine = this.findNodeByName "ValveBiped.Bip01_Spine"
                local spine1 = this.findNodeByName "ValveBiped.Bip01_Spine1"
                local spine2 = this.findNodeByName "ValveBiped.Bip01_Spine2"
                local spine4 = this.findNodeByName "ValveBiped.Bip01_Spine4"
                local neck = this.findNodeByName "ValveBiped.Bip01_Neck1"
                local head = this.findNodeByName "ValveBiped.Bip01_Head1"
                local UpBody_Ctrl = this.findNodeByName "UpBody_Ctrl"
                local Waist = this.findNodeByName "Waist"
                local customSpine = this.findNodeByName "Spine"
                local chest = this.findNodeByName "Chest"
                local customNeck = this.findNodeByName "Neck"
                local customHead = this.findNodeByName "Head"
                local leftClavicle = this.findNodeByName "ValveBiped.Bip01_L_Clavicle"
                local leftUpperArm = this.findNodeByName "ValveBiped.Bip01_L_UpperArm"
                local leftForearm = this.findNodeByName "ValveBiped.Bip01_L_Forearm"
                local rightClavicle = this.findNodeByName "ValveBiped.Bip01_R_Clavicle"
                local rightUpperArm = this.findNodeByName "ValveBiped.Bip01_R_UpperArm"
                local rightForearm = this.findNodeByName "ValveBiped.Bip01_R_Forearm"
                local customLeftShoulder = this.findNodeByName "Shoulder_L"
                local customLeftArm = this.findNodeByName "Arm_L"
                local customLeftElbow = this.findNodeByName "Elbow_L"
                local customLeftWrist = this.findNodeByName "Wrist_L"
                local customRightShoulder = this.findNodeByName "Shoulder_R"
                local customRightArm = this.findNodeByName "Arm_R"
                local customRightElbow = this.findNodeByName "Elbow_R"
                local customRightWrist = this.findNodeByName "Wrist_R"
                local rightKnee = this.findNodeByName "Knee_R"
                local leftKnee = this.findNodeByName "Knee_L"
                local rightAnkle = this.findNodeByName "Ankle_R"
                local leftAnkle = this.findNodeByName "Ankle_L"
                local rightCalf = this.findNodeByName "ValveBiped.Bip01_R_Calf"
                local leftCalf = this.findNodeByName "ValveBiped.Bip01_L_Calf"
                local rightFoot = this.findNodeByName "ValveBiped.Bip01_R_Foot"
                local leftFoot = this.findNodeByName "ValveBiped.Bip01_L_Foot"
            
                -- 手指的骨骼和辅助对象 (赛马娘版本)
                local fingerBonesAndHelpers = #(
                    #("ValveBiped.Bip01_L_Finger4", "Pinky_01_L", "ValveBiped.Bip01_L_Finger41", "Pinky_02_L", "ValveBiped.Bip01_L_Finger42", "Pinky_03_L"),
                    #("ValveBiped.Bip01_L_Finger3", "Ring_01_L", "ValveBiped.Bip01_L_Finger31", "Ring_02_L", "ValveBiped.Bip01_L_Finger32", "Ring_03_L"),
                    #("ValveBiped.Bip01_L_Finger2", "Middle_01_L", "ValveBiped.Bip01_L_Finger21", "Middle_02_L", "ValveBiped.Bip01_L_Finger22", "Middle_03_L"),
                    #("ValveBiped.Bip01_L_Finger1", "Index_01_L", "ValveBiped.Bip01_L_Finger11", "Index_02_L", "ValveBiped.Bip01_L_Finger12", "Index_03_L"),
                    #("ValveBiped.Bip01_R_Finger4", "Pinky_01_R", "ValveBiped.Bip01_R_Finger41", "Pinky_02_R", "ValveBiped.Bip01_R_Finger42", "Pinky_03_R"),
                    #("ValveBiped.Bip01_R_Finger3", "Ring_01_R", "ValveBiped.Bip01_R_Finger31", "Ring_02_R", "ValveBiped.Bip01_R_Finger32", "Ring_03_R"),
                    #("ValveBiped.Bip01_R_Finger2", "Middle_01_R", "ValveBiped.Bip01_R_Finger21", "Middle_02_R", "ValveBiped.Bip01_R_Finger22", "Middle_03_R"),
                    #("ValveBiped.Bip01_R_Finger1", "Index_01_R", "ValveBiped.Bip01_R_Finger11", "Index_02_R", "ValveBiped.Bip01_R_Finger12", "Index_03_R")
                )
            
                -- 大拇指的骨骼和辅助对象 (赛马娘版本)
                local thumbBonesAndHelpers = #(
                    #("ValveBiped.Bip01_L_Finger0", "Thumb_01_L", "ValveBiped.Bip01_L_Finger01", "Thumb_02_L", "ValveBiped.Bip01_L_Finger02", "Thumb_03_L"),
                    #("ValveBiped.Bip01_R_Finger0", "Thumb_01_R", "ValveBiped.Bip01_R_Finger01", "Thumb_02_R", "ValveBiped.Bip01_R_Finger02", "Thumb_03_R")
                )
            
                if (
                    leftLeg == undefined or rightLeg == undefined or pelvis == undefined or 
                    customLeftLeg == undefined or customRightLeg == undefined or spine == undefined or 
                    spine1 == undefined or spine2 == undefined or spine4 == undefined or neck == undefined or 
                    head == undefined or customSpine == undefined or chest == undefined or customNeck == undefined or 
                    customHead == undefined or leftClavicle == undefined or leftUpperArm == undefined or 
                    leftForearm == undefined or rightClavicle == undefined or rightUpperArm == undefined or 
                    rightForearm == undefined or customLeftShoulder == undefined or customLeftArm == undefined or 
                    customLeftElbow == undefined or customLeftWrist == undefined or customRightShoulder == undefined or 
                    customRightArm == undefined or customRightElbow == undefined or customRightWrist == undefined or
                    rightKnee == undefined or leftKnee == undefined or rightAnkle == undefined or leftAnkle == undefined or
                    rightCalf == undefined or leftCalf == undefined or rightFoot == undefined or leftFoot == undefined
                ) then (
                    throw "找不到一个或多个必要的对象"
                )
            
                -- 骨骼的Z轴高度
                local targetHeight = (leftLeg.position.z + rightLeg.position.z) / 2
            
                -- 自定义模型辅助对象的平均Z轴高度
                local customHeight = (customLeftLeg.position.z + customRightLeg.position.z) / 2
            
                -- 计算缩放因子并应用缩放
                local scaleFactor = targetHeight / customHeight
                scale armature [scaleFactor, scaleFactor, scaleFactor]
            
                -- 调整Armature对象的Y轴位置
                local yOffset = ((leftLeg.position.y + rightLeg.position.y) / 2) - ((customLeftLeg.position.y + customRightLeg.position.y) / 2)
                armature.position.y += yOffset
            
                -- 断开各个骨骼的父子关系
                leftLeg.parent = undefined
                rightLeg.parent = undefined
                spine.parent = undefined
                spine1.parent = undefined
                spine2.parent = undefined
                spine4.parent = undefined
                neck.parent = undefined
                head.parent = undefined
                leftClavicle.parent = undefined
                leftUpperArm.parent = undefined
                rightClavicle.parent = undefined
                rightUpperArm.parent = undefined
                rightCalf.parent = undefined
                leftCalf.parent = undefined
                rightFoot.parent = undefined
                leftFoot.parent = undefined
            
                -- 使用修改后的对齐方式
                this.safeAlign leftLeg customLeftLeg
                this.safeAlign rightLeg customRightLeg
                this.safeAlign spine UpBody_Ctrl
                this.safeAlign spine1 Waist
                this.safeAlign spine2 customSpine
                this.safeAlign spine4 chest
                this.safeAlign neck customNeck
                this.safeAlign head customHead
                this.safeAlign leftClavicle customLeftShoulder
                this.safeAlign leftUpperArm customLeftArm
                this.safeAlign rightClavicle customRightShoulder
                this.safeAlign rightUpperArm customRightArm
                this.safeAlign rightCalf rightKnee
                this.safeAlign leftCalf leftKnee
                this.safeAlign rightFoot rightAnkle
                this.safeAlign leftFoot leftAnkle

                -- 等待一帧以确保缩放和位置更新
                completeRedraw()
                
                -- 处理手指
                for i = 1 to fingerBonesAndHelpers.count do (
                    local firstBoneName = fingerBonesAndHelpers[i][1]
                    local firstHelperName = fingerBonesAndHelpers[i][2]
                    local secondBoneName = fingerBonesAndHelpers[i][3]
                    local secondHelperName = fingerBonesAndHelpers[i][4]
                    local thirdBoneName = fingerBonesAndHelpers[i][5]
                    local thirdHelperName = fingerBonesAndHelpers[i][6]

                    local firstBone = this.findNodeByName firstBoneName
                    local firstHelper = this.findNodeByName firstHelperName
                    local secondBone = this.findNodeByName secondBoneName
                    local secondHelper = this.findNodeByName secondHelperName
                    local thirdBone = this.findNodeByName thirdBoneName
                    local thirdHelper = this.findNodeByName thirdHelperName

                    if (firstBone != undefined and firstHelper != undefined and 
                        secondBone != undefined and secondHelper != undefined and 
                        thirdBone != undefined and thirdHelper != undefined) then (
                        
                        -- 保存原始父对象
                        local originalParent = firstBone.parent
                        firstBone.parent = undefined
                        
                        -- 使用safeAlign对齐第一根手指骨骼的位置
                        this.safeAlign firstBone firstHelper

                        -- 缩放第一根手指骨骼
                        local firstBoneEndPos = secondBone.position
                        local firstHelperEndPos = secondHelper.position
                        local firstBoneLength = distance firstBone.position firstBoneEndPos
                        local firstHelperLength = distance firstHelper.position firstHelperEndPos
                        local firstBoneScaleFactor = firstHelperLength / firstBoneLength
                        scale firstBone [firstBoneScaleFactor, firstBoneScaleFactor, firstBoneScaleFactor]

                        -- 缩放第二根手指骨骼
                        local secondBoneEndPos = thirdBone.position
                        local secondHelperEndPos = thirdHelper.position
                        local secondBoneLength = distance secondBone.position secondBoneEndPos
                        local secondHelperLength = distance secondHelper.position secondHelperEndPos
                        local secondBoneScaleFactor = secondHelperLength / secondBoneLength
                        scale secondBone [secondBoneScaleFactor, secondBoneScaleFactor, secondBoneScaleFactor]

                        -- 重新连接第一根手指骨骼的父子关系
                        firstBone.parent = originalParent
                    )
                )

                -- 处理大拇指
                for i = 1 to thumbBonesAndHelpers.count do (
                    local firstBoneName = thumbBonesAndHelpers[i][1]
                    local firstHelperName = thumbBonesAndHelpers[i][2]
                    local secondBoneName = thumbBonesAndHelpers[i][3]
                    local secondHelperName = thumbBonesAndHelpers[i][4]
                    local thirdBoneName = thumbBonesAndHelpers[i][5]
                    local thirdHelperName = thumbBonesAndHelpers[i][6]

                    local firstBone = this.findNodeByName firstBoneName
                    local firstHelper = this.findNodeByName firstHelperName
                    local secondBone = this.findNodeByName secondBoneName
                    local secondHelper = this.findNodeByName secondHelperName
                    local thirdBone = this.findNodeByName thirdBoneName
                    local thirdHelper = this.findNodeByName thirdHelperName

                    if (firstBone != undefined and firstHelper != undefined and 
                        secondBone != undefined and secondHelper != undefined and 
                        thirdBone != undefined and thirdHelper != undefined) then (
                        
                        -- 断开第一根大拇指骨骼的父子关系
                        local originalParent = firstBone.parent
                        firstBone.parent = undefined

                        -- 先对齐位置
                        local originalPos = firstHelper.position
                        this.safeAlign firstBone firstHelper

                        -- 计算骨骼和辅助对象的方向向量
                        local boneDir = normalize (secondBone.position - firstBone.position)
                        local helperDir = normalize (secondHelper.position - firstHelper.position)

                        -- 计算旋转轴和角度
                        local rotationAxis = cross boneDir helperDir
                        local rotationAngle = acos(dot boneDir helperDir)

                        -- 如果旋转轴接近零向量，说明方向相反
                        if (length rotationAxis) < 0.001 then (
                            rotationAxis = cross boneDir [0,0,1]
                            if (length rotationAxis) < 0.001 then (
                                rotationAxis = cross boneDir [0,1,0]
                            )
                            rotationAngle = 180
                        )

                        -- 应用旋转，保持位置不变
                        local currentPos = firstBone.position
                        in coordsys world (
                            rotate firstBone (angleaxis rotationAngle (normalize rotationAxis))
                        )
                        firstBone.position = currentPos

                        -- 计算缩放因子
                        local firstBoneEndPos = secondBone.position
                        local firstHelperEndPos = secondHelper.position
                        local firstBoneLength = distance firstBone.position firstBoneEndPos
                        local firstHelperLength = distance firstHelper.position firstHelperEndPos
                        local firstBoneScaleFactor = firstHelperLength / firstBoneLength
                        scale firstBone [firstBoneScaleFactor, firstBoneScaleFactor, firstBoneScaleFactor]

                        -- 重新连接第一根大拇指骨骼的父子关系
                        firstBone.parent = originalParent

                        -- 计算第二根骨骼的缩放因子
                        local secondBoneEndPos = thirdBone.position
                        local secondHelperEndPos = thirdHelper.position
                        local secondBoneLength = distance secondBone.position secondBoneEndPos
                        local secondHelperLength = distance secondHelper.position secondHelperEndPos
                        local secondBoneScaleFactor = secondHelperLength / secondBoneLength
                        scale secondBone [secondBoneScaleFactor, secondBoneScaleFactor, secondBoneScaleFactor]
                    )
                )
            
                -- 重新建立骨骼的父子关系
                leftLeg.parent = pelvis
                rightLeg.parent = pelvis
                spine.parent = pelvis
                spine1.parent = spine
                spine2.parent = spine1
                spine4.parent = spine2
                neck.parent = spine4
                head.parent = neck
                leftClavicle.parent = spine4
                leftUpperArm.parent = leftClavicle
                rightClavicle.parent = spine4
                rightUpperArm.parent = rightClavicle
                rightCalf.parent = rightLeg
                leftCalf.parent = leftLeg
                rightFoot.parent = rightCalf
                leftFoot.parent = leftCalf
            
                -- 骨骼对齐和缩放完成
                format "骨骼对齐和缩放完成。\n"
            
            ) catch (
                -- 捕获并打印错误信息
                format "发生错误: %\n" (getCurrentException())
            )
        ),
        
        -- 检测函数实现
        fn checkMissingObjects modelType = (
            -- 根据模型类型选择检测列表
            local objNamesToCheck = if modelType == "uma" then (
                #(
                    "Armature", "Thigh_L", "Thigh_R", "Spine", "Chest", "Neck", "Head",
                    "Shoulder_L", "Arm_L", "Elbow_L", "Wrist_L",
                    "Shoulder_R", "Arm_R", "Elbow_R", "Wrist_R",
                    "Knee_R", "Knee_L", "Ankle_R", "Ankle_L",
                    "Pinky_01_L", "Pinky_02_L", "Pinky_03_L",
                    "Ring_01_L", "Ring_02_L", "Ring_03_L",
                    "Middle_01_L", "Middle_02_L", "Middle_03_L",
                    "Index_01_L", "Index_02_L", "Index_03_L",
                    "Thumb_01_L", "Thumb_02_L", "Thumb_03_L",
                    "Pinky_01_R", "Pinky_02_R", "Pinky_03_R",
                    "Ring_01_R", "Ring_02_R", "Ring_03_R",
                    "Middle_01_R", "Middle_02_R", "Middle_03_R",
                    "Index_01_R", "Index_02_R", "Index_03_R",
                    "Thumb_01_R", "Thumb_02_R", "Thumb_03_R",
                    "UpBody_Ctrl", "Waist"  -- 添加赛马娘特有的骨骼
                )
            ) else (
                #(
                    "Armature", "Left leg", "Right leg", "Spine", "Chest", "Neck", "Head",
                    "Left shoulder", "Left arm", "Left_elbow", "Left wrist",
                    "Right shoulder", "Right arm", "Right_elbow", "Right wrist",
                    "Right knee", "Left knee", "Right_ankle", "Left_ankle",
                    "LittleFinger1_L", "LittleFinger2_L", "LittleFinger3_L",
                    "RingFinger1_L", "RingFinger2_L", "RingFinger3_L",
                    "MiddleFinger1_L", "MiddleFinger2_L", "MiddleFinger3_L",
                    "IndexFinger1_L", "IndexFinger2_L", "IndexFinger3_L",
                    "Thumb0_L", "Thumb1_L", "Thumb2_L",
                    "LittleFinger1_R", "LittleFinger2_R", "LittleFinger3_R",
                    "RingFinger1_R", "RingFinger2_R", "RingFinger3_R",
                    "MiddleFinger1_R", "MiddleFinger2_R", "MiddleFinger3_R",
                    "IndexFinger1_R", "IndexFinger2_R", "IndexFinger3_R",
                    "Thumb0_R", "Thumb1_R", "Thumb2_R"
                )
            )
            
            local sceneObjects = for obj in objects collect obj.name
            local missingObjects = for name in objNamesToCheck where findItem sceneObjects name == 0 collect name
            return missingObjects
        ),
        
        -- 创建UI
        fn createUI = (
            try(destroyDialog boneAlignToolRollout) catch()
            
            rollout boneAlignToolRollout "骨骼对齐工具" width:600 height:500
            (
                local theTool
                
                fn setTool t = (
                    theTool = t
                )
                
                groupBox grp_mode "模式选择" pos:[10,10] width:580 height:60
                radioButtons rdo_mode "" pos:[20,30] width:560 height:30 labels:#("标准模型", "赛马娘模型") columns:2
                
                groupBox grp_check "骨骼检测" pos:[10,80] width:580 height:200
                listBox lb_missingObjects "缺失的骨骼：" pos:[20,100] width:270 height:10
                editText et_missingText "" pos:[300,100] width:280 height:170 readOnly:true
                
                groupBox grp_operation "操作" pos:[10,290] width:580 height:200
                button btn_check "检测缺失骨骼" pos:[20,310] width:180 height:30
                button btn_clear "清空显示内容" pos:[210,310] width:180 height:30
                button btn_align "执行骨骼对齐" pos:[400,310] width:180 height:30
                
                on btn_check pressed do (
                    local modelType = if rdo_mode.state == 1 then "standard" else "uma"
                    local missingObjects = theTool.checkMissingObjects modelType
                    lb_missingObjects.items = missingObjects
                    
                    if missingObjects.count > 0 then (
                        et_missingText.text = ""
                        for obj in missingObjects do
                            et_missingText.text += obj + "\n"
                        messageBox "检测到缺失骨骼，请查看详细列表！" title:"检测结果"
                    ) else (
                        messageBox "场景中的骨骼齐全，无缺失！" title:"检测结果"
                        et_missingText.text = ""
                    )
                )
                
                on btn_clear pressed do (
                    lb_missingObjects.items = #()
                    et_missingText.text = ""
                )
                
                on btn_align pressed do (
                    try (
                        if rdo_mode.state == 1 then (
                            theTool.alignAndScaleBones()
                            messageBox "标准模型骨骼对齐完成！" title:"操作成功"
                        ) else (
                            theTool.alignAndScaleBones_UMA()
                            messageBox "赛马娘模型骨骼对齐完成！" title:"操作成功"
                        )
                    ) catch (
                        messageBox ("骨骼对齐失败：" + getCurrentException()) title:"错误"
                    )
                )
            )
            
            createDialog boneAlignToolRollout
            boneAlignToolRollout.setTool this
        ),
        
        -- 初始化函数
        fn initialize = (
            this.createUI()
        )
    )
    
    -- 创建工具实例并初始化
    local theTool = BoneAlignToolStruct()
    theTool.initialize()
)

fn pushModifierControl = (
    global rollout_push
    try(destroyDialog rollout_push)catch()
    rollout rollout_push "Push Modifier Control" width:200 height:100
    (
        edittext edt_push "Push Value:" text:"-0.001" width:120
        button btn_apply "Apply" width:80 height:40
    
        on btn_apply pressed do
        (
            -- 获取输入的推进值
            local pushValue = edt_push.text as float
            
            -- 获取当前场景中的所有可编辑网格/多边形对象，不包括带有"Outline_"前缀的对象
            geoArray = for obj in geometry where ((classOf obj == Editable_Mesh or classOf obj == Editable_Poly) and not matchPattern obj.name pattern:"Outline_*") collect obj
            
            -- 获取当前场景中的所有带有"Outline_"前缀的几何体名称
            outlineNames = for obj in geometry where matchPattern obj.name pattern:"Outline_*" collect obj.name
            
            -- 遍历每个几何体并进行克隆复制
            for geo in geoArray do
            (
                -- 为几何体创建一个新的名字
                local outlineName = "Outline_" + geo.name
    
                -- 如果当前几何体的克隆已经存在则跳过
                if (findItem outlineNames outlineName == 0) then
                (
                    -- 使用copy函数克隆几何体作为复制品
                    clonedGeo = copy geo
                    -- 设置克隆几何体的名称
                    clonedGeo.name = outlineName
                    -- 为带有"Outline_"前缀的克隆添加法线修改器并翻转法线
                    if (matchPattern clonedGeo.name pattern:"Outline_*") then
                    (
                        -- 创建一个法线修改器实例并翻转法线
                        local nm = NormalModifier()
                        nm.flip = true
                        addModifier clonedGeo nm
                        -- 创建一个推力修改器实例并添加到克隆几何体
                        local pm = Push()
                        pm.Push_Value = pushValue
                        addModifier clonedGeo pm
                        -- 禁用双面渲染
                        clonedGeo.backfaceCull = true
                        -- 设置材质为纯黑
                        local blackMat = StandardMaterial()
                        blackMat.diffuse = color 0 0 0
                        clonedGeo.material = blackMat
                    )
                )
            )
            
            -- 关闭对话框
            destroyDialog rollout_push
        )
    )
    createdialog rollout_push
    

)

fn adjustCustomHandModel = (
    try(destroyDialog myToolRollout) catch()
global myToolRollout

-- 定义全局数组来存储选中的辅助对象
global customHandRootBones = #()
global leftHandArmBones = #()
global rightHandArmBones = #()
global leftHandWristBones = #()
global rightHandWristBones = #()
global leftHandPinkyBones = #()
global rightHandPinkyBones = #()
global leftHandMiddleBones = #()
global rightHandMiddleBones = #()
global leftHandMiddleRootBones = #()
global rightHandMiddleRootBones = #()

rollout myToolRollout "一键调整自定义手模" width:300 height:450
(
    -- 创建按钮
    button btnSaveRoot "存取自定义手模根骨骼" pos:[50,30] width:200 height:40
    button btnSaveArms "存取自定义手模左右臂根骨骼" pos:[50,80] width:200 height:40
    button btnSaveWrists "存取自定义手模左右手腕骨" pos:[50,130] width:200 height:40
    button btnSavePinkies "存取自定义手模左右小拇指骨" pos:[50,180] width:200 height:40
    button btnSaveMiddles "存取自定义手模左右中指末端骨" pos:[50,230] width:200 height:40
    button btnSaveMiddleRoots "存取自定义手模左右中指根骨" pos:[50,280] width:200 height:40
    button btnExecute "执行" pos:[50,330] width:200 height:40

    -- 按钮的点击事件
    on btnSaveRoot pressed do
    (
        -- 检查是否有选中的对象
        if selection.count == 0 then
        (
            messageBox "请选择一个辅助对象！" title:"错误"
        )
        else
        (
            -- 遍历所有选中的对象并存储到全局数组中
            for obj in selection do
            (
                appendIfUnique customHandRootBones obj
                format "根骨骼对象 % 已存储。\n" obj.name
            )
            messageBox "根骨骼对象存储完成！" title:"完成"
        )
    )
    
    on btnSaveArms pressed do
    (
        -- 检查是否有选中的对象
        if selection.count == 0 then
        (
            messageBox "请选择一个辅助对象！" title:"错误"
        )
        else
        (
            -- 遍历所有选中的对象并根据名称存储到左右臂数组中
            for obj in selection do
            (
                if matchPattern obj.name pattern:"*Left*" then
                (
                    appendIfUnique leftHandArmBones obj
                    format "左臂根骨骼对象 % 已存储。\n" obj.name
                )
                else if matchPattern obj.name pattern:"*Right*" then
                (
                    appendIfUnique rightHandArmBones obj
                    format "右臂根骨骼对象 % 已存储。\n" obj.name
                )
                else
                (
                    format "对象 % 无法识别为左臂或右臂。\n" obj.name
                )
            )
            messageBox "左右臂根骨骼对象存储完成！" title:"完成"
        )
    )

    on btnSaveWrists pressed do
    (
        -- 检查是否有选中的对象
        if selection.count == 0 then
        (
            messageBox "请选择一个辅助对象！" title:"错误"
        )
        else
        (
            -- 遍历所有选中的对象并根据名称存储到左右手腕数组中
            for obj in selection do
            (
                if matchPattern obj.name pattern:"*Left*" then
                (
                    appendIfUnique leftHandWristBones obj
                    format "左手腕骨骼对象 % 已存储。\n" obj.name
                )
                else if matchPattern obj.name pattern:"*Right*" then
                (
                    appendIfUnique rightHandWristBones obj
                    format "右手腕骨骼对象 % 已存储。\n" obj.name
                )
                else
                (
                    format "对象 % 无法识别为左手腕或右手腕。\n" obj.name
                )
            )
            messageBox "左右手腕骨骼对象存储完成！" title:"完成"
        )
    )

    on btnSavePinkies pressed do
    (
        -- 检查是否有选中的对象
        if selection.count == 0 then
        (
            messageBox "请选择一个辅助对象！" title:"错误"
        )
        else
        (
            -- 遍历所有选中的对象并根据名称后缀存储到左右小拇指数组中
            for obj in selection do
            (
                if matchPattern obj.name pattern:"*_L" then
                (
                    appendIfUnique leftHandPinkyBones obj
                    format "左小拇指骨骼对象 % 已存储。\n" obj.name
                )
                else if matchPattern obj.name pattern:"*_R" then
                (
                    appendIfUnique rightHandPinkyBones obj
                    format "右小拇指骨骼对象 % 已存储。\n" obj.name
                )
                else
                (
                    format "对象 % 无法识别为左小拇指或右小拇指。\n" obj.name
                )
            )
            messageBox "左右小拇指骨骼对象存储完成！" title:"完成"
        )
    )

    on btnSaveMiddles pressed do
    (
        -- 检查是否有选中的对象
        if selection.count == 0 then
        (
            messageBox "请选择一个辅助对象！" title:"错误"
        )
        else
        (
            -- 遍历所有选中的对象并根据名称后缀存储到左右中指末端数组中
            for obj in selection do
            (
                if matchPattern obj.name pattern:"*_L" then
                (
                    appendIfUnique leftHandMiddleBones obj
                    format "左中指末端骨骼对象 % 已存储。\n" obj.name
                )
                else if matchPattern obj.name pattern:"*_R" then
                (
                    appendIfUnique rightHandMiddleBones obj
                    format "右中指末端骨骼对象 % 已存储。\n" obj.name
                )
                else
                (
                    format "对象 % 无法识别为左中指末端或右中指末端。\n" obj.name
                )
            )
            messageBox "左右中指末端骨骼对象存储完成！" title:"完成"
        )
    )

    on btnSaveMiddleRoots pressed do
    (
        -- 检查是否有选中的对象
        if selection.count == 0 then
        (
            messageBox "请选择一个辅助对象！" title:"错误"
        )
        else
        (
            -- 遍历所有选中的对象并根据名称后缀存储到左右中指根骨骼数组中
            for obj in selection do
            (
                if matchPattern obj.name pattern:"*_L" then
                (
                    appendIfUnique leftHandMiddleRootBones obj
                    format "左中指根骨骼对象 % 已存储。\n" obj.name
                )
                else if matchPattern obj.name pattern:"*_R" then
                (
                    appendIfUnique rightHandMiddleRootBones obj
                    format "右中指根骨骼对象 % 已存储。\n" obj.name
                )
                else
                (
                    format "对象 % 无法识别为左中指根骨骼或右中指根骨骼。\n" obj.name
                )
            )
            messageBox "左右中指根骨骼对象存储完成！" title:"完成"
        )
    )

    on btnExecute pressed do
    (
        -- 读取并输出 ValveBiped.Bip01_L_Clavicle 和 ValveBiped.Bip01_R_Clavicle 以及 ValveBiped.ValveBiped 的位置
        leftClavicleName = "ValveBiped.Bip01_L_Clavicle"
        rightClavicleName = "ValveBiped.Bip01_R_Clavicle"
        valveBipedName = "ValveBiped.ValveBiped"
        leftHandName = "ValveBiped.Bip01_L_Hand"
        rightHandName = "ValveBiped.Bip01_R_Hand"
        leftPinkyName = "ValveBiped.Bip01_L_Finger4"
        rightPinkyName = "ValveBiped.Bip01_R_Finger4"
        leftMiddleName = "ValveBiped.Bip01_L_Finger22"
        rightMiddleName = "ValveBiped.Bip01_R_Finger22"
        leftMiddleRootName = "ValveBiped.Bip01_L_Finger2"
        rightMiddleRootName = "ValveBiped.Bip01_R_Finger2"

        leftClavicle = undefined
        rightClavicle = undefined
        valveBiped = undefined
        leftHand = undefined
        rightHand = undefined
        leftPinky = undefined
        rightPinky = undefined
        leftMiddle = undefined
        rightMiddle = undefined
        leftMiddleRoot = undefined
        rightMiddleRoot = undefined

        for obj in objects do
        (
            if obj.name == leftClavicleName then
                leftClavicle = obj
            else if obj.name == rightClavicleName then
                rightClavicle = obj
            else if obj.name == valveBipedName then
                valveBiped = obj
            else if obj.name == leftHandName then
                leftHand = obj
            else if obj.name == rightHandName then
                rightHand = obj
            else if obj.name == leftPinkyName then
                leftPinky = obj
            else if obj.name == rightPinkyName then
                rightPinky = obj
            else if obj.name == leftMiddleName then
                leftMiddle = obj
            else if obj.name == rightMiddleName then
                rightMiddle = obj
            else if obj.name == leftMiddleRootName then
                leftMiddleRoot = obj
            else if obj.name == rightMiddleRootName then
                rightMiddleRoot = obj
        )

        if leftClavicle != undefined then
        (
            format "左锁骨位置: %\n" leftClavicle.position
        )
        else
        (
            format "未找到左锁骨对象: %\n" leftClavicleName
        )

        if rightClavicle != undefined then
        (
            format "右锁骨位置: %\n" rightClavicle.position
        )
        else
        (
            format "未找到右锁骨对象: %\n" rightClavicleName
        )

        if valveBiped != undefined then
        (
            format "ValveBiped.ValveBiped 位置: %\n" valveBiped.position
        )
        else
        (
            format "未找到 ValveBiped.ValveBiped 对象: %\n" valveBipedName
        )

        if leftHand != undefined then
        (
            format "左手位置: %\n" leftHand.position
        )
        else
        (
            format "未找到左手对象: %\n" leftHandName
        )

        if rightHand != undefined then
        (
            format "右手位置: %\n" rightHand.position
        )
        else
        (
            format "未找到右手对象: %\n" rightHandName
        )

        -- 检查是否有存储的左右臂根骨骼对象
        if leftHandArmBones.count != 0 and rightHandArmBones.count != 0 then
        (
            format "左臂根骨骼对象位置：\n"
            for obj in leftHandArmBones do
            (
                format "对象 % 的位置: %\n" obj.name obj.position
            )
            format "右臂根骨骼对象位置：\n"
            for obj in rightHandArmBones do
            (
                format "对象 % 的位置: %\n" obj.name obj.position
            )

            -- 计算缩放比例
            leftRatio = leftClavicle.position.z / leftHandArmBones[1].position.z
            rightRatio = rightClavicle.position.z / rightHandArmBones[1].position.z
            avgRatio = (leftRatio + rightRatio) / 2.0
            format "左臂缩放比例: %\n" leftRatio
            format "右臂缩放比例: %\n" rightRatio
            format "平均缩放比例: %\n" avgRatio

            -- 应用缩放到根骨骼
            for obj in customHandRootBones do
            (
                scale obj [avgRatio, avgRatio, avgRatio]
                format "根骨骼对象 % 已按比例 % 缩放。\n" obj.name avgRatio
            )
            messageBox "根骨骼缩放完成！" title:"完成"
        )
        else
        (
            messageBox "请确保已存储左右臂根骨骼对象！" title:"错误"
        )

        -- 输出手腕骨骼和手腕辅助对象的差值，并根据Y轴移动左右臂根辅助对象
        if leftHandWristBones.count != 0 and leftHand != undefined then
        (
            leftWristDiff = leftHand.position - leftHandWristBones[1].position
            format "左手腕位置差值: %\n" leftWristDiff

            for obj in leftHandArmBones do
            (
                obj.position += [0, leftWristDiff.y, 0]
                format "左臂根骨骼对象 % 已移动到位置: %\n" obj.name obj.position
            )

            leftWristXRatio = leftHand.position.x / leftHandWristBones[1].position.x
            format "左手腕X轴比例: %\n" leftWristXRatio

            -- 缩放左臂根骨骼
            for obj in leftHandArmBones do
            (
                scale obj [leftWristXRatio, leftWristXRatio, leftWristXRatio]
                format "左臂根骨骼对象 % 已按X轴比例 % 缩放。\n" obj.name leftWristXRatio
            )
        )
        else
        (
            format "请确保已存储左手腕骨骼对象，并且已读取左手位置！\n"
        )

        if rightHandWristBones.count != 0 and rightHand != undefined then
        (
            rightWristDiff = rightHand.position - rightHandWristBones[1].position
            format "右手腕位置差值: %\n" rightWristDiff

            for obj in rightHandArmBones do
            (
                obj.position += [0, rightWristDiff.y, 0]
                format "右臂根骨骼对象 % 已移动到位置: %\n" obj.name obj.position
            )

            rightWristXRatio = rightHand.position.x / rightHandWristBones[1].position.x
            format "右手腕X轴比例: %\n" rightWristXRatio

            -- 缩放右臂根骨骼
            for obj in rightHandArmBones do
            (
                scale obj [rightWristXRatio, rightWristXRatio, rightWristXRatio]
                format "右臂根骨骼对象 % 已按X轴比例 % 缩放。\n" obj.name rightWristXRatio
            )
        )
        else
        (
            format "请确保已存储右手腕骨骼对象，并且已读取右手位置！\n"
        )

        -- 读取并输出小拇指骨骼的位置
        if leftPinky != undefined then
        (
            format "缩放后左小拇指位置: %\n" leftPinky.position
        )
        else
        (
            format "未找到左小拇指对象: %\n" leftPinkyName
        )

        if rightPinky != undefined then
        (
            format "缩放后右小拇指位置: %\n" rightPinky.position
        )
        else
        (
            format "未找到右小拇指对象: %\n" rightPinkyName
        )

        -- 读取并输出小拇指辅助对象的位置
        if leftHandPinkyBones.count != 0 then
        (
            format "缩放后左小拇指辅助对象位置：\n"
            for obj in leftHandPinkyBones do
            (
                format "对象 % 的位置: %\n" obj.name obj.position
            )
        )
        else
        (
            format "未存储左小拇指辅助对象！\n"
        )

        if rightHandPinkyBones.count != 0 then
        (
            format "缩放后右小拇指辅助对象位置：\n"
            for obj in rightHandPinkyBones do
            (
                format "对象 % 的位置: %\n" obj.name obj.position
            )
        )
        else
        (
            format "未存储右小拇指辅助对象！\n"
        )

        -- 移动左右手臂辅助对象
        if leftPinky != undefined and leftHandPinkyBones.count != 0 then
        (
            leftPinkyDiffY = leftPinky.position.y - leftHandPinkyBones[1].position.y
            leftPinkyDiffZ = leftPinky.position.z - leftHandPinkyBones[1].position.z
            format "左小拇指Y轴差值: %\n" leftPinkyDiffY
            format "左小拇指Z轴差值: %\n" leftPinkyDiffZ

            for obj in leftHandArmBones do
            (
                obj.position += [0, leftPinkyDiffY, leftPinkyDiffZ]
                format "左臂根骨骼对象 % 已按小拇指Y轴和Z轴差值移动到位置: %\n" obj.name obj.position
            )
        )

        if rightPinky != undefined and rightHandPinkyBones.count != 0 then
        (
            rightPinkyDiffY = rightPinky.position.y - rightHandPinkyBones[1].position.y
            rightPinkyDiffZ = rightPinky.position.z - rightHandPinkyBones[1].position.z
            format "右小拇指Y轴差值: %\n" rightPinkyDiffY
            format "右小拇指Z轴差值: %\n" rightPinkyDiffZ

            for obj in rightHandArmBones do
            (
                obj.position += [0, rightPinkyDiffY, rightPinkyDiffZ]
                format "右臂根骨骼对象 % 已按小拇指Y轴和Z轴差值移动到位置: %\n" obj.name obj.position
            )
        )

        -- 读取并输出中指末端骨骼的位置
        if leftMiddle != undefined then
        (
            format "左中指末端位置: %\n" leftMiddle.position
        )
        else
        (
            format "未找到左中指末端对象: %\n" leftMiddleName
        )

        if rightMiddle != undefined then
        (
            format "右中指末端位置: %\n" rightMiddle.position
        )
        else
        (
            format "未找到右中指末端对象: %\n" rightMiddleName
        )

        -- 读取并输出中指末端辅助对象的位置，并计算比例缩放手臂根骨骼
        if leftMiddle != undefined and leftHandMiddleBones.count != 0 then
        (
            leftMiddleRatio = leftMiddle.position.x / leftHandMiddleBones[1].position.x
            format "左中指末端X轴比例: %\n" leftMiddleRatio

            for obj in leftHandArmBones do
            (
                scale obj [leftMiddleRatio, leftMiddleRatio, leftMiddleRatio]
                format "左臂根骨骼对象 % 已按中指末端X轴比例 % 缩放。\n" obj.name leftMiddleRatio
            )
        )
        else
        (
            format "请确保已存储左中指末端辅助对象，并且已读取左中指末端位置！\n"
        )

        if rightMiddle != undefined and rightHandMiddleBones.count != 0 then
        (
            rightMiddleRatio = rightMiddle.position.x / rightHandMiddleBones[1].position.x
            format "右中指末端X轴比例: %\n" rightMiddleRatio

            for obj in rightHandArmBones do
            (
                scale obj [rightMiddleRatio, rightMiddleRatio, rightMiddleRatio]
                format "右臂根骨骼对象 % 已按中指末端X轴比例 % 缩放。\n" obj.name rightMiddleRatio
            )
        )
        else
        (
            format "请确保已存储右中指末端辅助对象，并且已读取右中指末端位置！\n"
        )

        -- 读取并输出中指根骨骼的位置，并计算差值应用于手臂辅助对象
        if leftMiddleRoot != undefined then
        (
            format "左中指根骨骼位置: %\n" leftMiddleRoot.position
        )
        else
        (
            format "未找到左中指根骨骼对象: %\n" leftMiddleRootName
        )

        if rightMiddleRoot != undefined then
        (
            format "右中指根骨骼位置: %\n" rightMiddleRoot.position
        )
        else
        (
            format "未找到右中指根骨骼对象: %\n" rightMiddleRootName
        )

        -- 读取并输出中指根辅助对象的位置，并应用差值移动手臂根辅助对象
        if leftMiddleRoot != undefined and leftHandMiddleRootBones.count != 0 then
        (
            leftMiddleRootDiffY = leftMiddleRoot.position.y - leftHandMiddleRootBones[1].position.y
            leftMiddleRootDiffX = leftMiddleRoot.position.x - leftHandMiddleRootBones[1].position.x
            format "左中指根骨骼Y轴差值: %\n" leftMiddleRootDiffY
            format "左中指根骨骼X轴差值: %\n" leftMiddleRootDiffX

            for obj in leftHandArmBones do
            (
                obj.position += [leftMiddleRootDiffX, leftMiddleRootDiffY, 0]
                format "左臂根骨骼对象 % 已按中指根骨骼差值移动到位置: %\n" obj.name obj.position
            )
        )
        else
        (
            format "请确保已存储左中指根辅助对象，并且已读取左中指根骨骼位置！\n"
        )

        if rightMiddleRoot != undefined and rightHandMiddleRootBones.count != 0 then
        (
            rightMiddleRootDiffY = rightMiddleRoot.position.y - rightHandMiddleRootBones[1].position.y
            rightMiddleRootDiffX = rightMiddleRoot.position.x - rightHandMiddleRootBones[1].position.x
            format "右中指根骨骼Y轴差值: %\n" rightMiddleRootDiffY
            format "右中指根骨骼X轴差值: %\n" rightMiddleRootDiffX

            for obj in rightHandArmBones do
            (
                obj.position += [rightMiddleRootDiffX, rightMiddleRootDiffY, 0]
                format "右臂根骨骼对象 % 已按中指根骨骼差值移动到位置: %\n" obj.name obj.position
            )
        )
        else
        (
            format "请确保已存储右中指根辅助对象，并且已读取右中指根骨骼位置！\n"
        )

        -- 最后的调整：右手小拇指骨骼与右手小拇指辅助对象的Y值相减，除以2并加到手臂根辅助对象的Y值上
        if rightPinky != undefined and rightHandPinkyBones.count != 0 then
        (
            finalRightPinkyDiffY = (rightPinky.position.y - rightHandPinkyBones[1].position.y) / 2
            format "右手小拇指最终Y轴调整差值: %\n" finalRightPinkyDiffY

            for obj in rightHandArmBones do
            (
                obj.position += [0, finalRightPinkyDiffY, 0]
                format "右臂根骨骼对象 % 已按最终小拇指Y轴调整差值移动到位置: %\n" obj.name obj.position
            )
        )
        else
        (
            format "请确保已存储右小拇指辅助对象，并且已读取右小拇指位置！\n"
        )
    )
)

createDialog myToolRollout

)

fn processAnkleSetup = (
    -- 保存权重数据
    local weightData = #()
    local ankleHelpers = #("Right_ankle", "Left_ankle")
    
    -- 收集受ankle影响的网格及其权重
    for obj in geometry where classOf obj != BoneGeometry do
    (
        if obj.modifiers[#Skin] != undefined do
        (
            local skinMod = obj.modifiers[#Skin]
            local bones = for i = 1 to skinOps.GetNumberBones skinMod collect skinOps.GetBoneName skinMod i 1
            
            -- 检查是否受ankle影响
            local affectedByAnkle = false
            for helper in ankleHelpers do
            (
                if findItem bones helper != 0 do affectedByAnkle = true
            )
            
            if affectedByAnkle do
            (
                local objData = #(obj.name, #())
                local numVerts = skinOps.GetNumberVertices skinMod
                
                -- 按顶点保存权重
                for v = 1 to numVerts do
                (
                    local vertWeights = #()
                    local weightCount = skinOps.GetVertexWeightCount skinMod v
                    
                    for w = 1 to weightCount do
                    (
                        local boneID = skinOps.GetVertexWeightBoneID skinMod v w
                        local weight = skinOps.GetVertexWeight skinMod v w
                        local boneName = skinOps.GetBoneName skinMod boneID 1
                        append vertWeights #(boneName, weight)
                    )
                    append objData[2] vertWeights
                )
                append weightData objData
            )
        )
    )
    
    -- 转换受影响的网格为可编辑网格
    for data in weightData do
    (
        local obj = getNodeByName data[1]
        if obj != undefined do convertToMesh obj
    )
    
    -- 删除原来的ankle辅助骨骼
    local leftAnkle = getNodeByName "Left_ankle"
    local rightAnkle = getNodeByName "Right_ankle"
    if leftAnkle != undefined do delete leftAnkle
    if rightAnkle != undefined do delete rightAnkle
    
    -- 处理左脚
    local leftFoot = getNodeByName "ValveBiped.Bip01_L_Foot"
    local leftToe = getNodeByName "ValveBiped.Bip01_L_Toe0"
    local leftToeDummy = getNodeByName "Left toe"
    if leftFoot != undefined do
    (
        -- 移动到指定位置
        leftFoot.pos.z = 2.514
        -- 复制并重命名为新的ankle
        local newLeftAnkle = copy leftFoot
        newLeftAnkle.name = "Left_ankle"
        -- 重新设置层级关系
        local leftCalf = getNodeByName "ValveBiped.Bip01_L_Calf"
        if leftCalf != undefined do
        (
            leftFoot.parent = leftCalf
            newLeftAnkle.parent = leftCalf
            if leftToe != undefined do leftToe.parent = leftFoot
            if leftToeDummy != undefined do leftToeDummy.parent = newLeftAnkle
        )
    )
    
    -- 处理右脚
    local rightFoot = getNodeByName "ValveBiped.Bip01_R_Foot"
    local rightToe = getNodeByName "ValveBiped.Bip01_R_Toe0"
    local rightToeDummy = getNodeByName "Right toe"
    if rightFoot != undefined do
    (
        -- 移动到指定位置
        rightFoot.pos.z = 2.514
        -- 复制并重命名为新的ankle
        local newRightAnkle = copy rightFoot
        newRightAnkle.name = "Right_ankle"
        -- 重新设置层级关系
        local rightCalf = getNodeByName "ValveBiped.Bip01_R_Calf"
        if rightCalf != undefined do
        (
            rightFoot.parent = rightCalf
            newRightAnkle.parent = rightCalf
            if rightToe != undefined do rightToe.parent = rightFoot
            if rightToeDummy != undefined do rightToeDummy.parent = newRightAnkle
        )
    )
    
    -- 还原权重
    for data in weightData do
    (
        local obj = getNodeByName data[1]
        if obj != undefined do
        (
            -- 添加新的蒙皮修改器
            local skinMod = Skin()
            addModifier obj skinMod
            
            -- 添加所有骨骼
            local allBones = ($'*' as array)
            for bone in allBones where (classOf bone == BoneGeometry or classOf bone == Point or classOf bone == Dummy) do
            (
                skinOps.addBone skinMod bone 0
            )
            
            -- 还原权重
            local numVerts = skinOps.GetNumberVertices skinMod
            for v = 1 to numVerts do
            (
                local vertWeights = data[2][v]
                if vertWeights != undefined and vertWeights.count > 0 then
                (
                    local boneIDs = #()
                    local weights = #()
                    
                    for w in vertWeights do
                    (
                        local boneName = w[1]
                        local weight = w[2]
                        
                        for i = 1 to skinOps.GetNumberBones skinMod do
                        (
                            if (skinOps.GetBoneName skinMod i 1) == boneName do
                            (
                                append boneIDs i
                                append weights weight
                                exit
                            )
                        )
                    )
                    
                    if boneIDs.count > 0 and weights.count > 0 do
                    (
                        try
                        (
                            skinOps.ReplaceVertexWeights skinMod v boneIDs weights
                        )
                        catch()
                    )
                )
            )
        )
    )
    
    messageBox "ankle设置处理完成！" title:"完成"
)

fn footActionScript = (
    try (destroyDialog footScriptDialog) catch()

global footHelpers = #()

fn setHelpers arrayHelper caption =
(
    arrayHelper = selection as array
    messageBox (caption + " 已选择 " + arrayHelper.count as string + " 个对象")
    return arrayHelper
)

fn generateOutputText footAngle =
(
    local outputText = ""
    local footBones = #("ValveBiped.Bip01_L_Foot", "ValveBiped.Bip01_R_Foot")
    local leftHelpers = for obj in footHelpers where obj.position.x > 0 collect obj.name
    local rightHelpers = for obj in footHelpers where obj.position.x <= 0 collect obj.name

    for i = 1 to footBones.count do
    (
        outputText += "$NekoDriverBone \"" + footBones[i] + "\" {\n"
        outputText += "\tpose \"Foot_VRD.smd\"\n"
        outputText += "\t  trigger 60 0\n"
        outputText += "\t  trigger 60 10\n"
        outputText += "\t  trigger 60 20\n"
        outputText += "\t  trigger 60 30\n"

        if footBones[i] == "ValveBiped.Bip01_L_Foot" then
        (
            for name in leftHelpers do
            (
                outputText += "\t  " + name + "\n"
            )
        )
        else if footBones[i] == "ValveBiped.Bip01_R_Foot" then
        (
            for name in rightHelpers do
            (
                outputText += "\t  " + name + "\n"
            )
        )

        outputText += "}\n\n"
    )
    return outputText
)

rollout footScriptDialog "足部动作脚本"
(
    spinner spnFootAngle "足辅助对象旋转角度：" range:[0, 180, 60] type:#integer

    button btnSelectFoot "拾取足辅助对象" width:200 align:#center
    button btnExecute "执行" width:200 align:#center
    button btnGenerateOutput "生成输出文本" width:200 align:#center
    button btnExport "导出SMD" width:200 align:#center
    button btnProcessAnkle "处理Ankle设置" width:200 align:#center
    editText edtOutput "" width:280 height:150 readOnly:true -- 文本显示框

    on btnSelectFoot pressed do
    (
        footHelpers = setHelpers footHelpers "足辅助对象"
    )

    on btnExecute pressed do
    (
        local footBones = #("ValveBiped.Bip01_L_Foot", "ValveBiped.Bip01_R_Foot")
        local footAngle = spnFootAngle.value

        if footHelpers.count > 0 then
        (
            -- 开始动画模式
            animate on
            (
                -- 在第0帧创建默认关键帧
                sliderTime = 0
                for obj in footHelpers do
                (
                    obj.rotation.controller = Euler_XYZ()
                    addNewKey obj.rotation.controller 0
                )
                for boneName in footBones do
                (
                    local obj = getNodeByName boneName
                    if obj != undefined do
                    (
                        obj.rotation.controller = Euler_XYZ()
                        addNewKey obj.rotation.controller 0
                    )
                )

                -- 在第10帧旋转足辅助对象和骨骼
                sliderTime = 10
                for obj in footHelpers do
                (
                    rotate obj (angleaxis (-footAngle) [1, 0, 0])
                    addNewKey obj.rotation.controller 10
                )
                for boneName in footBones do
                (
                    local obj = getNodeByName boneName
                    if obj != undefined do
                    (
                        rotate obj (angleaxis -60 [1, 0, 0])
                        addNewKey obj.rotation.controller 10
                    )
                )

                -- 在第20帧旋转足辅助对象和骨骼
                sliderTime = 20
                for obj in footHelpers do
                (
                    rotate obj (angleaxis footAngle [1, 0, 0])
                    addNewKey obj.rotation.controller 20
                )
                for boneName in footBones do
                (
                    local obj = getNodeByName boneName
                    if obj != undefined do
                    (
                        rotate obj (angleaxis 60 [1, 0, 0])
                        addNewKey obj.rotation.controller 20
                    )
                )

                -- 在第30帧旋转足辅助对象和骨骼
                sliderTime = 30
                for obj in footHelpers do
                (
                    if matchPattern obj.name pattern:"*R*" then
                    (
                        rotate obj (angleaxis -footAngle [0, 1, 0])
                    )
                    else if matchPattern obj.name pattern:"*L*" then
                    (
                        rotate obj (angleaxis footAngle [0, 1, 0])
                    )
                    addNewKey obj.rotation.controller 30
                )
                for boneName in footBones do
                (
                    local obj = getNodeByName boneName
                    if obj != undefined do
                    (
                        if boneName == "ValveBiped.Bip01_L_Foot" then
                            rotate obj (angleaxis -60 [0, 0, 1])
                        else if boneName == "ValveBiped.Bip01_R_Foot" then
                            rotate obj (angleaxis 60 [0, 0, 1])
                        addNewKey obj.rotation.controller 30
                    )
                )
            )

            messageBox "已完成足部动作的关键帧设置。" title:"操作完成"
        )
        else
        (
            messageBox "请先选择足辅助对象。"
        )
    )

    on btnGenerateOutput pressed do
    (
        local footAngle = spnFootAngle.value
        local outputText = generateOutputText footAngle
        edtOutput.text = outputText
    )

    on btnExport pressed do
    (
        local exportPath = getSaveFileName caption:"选择导出路径" types:"SMD(*.smd)|*.smd|所有文件(*.*)|*.*"
        if exportPath != undefined do
        (
            local result = WBSMDExport exportPath false 1 false 1 0 30 false false false false
            if result == "OK" then
                messageBox "导出成功！" title:"导出完成"
            else
                messageBox ("导出失败：" + result) title:"导出错误"
        )
    )

    on btnProcessAnkle pressed do
    (
        processAnkleSetup()
    )
)

-- 创建对话框
createDialog footScriptDialog 300 400

)

fn OpenRenamePresetManager = 
(
    global RenamePresetRollout
    global CreateMappingRollout
    global renamePresetFilePath = ((getDir #userScripts) + "\\RenamePresets.ini")
    global renameMappings = #()
    
    try(destroyDialog RenamePresetRollout) catch()
    try(destroyDialog CreateMappingRollout) catch()
    
    rollout CreateMappingRollout "创建重命名映射" width:400
    (
        listbox lbxMappings "当前映射:" height:15
        group "添加映射"
        (
            editText edtOldName "原始名称:" width:360
            editText edtNewName "新名称:" width:360
            button btnAdd "添加映射" width:170
            button btnRemove "删除选中" width:170
        )
        button btnDone "完成" width:360
        
        fn updateList =
        (
            local items = #()
            for m in renameMappings do
            (
                append items (m[1] + " -> " + m[2])
            )
            lbxMappings.items = items
        )
        
        on CreateMappingRollout open do
        (
            updateList()
        )
        
        on btnAdd pressed do
        (
            if edtOldName.text != "" and edtNewName.text != "" then
            (
                append renameMappings #(edtOldName.text, edtNewName.text)
                updateList()
                edtOldName.text = ""
                edtNewName.text = ""
            )
        )
        
        on btnRemove pressed do
        (
            local sel = lbxMappings.selection
            if sel > 0 do
            (
                deleteItem renameMappings sel
                updateList()
            )
        )
        
        on btnDone pressed do
        (
            destroyDialog CreateMappingRollout
        )
    )

    rollout RenamePresetRollout "重命名预设管理器" width:300
    (
        dropdownList ddlPresets "预设列表:" items:#() width:280
        editText edtNewPreset "新预设名称:" text:"" width:280
        
        group "操作"
        (
            button btnSetMappings "设置重命名映射" width:135
            button btnApply "应用预设" width:135
            button btnSave "保存预设" width:135
            button btnDelete "删除预设" width:135
        )
        
        fn savePreset presetName mappings =
        (
            local str = ""
            for m in mappings do
            (
                str += m[1] + "," + m[2] + ";"
            )
            setINISetting renamePresetFilePath presetName "Mappings" str
        )

        fn loadPreset presetName =
        (
            local mappings = #()
            local mappingsStr = getINISetting renamePresetFilePath presetName "Mappings"
            local pairs = filterString mappingsStr ";"
            for p in pairs where p.count > 0 do
            (
                local data = filterString p ","
                if data.count == 2 do
                (
                    append mappings #(data[1], data[2])
                )
            )
            mappings
        )

        fn getAllPresets =
        (
            local presets = #()
            if doesFileExist renamePresetFilePath then
            (
                local sections = getINISetting renamePresetFilePath
                for s in sections do append presets s
            )
            presets
        )

        fn refreshPresetList =
        (
            ddlPresets.items = getAllPresets()
        )
        
        fn applyRenaming mappings =
        (
            for obj in objects do
            (
                for mapping in mappings do
                (
                    if obj.name == mapping[1] do
                    (
                        obj.name = mapping[2]
                        format "已重命名对象: % -> %\n" mapping[1] mapping[2]
                    )
                )
            )
        )
        
        on RenamePresetRollout open do
        (
            refreshPresetList()
        )
        
        on btnSetMappings pressed do
        (
            createDialog CreateMappingRollout
        )
        
        on btnApply pressed do
        (
            if ddlPresets.selected != undefined do
            (
                local presetData = loadPreset ddlPresets.selected
                if presetData.count > 0 then
                (
                    applyRenaming presetData
                    messageBox ("已应用预设: " + ddlPresets.selected) title:"成功"
                )
                else
                    messageBox "预设数据无效!" title:"错误"
            )
        )
        
        on btnSave pressed do
        (
            local newName = edtNewPreset.text
            if newName.count > 0 then
            (
                if renameMappings.count > 0 then
                (
                    savePreset newName renameMappings
                    refreshPresetList()
                    messageBox ("已保存预设: " + newName) title:"成功"
                )
                else
                    messageBox "请先设置重命名映射!" title:"错误"
            )
            else
                messageBox "请输入预设名称!" title:"错误"
        )
        
        on btnDelete pressed do
        (
            if ddlPresets.selected != undefined do
            (
                local presetToDelete = ddlPresets.selected  -- 保存要删除的预设名称
                delINISetting renamePresetFilePath presetToDelete
                refreshPresetList()
                messageBox ("已删除预设: " + presetToDelete) title:"成功"
            )
        )
    )

    createDialog RenamePresetRollout
) 

fn FastJigglebones = (
    try(destroyDialog JiggleBoneUI) catch()

rollout JiggleBoneUI "快速编写飘动骨骼" width:400 height:460
(
    label lbl1 "选择多个父级辅助对象" pos:[10,10]
    
    label lbl2 "重力值" pos:[10,40]
    spinner spnGravity "重力:" range:[0,10000,500] pos:[150,40] width:100 type:#float
    
    label lbl3 "飘动约束" pos:[10,70]
    spinner spnAngleConstraint "约束:" range:[0,180,20] pos:[150,70] width:100 type:#float
    
    label lbl4 "重力递减值" pos:[10,100]
    spinner spnGravityDecrement "重力递减:" range:[0,1000,50] pos:[150,100] width:100 type:#float
    
    label lbl5 "约束递减值" pos:[10,130]
    spinner spnConstraintDecrement "约束递减:" range:[0,50,2.5] pos:[150,130] width:100 type:#float

    checkbox chkBigBreast "大胸参数" pos:[10,160] width:150

    label lbl6 "胸部对象关键词" pos:[10,190]
    editText txtBreastKeyword "" pos:[150,190] width:240 height:20

    checkbox chkSkirt "裙子参数" pos:[10,220] width:150 -- 裙子参数

    button btnGenerate "生成飘动骨骼代码" pos:[10,250] width:380 height:30
    
    editText txtOutput "" pos:[10,290] width:380 height:170 style:#multiline
    
    -- 修改递归函数，添加层级信息
    fn getAllChildrenByLevel obj startLevel:1 = 
    (
        -- 返回格式为 #(#(obj, level), ...)
        local result = #()
        
        -- 获取直接子对象
        local directChildren = for child in objects where child.parent == obj collect child
        
        -- 将当前层级的所有直接子对象添加到结果中
        for child in directChildren do
        (
            append result #(child, startLevel)
            -- 递归处理每个子对象，层级+1
            local subChildren = getAllChildrenByLevel child startLevel:(startLevel + 1)
            result += subChildren
        )
        
        return result
    )
    
    on btnGenerate pressed do
    (
        if selection.count < 1 then
        (
            messageBox "请至少选择一个父级辅助对象!"
        )
        else
        (
            local initialGravity = spnGravity.value
            local initialAngleConstraint = spnAngleConstraint.value
            local gravityDecrement = spnGravityDecrement.value
            local constraintDecrement = spnConstraintDecrement.value
            local useBigBreast = chkBigBreast.checked
            local breastKeyword = trimRight txtBreastKeyword.text -- 去除关键词末尾的空格
            local useSkirt = chkSkirt.checked -- 检查是否启用了裙子参数
            local resultText = ""
            local processedObjects = #() -- 用于存储已经处理过的对象名称
            
            -- 遍历所有选中的父级对象
            for j = 1 to selection.count do
            (
                local parentObject = selection[j]
                local allObjectsWithLevels = #()
                
                -- 获取所有子对象及其层级信息
                allObjectsWithLevels = getAllChildrenByLevel parentObject
                -- 将父对象添加到列表开头，层级为0
                insertItem #(parentObject, 0) allObjectsWithLevels 1
                
                -- 为每个对象生成独立的递减参数
                for item in allObjectsWithLevels do
                (
                    local obj = item[1]
                    local level = item[2]
                    local objectName = obj.name
                    
                    -- 检查对象是否已经处理过
                    if not (findItem processedObjects objectName > 0) then
                    (
                        -- 如果勾选了"裙子参数"，所有对象都会按固定裙子参数处理
                        if useSkirt then
                        (
                            -- 固定的裙子参数，不应用递减
                            -- 参数来源于B站jjzy0593大佬
                            resultText += "$jigglebone \"" + objectName + "\"\n"
                            resultText += "{\n"
                            resultText += "\tis_flexible\n"
                            resultText += "\t{\n"
                            resultText += "\t\tlength 20\n"
                            resultText += "\t\ttip_mass 0\n"
                            resultText += "\t\tpitch_stiffness 150\n"
                            resultText += "\t\tpitch_damping 7\n"
                            resultText += "\t\tyaw_stiffness 50\n"
                            resultText += "\t\tyaw_damping 7\n"
                            resultText += "\t\tallow_length_flex\n"
                            resultText += "\t\talong_stiffness 100\n"
                            resultText += "\t\talong_damping 50\n"
                            resultText += "\t\tangle_constraint 25\n"
                            resultText += "\t}\n"
                            resultText += "}\n\n"
                        )
                        -- 如果输入了有效的胸部关键词，并且对象名称包含该关键词，才进行胸部参数生成
                        else if breastKeyword != "" and matchPattern objectName pattern:("*" + breastKeyword + "*") then
                        (
                            local side = if obj.position.x < 0 then "L" else "R"
                            
                            -- 检查是否勾选了大胸参数
                            if useBigBreast then
                            (
                                -- 生成大胸参数
                                resultText += "$jigglebone \"" + objectName + "\"\n"
                                resultText += "{\n"
                                resultText += "\tis_flexible\n"
                                resultText += "\t{\n"
                                resultText += "\t\tlength 20\n"
                                resultText += "\t\ttip_mass 0\n"
                                resultText += "\t\tpitch_stiffness 200\n"
                                resultText += "\t\tpitch_damping 5\n"
                                resultText += "\t\tyaw_stiffness 200\n"
                                resultText += "\t\tyaw_damping 5\n"
                                resultText += "\t\tallow_length_flex\n"
                                resultText += "\t\talong_stiffness 100\n"
                                resultText += "\t\talong_damping 0\n"
                                resultText += "\t\tangle_constraint 20.000001\n"
                                resultText += "\t}\n"
                                resultText += "}\n\n"
                            )
                            else
                            (
                                -- 生成普通胸参数
                                resultText += "$JiggleBone \"" + objectName + "\"\n"
                                resultText += "{\n"
                                resultText += "\tis_flexible\n"
                                resultText += "\t{\n"
                                resultText += "\t\tlength 5\n"
                                resultText += "\t\ttip_mass 10\n"
                                resultText += "\t\tpitch_stiffness 50\n"
                                resultText += "\t\tpitch_damping 10\n"
                                resultText += "\t\tyaw_stiffness 50\n"
                                resultText += "\t\tyaw_damping 10\n"
                                resultText += "\t\tallow_length_flex\n"
                                resultText += "\t\talong_stiffness 100\n"
                                resultText += "\t\talong_damping 0\n"
                                resultText += "\t\tangle_constraint 3\n"
                                resultText += "\t}\n"
                                resultText += "\thas_base_spring\n"
                                resultText += "\t{\n"
                                resultText += "\t\tbase_mass 0\n"
                                resultText += "\t\tstiffness 100\n"
                                resultText += "\t\tdamping 3\n"
                                resultText += "\t\tleft_constraint -0.3 0.3\n"
                                resultText += "\t\tleft_friction 0\n"
                                resultText += "\t\tup_constraint -0.3 0.3\n"
                                resultText += "\t\tup_friction 0\n"
                                resultText += "\t\tforward_constraint -0.3 0.3\n"
                                resultText += "\t\tforward_friction 0\n"
                                resultText += "\t}\n"
                                resultText += "}\n\n"
                            )
                        )
                        else
                        (
                            -- 常规对象处理，应用递减参数
                            local adjustedGravity = initialGravity - level * gravityDecrement
                            local adjustedConstraint = initialAngleConstraint - level * constraintDecrement
                        
                            -- 防止值变成负数
                            if adjustedGravity < 0 then adjustedGravity = 0
                            if adjustedConstraint < 0 then adjustedConstraint = 0
                            
                            resultText += "$JiggleBone \"" + objectName + "\"\n"
                            resultText += "{\n"
                            resultText += "\tis_flexible\n"
                            resultText += "\t{\n"
                            resultText += "\t\tlength 30\n"
                            resultText += "\t\ttip_mass " + adjustedGravity as string + "\n"
                            resultText += "\t\tpitch_stiffness 50\n"
                            resultText += "\t\tpitch_damping 7\n"
                            resultText += "\t\tyaw_stiffness 50\n"
                            resultText += "\t\tyaw_damping 7\n"
                            resultText += "\t\talong_stiffness 100\n"
                            resultText += "\t\talong_damping 0\n"
                            resultText += "\t\tangle_constraint " + adjustedConstraint as string + "\n"
                            resultText += "\t}\n"
                            resultText += "}\n\n"
                        )
                        
                        -- 将对象名称加入已处理列表
                        append processedObjects objectName
                    )
                )
            )
            
            txtOutput.text = resultText
        )
    )
)

createDialog JiggleBoneUI

    
)

fn WeightMerging =
(
    rollout WeightMergeRollout "权重合并工具" width:400 height:500
(
    group "合并模式"
    (
        radiobuttons rdoMode labels:#("合并到指定骨骼", "合并到父级") across:2 align:#center
        label lblStatus "" align:#center
    )
    
    group ""
    (
        listbox lstSourceBones "源骨骼列表:" height:15 width:170 across:2
        listbox lstTargetBones "待合并骨骼列表:" height:15 width:170
        
        button btnPickSource "拾取源骨骼" width:120 height:25 across:2 align:#center offset:[0,5]
        button btnPickTarget "拾取待合并骨骼" width:120 height:25 align:#center offset:[0,5]
        
        button btnClearSource "清空源列表" width:120 height:25 across:2 align:#center offset:[0,5]
        button btnClearTarget "清空待合并列表" width:120 height:25 align:#center offset:[0,5]
    )
    
    button btnExecute "执行合并" width:380 height:30 align:#center offset:[0,5]
    
    local sourceBones = #()
    local targetBones = #()
    
    fn isValidObject obj = (
        if obj == undefined do return false
        -- 打印对象类型以便调试
        format "Object: % Type: %\n" obj.name (classOf obj)
        -- 修改类型判断逻辑
        local validTypes = #(BoneGeometry, Biped_Object, Point, Dummy)
        local objClass = classOf obj
        -- 对于Helper类型的对象需要特殊处理
        if (superClassOf obj) == Helper do objClass = Dummy
        return findItem validTypes objClass > 0
    )
    
    fn updateUI =
    (
        -- 更新源骨骼列表状态
        lstSourceBones.enabled = (rdoMode.state == 1)
        btnPickSource.enabled = (rdoMode.state == 1)
        btnClearSource.enabled = (rdoMode.state == 1)
        
        btnExecute.enabled = if rdoMode.state == 1 then
            (sourceBones.count > 0 and targetBones.count > 0)
        else
            (targetBones.count > 0)
            
        -- 更新状态提示
        lblStatus.text = case of (
            (targetBones.count == 0): "请添加待合并骨骼"
            (rdoMode.state == 1 and sourceBones.count == 0): "请选择源骨骼"
            (btnExecute.enabled): "准备就绪"
            default: ""
        )
    )
    
    fn mergeToBone sources targets =
    (
        undo on
        (
            for source in sources do (
                for target in targets do
                (
                    format "正在处理: 源骨骼 = %, 目标骨骼 = %\n" source.name target.name
                    
                    -- 获取所有受该骨骼影响的蒙皮修改器
                    local affectedSkins = #()
                    for obj in objects do
                    (
                        if obj.modifiers.count > 0 do
                        (
                            for mod in obj.modifiers do
                            (
                                if classOf mod == Skin do
                                (
                                    try (
                                        -- 打印更多调试信息
                                        format "检查对象: % (类型: %)\n" obj.name (classOf obj)
                                        format "检查修改器: % (类型: %)\n" mod.name (classOf mod)
                                        
                                        -- 获取所有骨骼
                                        local boneCount = skinOps.GetNumberBones mod
                                        format "蒙皮中的骨骼数量: %\n" boneCount
                                        
                                        -- 打印所有骨骼名称
                                        for i = 1 to boneCount do
                                        (
                                            local boneName = skinOps.GetBoneName mod i 1
                                            format "骨骼 %: %\n" i boneName
                                        )
                                        
                                        -- 检查目标骨骼是否在蒙皮中
                                        for i = 1 to boneCount do
                                        (
                                            if (skinOps.GetBoneName mod i 1) == target.name do
                                            (
                                                format "找到受影响的蒙皮: % (目标骨骼索引: %)\n" obj.name i
                                                appendIfUnique affectedSkins #(obj, mod)
                                            )
                                        )
                                    ) catch (
                                        format "处理对象 % 时出错: %\n" obj.name (getCurrentException())
                                    )
                                )
                            )
                        )
                    )
                    
                    -- 转移权重
                    for skinData in affectedSkins do
                    (
                        try (
                            local obj = skinData[1]
                            local skin = skinData[2]
                            
                            -- 获取骨骼索引
                            local boneCount = skinOps.GetNumberBones skin
                            local sourceIndex = 0
                            local targetIndex = 0
                            
                            for i = 1 to boneCount do
                            (
                                local boneName = skinOps.GetBoneName skin i 1
                                if boneName == source.name do sourceIndex = i
                                if boneName == target.name do targetIndex = i
                            )
                            
                            if sourceIndex != 0 and targetIndex != 0 then
                            (
                                -- 获取所有顶点数量
                                local vertCount = obj.numverts
                                
                                -- 遍历所有顶点
                                for v = 1 to vertCount do
                                (
                                    local weightCount = skinOps.GetVertexWeightCount skin v
                                    
                                    -- 检查顶点是否受目标骨骼影响
                                    for w = 1 to weightCount do
                                    (
                                        if (skinOps.GetVertexWeightBoneID skin v w) == targetIndex do
                                        (
                                            -- 直接替换为源骨骼的权重
                                            skinOps.ReplaceVertexWeights skin v #(sourceIndex) #(1.0)
                                            exit -- 找到后就跳出内层循环
                                        )
                                    )
                                )
                            )
                            
                        ) catch (
                            format "转移权重时出错: %\n" (getCurrentException())
                        )
                    )
                    
                    -- 处理骨骼层级关系
                    local children = for child in target.children collect child
                    for child in children do
                    (
                        -- 将子骨骼重新链接到源骨骼或父级骨骼
                        if rdoMode.state == 1 then
                            child.parent = source
                        else
                            child.parent = target.parent
                    )
                    
                    -- 删除目标骨骼
                    try (
                        delete target
                    ) catch (
                        format "删除骨骼时出错: %\n" (getCurrentException())
                    )
                )
            )
        )
    )
    
    fn mergeToParent targets =
    (
        undo on
        (
            for target in targets do
            (
                local parent = target.parent
                if parent != undefined do
                (
                    mergeToBone #(parent) #(target)
                )
            )
        )
    )
    
    on rdoMode changed state do
    (
        if state == 2 do
        (
            sourceBones = #()
            lstSourceBones.items = #()
        )
        updateUI()
    )
    
    on btnPickSource pressed do
    (
        local sel = getCurrentSelection()
        for obj in sel do (
            if isValidObject obj do (
                appendIfUnique sourceBones obj
            )
        )
        lstSourceBones.items = for bone in sourceBones collect bone.name
        updateUI()
    )
    
    on btnClearSource pressed do
    (
        sourceBones = #()
        lstSourceBones.items = #()
        updateUI()
    )
    
    on btnPickTarget pressed do
    (
        local sel = getCurrentSelection()
        if sel.count == 0 then
        (
            messageBox "请先在场景中选择对象！" title:"提示"
            return()
        )
        
        local addedCount = 0
        for obj in sel do (
            if isValidObject obj then
            (
                if (appendIfUnique targetBones obj) do
                    addedCount += 1
            )
        )
        
        -- 更新列表显示
        lstTargetBones.items = for bone in targetBones collect bone.name
        
        -- 提示添加结果
        if addedCount > 0 then
            format "成功添加 % 个对象到待合并列表\n" addedCount
        else
            messageBox "没有添加任何有效对象！\n请确保选择的是骨骼或辅助对象。" title:"提示"
            
        updateUI()
    )
    
    on btnClearTarget pressed do
    (
        targetBones = #()
        lstTargetBones.items = #()
        updateUI()
    )
    
    on btnExecute pressed do
    (
        if rdoMode.state == 1 then
        (
            mergeToBone sourceBones targetBones
        )
        else
        (
            mergeToParent targetBones
        )
        
        -- 清除列表
        sourceBones = #()
        targetBones = #()
        lstSourceBones.items = #()
        lstTargetBones.items = #()
        updateUI()
    )
)

createDialog WeightMergeRollout

)

fn selectObjectsExcludingList = (
    -- 定义要排除的对象名称列表
excludedNames = #(
    "Armature", "Hips", "Spine", "Chest", "Right shoulder", "Right arm", "ZArmTwist_R",
    "Right_elbow", "ZHandTwist_R", "Right wrist", "MiddleFinger1_R", "MiddleFinger2_R",
    "MiddleFinger3_R", "Thumb0_R", "Thumb1_R", "Thumb2_R", "IndexFinger1_R", "IndexFinger2_R",
    "IndexFinger3_R", "LittleFinger1_R", "LittleFinger2_R", "LittleFinger3_R", "RingFinger1_R",
    "RingFinger2_R", "RingFinger3_R", "Right leg", "Right knee", "Right_ankle", "Right toe",
    "Neck", "Head",
    "Left shoulder", "Left arm", "ZArmTwist_L", "Left_elbow", "ZHandTwist_L", "Left wrist",
    "MiddleFinger1_L", "MiddleFinger2_L", "MiddleFinger3_L", "Thumb0_L", "Thumb1_L", "Thumb2_L",
    "IndexFinger1_L", "IndexFinger2_L", "IndexFinger3_L", "LittleFinger1_L", "LittleFinger2_L",
    "LittleFinger3_L", "RingFinger1_L", "RingFinger2_L", "RingFinger3_L", "Left leg", "Left knee",
    "Left_ankle", "Left toe"
)

-- 清空当前选择
clearSelection()

-- 遍历场景中的所有对象
for obj in objects do (
    -- 如果对象名称不在排除列表中
    if not (findItem excludedNames obj.name > 0) then (
        -- 输出调试信息
        format "Selecting object: %\n" obj.name
        -- 选择对象
        selectMore obj
    ) else (
        -- 输出调试信息
        format "Skipping object: %\n" obj.name
    )
)

-- 输出完成信息
format "Selection completed.\n"
)

-- 定义子界面的rollout
rollout buttonsRollout "工具" width:600 height:1000 (
    button btnScript1 "一键导出" pos:[10,710] width:580 height:40
    button btnScript2 "T-Pose预设管理器" pos:[10,160] width:580 height:40
    button btnScript3 "一键VRD动作" pos:[10,410] width:580 height:40
    button btnScript4 "一键变形开关" pos:[10,60] width:580 height:40
    button btnScript5 "一键表情" pos:[10,310] width:580 height:40
    button btnScript6 "一键嫁接" pos:[10,260] width:580 height:40
    button btnScript7 "一键选中骨骼" pos:[10,110] width:580 height:40
    button btnScript8 "一键对骨" pos:[10,210] width:580 height:40
    button btnScript9 "智能描边" pos:[10,360] width:580 height:40
    button btnScript10 "一键手模调整" pos:[10,510] width:580 height:40
    button btnScript11 "一键足VRD动作" pos:[10,460] width:580 height:40
    button btnScript12 "重命名预设管理器" pos:[10,10] width:580 height:40
    button btnScript13 "快速飘动编写" pos:[10,560] width:580 height:40
    button btnScript21 "权重合并" pos:[10,610] width:580 height:40
    button btnScript22 "骨骼/辅助对象名称输出" pos:[10,660] width:580 height:40

    on btnScript1 pressed do (
        exportGeometryWithAllBonesAndHelpers()
    )
    on btnScript2 pressed do (
        TPosePresetManager()
    )
    on btnScript3 pressed do (
        vrdActionScript()
    )
    on btnScript4 pressed do (
        toggleSkinDeform()
    )
    on btnScript5 pressed do (
        setMorpherKeyframes()
    )
    on btnScript6 pressed do (
        createSkirtHelperDialog()
    )
    on btnScript7 pressed do (
        selectObjectsExcludingList()
    )
    on btnScript8 pressed do (
        BoneAlignmentToolManager()
    )
    on btnScript9 pressed do (
        pushModifierControl()
    )
    on btnScript10 pressed do (
        adjustCustomHandModel()
    )
    on btnScript11 pressed do (
        footActionScript()
    )
    on btnScript12 pressed do (
        OpenRenamePresetManager()
    )
    on btnScript13 pressed do (
        FastJigglebones()
    )
    on btnScript21 pressed do (
        WeightMerging()
    )
    on btnScript22 pressed do (
        BoneNameLister()
    )
)

-- 定义主界面的rollout
rollout mainRollout "一键工具箱" width:640 height:1100 (
    label lblInfo "制作者：B站メジロ_McQueen/ChatGPT4o/Deepseek/Claude3.5-Cursor" pos:[10,10] width:620 height:30
    subRollout subRolloutContainer "工具" pos:[10,50] width:620 height:1000
)

-- 创建主界面对话框并添加子界面
try (destroyDialog mainDialog) catch()
mainDialog = newRolloutFloater "一键工具箱" 640 1100
addRollout mainRollout mainDialog

-- 将子界面添加到 subRollout 容器中
addSubRollout mainRollout.subRolloutContainer buttonsRollout
