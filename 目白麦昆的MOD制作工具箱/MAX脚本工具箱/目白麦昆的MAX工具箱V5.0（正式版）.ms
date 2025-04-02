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
    
    -- 快速导出静态表情网格的独立函数
    fn exportFaceEffects =
    (
        local exportPath = getSavePath caption:"选择表情网格导出路径"
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
            
            -- 查找名称包含fe1/fe2/fe3/fe4的网格
            local feMeshes = #()
            local feNames = #("fe1", "fe2", "fe3", "fe4")
            
            for i = 1 to feNames.count do
            (
                local foundFE = false
                for geo in allGeometries do
                (
                    if matchPattern geo.name pattern:("*" + feNames[i] + "*") ignoreCase:true then
                    (
                        append feMeshes geo
                        foundFE = true
                        exit -- 找到第一个匹配的就跳出
                    )
                )
                
                -- 如果没找到对应名称的网格，添加一个空值占位
                if not foundFE do append feMeshes undefined
            )
            
            -- 添加表情网格bodygroup信息到exportList
            exportList += "$bodygroup \"faceeffect\"\n{\n\tblank\n"
            
            -- 导出找到的表情网格
            for i = 1 to feMeshes.count do
            (
                local feName = feNames[i]
                local feMesh = feMeshes[i]
                
                if feMesh != undefined then
                (
                    clearSelection()
                    select feMesh
                    selectMore allBonesAndHelpers
                    
                    local filename = exportPath + "\\" + feName + ".smd"
                    local exportResult = WBSMDExport filename true 0 false 1 0 0 false false false false
                    
                    if exportResult == "OK" then
                    (
                        exportList += "\tstudio \"" + feName + ".smd\"\n"
                    )
                    else
                    (
                        exportList += "\t// 导出失败: " + feName + " 错误信息: " + exportResult + "\n"
                    )
                )
                else
                (
                    exportList += "\t// " + feName + " 未找到\n"
                )
            )
            
            exportList += "}\n"
            
            -- 显示导出结果
            if exportList != "" then
            (
                rollout exportRollout "表情网格导出列表" width:500 height:300
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
                messagebox "没有找到可导出的表情网格。"
            )
        )
        else
        (
            messagebox "导出被取消。"
        )
    )
    
    fn showEyeballTrackingSelection =
    (
        rollout eyeballRollout "一键导出" width:300 height:300
        (
            checkbox chk_useEyeballTrackingObject "启用眼球追踪对象" checked:useEyeballTrackingObject align:#center
            button btn_saveLoadEyeball "存取眼球追踪网格" width:180 height:30 align:#center enabled:useEyeballTrackingObject
            checkbox chk_exportAnimation "导出动作SMD" checked:exportAnimation align:#center
            spinner spn_startFrame "起始帧数" range:[0,999,0] type:#integer width:180 align:#center enabled:exportAnimation
            spinner spn_endFrame "结束帧数" range:[0,999,100] type:#integer width:180 align:#center enabled:exportAnimation
            button btn_exportFaceEffects "快速导出静态表情网格" width:180 height:30 align:#center
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
            
            -- 当点击"快速导出静态表情网格"按钮时
            on btn_exportFaceEffects pressed do
            (
                destroyDialog eyeballRollout
                -- 直接调用上层函数中定义的exportFaceEffects函数会导致错误
                -- 调用父函数exportGeometryWithAllBonesAndHelpers的局部函数
                -- 在此处重新定义一个临时的内联函数，然后调用这个函数
                fn tempExportFaceEffects =
                (
                    local exportPath = getSavePath caption:"选择表情网格导出路径"
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
                        
                        -- 查找名称包含fe1/fe2/fe3/fe4的网格
                        local feMeshes = #()
                        local feNames = #("fe1", "fe2", "fe3", "fe4")
                        
                        for i = 1 to feNames.count do
                        (
                            local foundFE = false
                            for geo in allGeometries do
                            (
                                if matchPattern geo.name pattern:("*" + feNames[i] + "*") ignoreCase:true then
                                (
                                    append feMeshes geo
                                    foundFE = true
                                    exit -- 找到第一个匹配的就跳出
                                )
                            )
                            
                            -- 如果没找到对应名称的网格，添加一个空值占位
                            if not foundFE do append feMeshes undefined
                        )
                        
                        -- 添加表情网格bodygroup信息到exportList
                        exportList += "$bodygroup \"faceeffect\"\n{\n\tblank\n"
                        
                        -- 导出找到的表情网格
                        for i = 1 to feMeshes.count do
                        (
                            local feName = feNames[i]
                            local feMesh = feMeshes[i]
                            
                            if feMesh != undefined then
                            (
                                clearSelection()
                                select feMesh
                                selectMore allBonesAndHelpers
                                
                                local filename = exportPath + "\\" + feName + ".smd"
                                local exportResult = WBSMDExport filename true 0 false 1 0 0 false false false false
                                
                                if exportResult == "OK" then
                                (
                                    exportList += "\tstudio \"" + feName + ".smd\"\n"
                                )
                                else
                                (
                                    exportList += "\t// 导出失败: " + feName + " 错误信息: " + exportResult + "\n"
                                )
                            )
                            else
                            (
                                exportList += "\t// " + feName + " 未找到\n"
                            )
                        )
                        
                        exportList += "}\n"
                        
                        -- 显示导出结果
                        if exportList != "" then
                        (
                            rollout exportRollout "表情网格导出列表" width:500 height:300
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
                            messagebox "没有找到可导出的表情网格。"
                        )
                    )
                    else
                    (
                        messagebox "导出被取消。"
                    )
                )
                
                -- 调用临时函数
                tempExportFaceEffects()
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
    
            -- 如果勾选了导出动作，才导出动作SMD
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
    
        -- 当勾选"取消裙子VRD"时，强制勾选并禁用"取消第40帧动作"以及前中后辅助对象角度输入框和拾取按钮
        on chkCancelSkirtVRD changed state do
        (
            if state then
            (
                chkCancel40Frame.checked = true
                chkCancel40Frame.enabled = false -- 禁用"取消第40帧动作"
                spnFront.enabled = false -- 禁用前辅助对象旋转角度
                spnSide.enabled = false -- 禁用侧辅助对象旋转角度
                spnBack.enabled = false -- 禁用后辅助对象旋转角度
                spnFrontLeft40.enabled = false -- 禁用"[深蹲防穿模][实验]"旋转角度
                btnSelectFront.enabled = false -- 禁用"拾取前辅助对象"按钮
                btnSelectSide.enabled = false -- 禁用"拾取侧边辅助对象"按钮
                btnSelectBack.enabled = false -- 禁用"拾取后辅助对象"按钮
            )
            else
            (
                chkCancel40Frame.enabled = true -- 启用"取消第40帧动作"
                spnFront.enabled = true -- 启用前辅助对象旋转角度
                spnSide.enabled = true -- 启用侧辅助对象旋转角度
                spnBack.enabled = true -- 启用后辅助对象旋转角度
                btnSelectFront.enabled = true -- 启用"拾取前辅助对象"按钮
                btnSelectSide.enabled = true -- 启用"拾取侧边辅助对象"按钮
                btnSelectBack.enabled = true -- 启用"拾取后辅助对象"按钮
                if not chkCancel40Frame.checked then spnFrontLeft40.enabled = true -- 启用"[深蹲防穿模][实验]"旋转角度
            )
        )
    
        -- 当勾选"取消第40帧动作"时，使"[深蹲防穿模][实验]"变灰无法使用
        on chkCancel40Frame changed state do
        (
            if state then
            (
                spnFrontLeft40.enabled = false -- 禁用"[深蹲防穿模][实验]"旋转角度
            )
            else if not chkCancelSkirtVRD.checked then
            (
                spnFrontLeft40.enabled = true -- 启用"[深蹲防穿模][实验]"旋转角度
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
    global morpherPresetFilePath = ((getDir #userScripts) + "\\MorpherPresets.ini")
    
    try(destroyDialog MorpherPresetRollout) catch()
    
    rollout MorpherPresetRollout "表情预设管理器" width:600 height:700
    (
        -- 界面元素 - 删除不需要的元素
        dropdownList ddlPresets "预设列表:" items:#() width:280
        editText edtNewPreset "新预设名称:" text:"" width:280
        label lblModelName "当前模型:" text:"未选择" width:280
        button btnLoadFromSelection "从选择加载模型" width:280 align:#left
        spinner spnTotalFrames "总帧数:" range:[1, 999, 27] type:#integer width:280 align:#right
        
        -- 其他界面元素保持不变
        group "屏蔽词列表"
        (
            editText edtBlockedKeywords "用逗号分隔:" text:"歯" width:560
        )
               
        group "帧设置"
        (
            listBox lbxFrames "帧数列表:" height:10 width:270 across:2
            listBox lbxChannels "通道列表:" height:10 width:270
            
            -- 删除帧号spinner，只保留通道值spinner
            spinner spnValue "通道值:" range:[0, 100, 100] type:#integer width:120
            
            -- 添加通道选择列表
            listBox lbxModelChannels "模型通道:" height:10 width:270 across:2
            button btnAddSelectedChannel "添加选中通道" width:200 align:#center
            
            -- 修改按钮布局，移除btnUpdateFrame按钮，调整宽度
            button btnAddFrame "添加帧" width:135 across:3
            button btnRemoveFrame "删除帧" width:135
            button btnRemoveChannel "删除通道" width:135
        )
        
        group "操作"
        (
            button btnLoadPreset "加载预设" width:135
            button btnSavePreset "保存预设" width:135
            button btnDeletePreset "删除预设" width:135
            button btnApplyPreset "应用预设" width:135
        )
        
        -- 数据结构
        local currentPreset = #()  -- 格式: #(#(帧号, #(#(通道名, 值), ...)), ...)
        local blockedKeywords = #("歯")
        local modelChannels = #() -- 存储模型的Morpher通道 #(#(显示名, 实际名), ...)
        
        -- 添加通道名称格式转换函数
        fn convertChannelFormat channelName = (
            -- 预设格式: _123__Mouth_34_0_TalkB_A_L__M_Face____无目标
            -- 模型格式: Mouth_34_0(TalkB_A_L)[M_Face]
            
            local result = channelName
            local debug = false  -- 设置为false禁用详细调试输出
            
            -- if debug then format "转换开始，原始通道名: '%'\n" channelName
            
            -- 1. 移除前缀数字部分，如 "_123__"
            local prefixPattern = "^[#]?_[0-9]+__"
            local regex = dotNetClass "System.Text.RegularExpressions.Regex"
            result = regex.Replace channelName prefixPattern ""
            
            -- if debug then format "去除前缀后: '%'\n" result
            
            -- 2. 移除末尾的"无目标"
            result = substituteString result "无目标" ""
            
            -- if debug then format "去除'无目标'后: '%'\n" result
            
            -- 3. 将下划线分隔的部分拆分为主要部分、表情部分和目标部分
            local components = filterString result "_"
            
            if components.count >= 4 then (
                -- 假设格式为 "Mouth_34_0_TalkB_A_L__M_Face"
                
                -- 查找双下划线位置，它们分隔主要部分和目标部分
                local doubleUnderscorePos = findString result "__"
                
                if doubleUnderscorePos != undefined then (
                    -- 提取主要部分（包括表情）
                    local mainPart = substring result 1 (doubleUnderscorePos-1)
                    -- 提取目标部分
                    local targetPart = substring result (doubleUnderscorePos+2) -1
                    
                    -- if debug then (
                    --     format "找到双下划线分隔: '%' => '%' + '%'\n" result mainPart targetPart
                    -- )
                    
                    -- 分析主要部分，找到表情部分
                    -- 通常表情部分是倒数第二个或第三个部分（如TalkB_A_L中的TalkB）
                    local mainComponents = filterString mainPart "_"
                    
                    -- 假设结构是基础部分(表情名)[目标]
                    -- 如: Mouth_34_0(TalkB_A_L)[M_Face]
                    
                    -- 基础部分通常是前3个元素
                    local basePart = ""
                    if mainComponents.count >= 3 then (
                        for i = 1 to 3 do (
                            basePart += mainComponents[i]
                            if i < 3 then basePart += "_"
                        )
                    ) else (
                        -- 如果组件较少，使用全部
                        basePart = mainPart
                    )
                    
                    -- 表情部分通常是第4个元素
                    local expressionPart = ""
                    if mainComponents.count >= 4 then (
                        expressionPart = mainComponents[4]
                    )
                    
                    -- 剩余部分作为方向/特性
                    local directionPart = ""
                    if mainComponents.count >= 5 then (
                        for i = 5 to mainComponents.count do (
                            directionPart += mainComponents[i]
                            if i < mainComponents.count then directionPart += "_"
                        )
                    )
                    
                    -- 组合为最终格式: 基础部分(表情)[方向/目标]
                    -- 检查是否有每个部分
                    if basePart != "" then (
                        result = basePart
                        
                        -- 添加表情部分
                        if expressionPart != "" then (
                            -- 检查是否有方向部分
                            if directionPart != "" then (
                                result += "(" + expressionPart + "_" + directionPart + ")"
                            ) else (
                                result += "(" + expressionPart + ")"
                            )
                        )
                        
                        -- 添加目标部分
                        if targetPart != "" then (
                            result += "[" + targetPart + "]"
                        )
                    )
                    
                    -- if debug then (
                    --     format "解析结果: 基础='%', 表情='%', 方向='%', 目标='%'\n最终结果='%'\n" basePart expressionPart directionPart targetPart result
                    -- )
                )
            )
            
            -- 如果没有找到双下划线或无法正确解析，尝试使用回退方法
            if result == channelName then (
                -- if debug then format "使用回退方法处理通道名称\n"
                
                -- 简单方法：如果名称很长，尝试提取主要部分
                if channelName.count > 10 then (
                    -- 提取基本部分，忽略前缀数字和后缀
                    local parts = filterString channelName "_"
                    if parts.count >= 3 then (
                        -- 使用最多4个组件
                        local maxComponents = (if parts.count >= 7 then 4 else parts.count - 3)
                        result = ""
                        for i = 1 to maxComponents do (
                            if i > 1 and parts[i][1] != undefined and parts[i][1] != "_" then (
                                result += (if i > 1 then "_" else "") + parts[i]
                            )
                        )
                        
                        -- if debug then format "回退方法结果: '%'\n" result
                    )
                )
            )
            
            -- if debug then format "最终转换结果: '%' -> '%'\n" channelName result
            
            return result
        )

        -- 排序帧
        fn sortFrames = (
            -- 普通冒泡排序实现
            for i = 1 to (currentPreset.count - 1) do (
                for j = 1 to (currentPreset.count - i) do (
                    if currentPreset[j][1] > currentPreset[j+1][1] then (
                        local temp = currentPreset[j]
                        currentPreset[j] = currentPreset[j+1]
                        currentPreset[j+1] = temp
                    )
                )
            )
        )
        
                -- 添加被删除的formatChannelName函数
        fn formatChannelName internalName = (
            local dispName = internalName
            
            -- 如果名称是以"#_"或"_"开头加数字的格式，移除这部分
            local pattern = "^[#]?_[0-9]+__"
            local regex = dotNetClass "System.Text.RegularExpressions.Regex"
            dispName = regex.Replace internalName pattern ""
            
            -- 处理MMD模型中常见的表情通道命名格式
            -- 例如：EyeBrow_1_R_WaraiA__M_Face____无目标
            -- 应变为：EyeBrow_1_R(WaraiA)[M_Face]
            
            -- 移除末尾的"无目标"
            dispName = substituteString dispName "无目标" ""
            
            -- 查找最后一个目标部分(通常在最后两个_之间)
            local parts = filterString dispName "_"
            if parts.count >= 3 then (
                -- 分离主要部分和目标部分
                local mainPart = ""
                local expressionPart = ""
                local targetPart = ""
                
                -- 检查是否符合典型的MMD表情格式
                if parts.count >= 4 then (
                    -- 假设倒数第二个部分是表情名，倒数第一个部分是目标
                    expressionPart = parts[parts.count-1]
                    targetPart = parts[parts.count]
                    
                    -- 构建主要部分(除了表情和目标)
                    for i = 1 to (parts.count-2) do (
                        mainPart += parts[i]
                        if i < (parts.count-2) then mainPart += "_"
                    )
                    
                    -- 重构格式为：主要部分(表情)[目标]
                    dispName = mainPart + "(" + expressionPart + ")[" + targetPart + "]"
                )
            )
            
            -- 如果转换失败(没有明显的格式模式)，尝试简单替换方法
            if dispName == internalName then (
                -- 简单替换双下划线为括号
                dispName = substituteString dispName "__" "("
                dispName = substituteString dispName "____" ")"
            )
            
            -- 如果仍然没有变化，返回原始名称
            if dispName == internalName do (
                return internalName
            )
            
            return dispName
        )

        -- 添加一个专用的Symbol转换函数，确保所有地方使用相同方法
        fn safeToString value = (
            if value == undefined then return ""
            
            if classOf value == Symbol then (
                -- 将Symbol转为字符串的可靠方法
                local ss = stringStream ""
                format "%" value to:ss
                local result = ss as string
                close ss
                return result
            ) else (
                return value as string
            )
        )

                -- 获取模型的Morpher通道
        fn getModelChannels modelObj requireMorpher:true = (
            local channels = #()
            local faceObject = undefined
            local success = true
            local message = ""
            
            -- 确定要处理的对象
            if classOf modelObj == String then
                faceObject = getNodeByName modelObj
            else
                faceObject = modelObj
            
            if faceObject != undefined then (
                -- 设置当前模型标签
                lblModelName.text = "当前模型: " + faceObject.name
                
                -- format "对象名称: %\n对象类型: %\n" faceObject.name (classOf faceObject)
                
                -- 明确查找Morpher修改器
                local morpherMod = undefined
                
                for mod in faceObject.modifiers do (
                    if classOf mod == Morpher then (
                        morpherMod = mod
                        -- format "找到Morpher修改器: %\n" mod.name
                        exit
                    )
                )
                
                if morpherMod != undefined then (
                    -- 选择对象和修改器，以确保正确访问
                    select faceObject
                        max modify mode
                    modPanel.setCurrentObject morpherMod
                    
                    local channelCount = 0
                    
                    -- 获取Morpher通道总数
                    local maxChannels = 1000
                    
                    -- 方法: 扫描所有可能的通道
                    for i = 1 to maxChannels do (
                        try (
                            -- 获取通道值
                            local chanValue = WM3_MC_GetValue morpherMod i
                            
                            -- 尝试获取通道名称
                            local internalName = undefined
                            
                            -- 尝试获取内部名称
                            try (
                                internalName = getSubAnimName morpherMod i
                            ) catch()
                            
                            -- 如果获取到内部名称，转换为显示名称
                            if internalName != undefined and internalName != "" then (
                                local displayName = formatChannelName internalName
                                -- 确保内部名称是字符串而非Symbol
                                if classOf internalName == Symbol then
                                    internalName = internalName as string
                                append channels #(displayName, internalName)
                                channelCount += 1
                                -- format "添加通道 %：'%' (内部名: '%')\n" i displayName internalName
                            )
                            
                            -- 如果连续10个通道都没有名称，认为已经到达通道列表末尾
                            if i > 100 and mod i 10 == 0 then (
                                local hasMoreChannels = false
                                for j = 1 to 10 do (
                                    try (
                                        if getSubAnimName morpherMod (i+j) != undefined then (
                                            hasMoreChannels = true
                                    exit
                                )
                                    ) catch()
                                )
                                if not hasMoreChannels do exit
                            )
                        ) catch (
                            -- 忽略错误
                        )
                    )
                    
                    success = true
                    message = "已找到Morpher修改器并加载通道"
                ) else (
                    -- 没有找到Morpher修改器
                    if requireMorpher then (
                        success = false
                        message = "所选对象上没有找到Morpher修改器"
                    ) else (
                        success = true
                        message = "已选择对象，但没有找到Morpher修改器"
                    )
                )
            ) else (
                success = false
                message = "未找到指定对象"
            )
            
            -- format "找到 % 个通道\n" channels.count
            return #(success, channels, message, faceObject)
        )
        
        -- 更新UI函数
        fn updateFrameList = (
            lbxFrames.items = for frame in currentPreset collect ("帧 " + frame[1] as string)
        )
        
        -- 修复updateChannelList函数，解决Symbol转换问题
        fn updateChannelList = (
            local sel = lbxFrames.selection  -- 使用selection而不是selected
            if sel > 0 and sel <= currentPreset.count then (
                local channels = currentPreset[sel][2]
                local items = #()
                for channel in channels do (
                    -- 确保通道名称是字符串类型 - 使用更强的转换方法
                    local chanNameStr = ""
                    if classOf channel[1] == Symbol then (
                        chanNameStr = channel[1] as string
                    ) else if isKindOf channel[1] String then (
                        chanNameStr = channel[1]
                    ) else (
                        chanNameStr = channel[1] as string
                    )
                    
                    -- 确保值也是字符串
                    local valueStr = channel[2] as string
                    
                    -- 安全地构建显示字符串
                    append items (chanNameStr + ": " + valueStr + "%")
                )
                lbxChannels.items = items
            ) else (
                lbxChannels.items = #()
            )
        )
        
        fn updateModelChannelsList = (
            lbxModelChannels.items = for channel in modelChannels collect channel[1]
        )
        
        fn refreshPresetList = (
            local presets = #()
            if doesFileExist morpherPresetFilePath then (
                local sections = getINISetting morpherPresetFilePath
                for s in sections do append presets s
            )
            ddlPresets.items = presets
        )
        
        -- 保存和加载预设
        fn savePreset presetName = (
            -- 移除保存空帧部分
            local blockedStr = ""
            for i = 1 to blockedKeywords.count do (
                blockedStr += blockedKeywords[i]
                if i < blockedKeywords.count do blockedStr += ","
            )
            
            -- 清理模型名称，移除前缀
            local modelName = lblModelName.text
            if matchPattern modelName pattern:"当前模型: *" then (
                modelName = substring modelName 6 -1
            )
            
            -- 写入基本信息 - 保存实际模型名称，不带前缀
            setINISetting morpherPresetFilePath presetName "ModelName" modelName
            setINISetting morpherPresetFilePath presetName "TotalFrames" (spnTotalFrames.value as string)
            setINISetting morpherPresetFilePath presetName "BlockedKeywords" blockedStr
            
            -- 移除EmptyFrames部分，不再保存空帧
            
            -- 保存帧设置，包括空帧
            for i = 1 to currentPreset.count do (
                local frame = currentPreset[i]
                local frameNum = frame[1]
                local frameStr = ""
                
                -- 保存所有帧，包括没有通道设置的空帧
                for j = 1 to frame[2].count do (
                    local channel = frame[2][j]
                    
                    -- 确保保存精确的通道名称和值
                    local chanNameStr = safeToString(channel[1])
                    local valueStr = safeToString(channel[2])
                    
                    frameStr += chanNameStr + "=" + valueStr
                    if j < frame[2].count do frameStr += "|"
                )
                
                -- 即使frameStr为空（没有通道设置），也保存该帧
                -- 这样空帧也会被记录下来
                setINISetting morpherPresetFilePath presetName ("Frame_" + frameNum as string) frameStr
            )
            
            refreshPresetList()
            -- messageBox ("预设保存成功: " + presetName) title:"成功" -- 移除这行
            return true -- 返回成功状态
        )
        
        fn loadPreset presetName = (
            -- 清空当前预设
            currentPreset = #()
            
            -- 读取基本信息
            local modelName = getINISetting morpherPresetFilePath presetName "ModelName"
            local totalFrames = getINISetting morpherPresetFilePath presetName "TotalFrames"
            local blockedStr = getINISetting morpherPresetFilePath presetName "BlockedKeywords"
            
            -- 解析屏蔽关键词
            blockedKeywords = #()
            if blockedStr != "" then (
                local keywords = filterString blockedStr ","
                for word in keywords do (
                    append blockedKeywords word
                )
            )
            
            -- 自动更新屏蔽词文本框
            edtBlockedKeywords.text = blockedStr
            
            -- 读取帧设置
            for i = 0 to (totalFrames as integer) do (
                local frameKey = "Frame_" + i as string
                local frameStr = getINISetting morpherPresetFilePath presetName frameKey
                
                -- 处理帧数据
                local channelList = #()
                
                -- 如果帧有通道设置，解析它们
                if frameStr != "" then (
                    local channels = filterString frameStr "|"
                    
                    for channel in channels do (
                        local parts = filterString channel "="
                        if parts.count >= 2 then (
                            local chanName = parts[1]
                            local chanValue = parts[2] as integer
                            append channelList #(chanName, chanValue)
                        )
                    )
                )
                
                -- 添加帧，无论是否有通道设置
                append currentPreset #(i, channelList)
            )
            
            -- 更新UI - 在单独的行中重写这部分
            try (
                local frameVal = totalFrames as integer
                spnTotalFrames.value = frameVal
            ) catch (
                format "设置帧数时出错: %\n" (getCurrentException())
            )
            
            -- 单独设置模型名称
            try (
                lblModelName.text = modelName
            ) catch (
                format "设置模型名称时出错: %\n" (getCurrentException())
            )
            
            -- 确保更新帧列表和通道列表
            updateFrameList()
            updateChannelList()
            
            -- 移除消息框，只返回成功状态
            -- messageBox ("已加载预设: " + presetName) title:"成功"  -- 删除此行
            return true  -- 返回成功状态
        )
        
        -- UI事件处理
        on MorpherPresetRollout open do (
            refreshPresetList()
        )
        
        on lbxFrames selected sel do (
            -- 移除对已删除的spnFrame控件的引用
            -- 下面这行应该被删除或注释掉：
            -- spnFrame.value = currentPreset[sel][1]
            
            -- 只保留更新通道列表的功能
            updateChannelList()
        )
        
        on btnAddFrame pressed do (
            -- 确定下一帧的帧号
            local nextFrame = 0
            
            -- 查找已有帧中最大的帧号
            if currentPreset.count > 0 then (
                for frame in currentPreset do (
                    if frame[1] >= nextFrame then (
                        nextFrame = frame[1] + 1
                    )
                )
            )
            
            -- 添加新帧
            append currentPreset #(nextFrame, #())
            
            -- 排序并更新UI
            sortFrames()
            updateFrameList()
            
            -- 选择新添加的帧
            local newIndex = 0
            for i = 1 to currentPreset.count do (
                if currentPreset[i][1] == nextFrame then (
                    newIndex = i
                    exit
                )
            )
            
            if newIndex > 0 then (
                lbxFrames.selection = newIndex
                updateChannelList()
            )
            
            -- 显示成功消息
            format "添加了新帧: %\n" nextFrame
        )
        
        on btnRemoveFrame pressed do (
            local sel = lbxFrames.selection
            if sel > 0 and sel <= currentPreset.count then (
                deleteItem currentPreset sel
                updateFrameList()
                updateChannelList()
            )
        )
        
        -- 新增 - 加载模型通道按钮事件
        on btnLoadFromSelection pressed do (
            -- 检查是否有选择
            if selection.count > 0 then (
                -- 获取选中的第一个对象
                local selObj = selection[1]
                
                -- 保存模型对象引用
                selectedModelObj = selObj
                
                -- 只在UI显示带前缀的名称，但内部使用纯模型名称
                lblModelName.text = "当前模型: " + selObj.name -- 直接保存模型名称，加前缀
                
                -- 加载通道
                local result = getModelChannels selObj requireMorpher:true
                if result[1] then (
                    modelChannels = result[2]
                    updateModelChannelsList()
                    messageBox result[3] title:"成功"
                ) else (
                    messageBox result[3] title:"错误"
                )
            ) else (
                messageBox "请先选择一个对象!" title:"错误"
            )
        )
        
        -- 新增 - 添加选中通道按钮事件
        on btnAddSelectedChannel pressed do (
            local frameIndex = lbxFrames.selection
            local channelIndex = lbxModelChannels.selection
            
            if frameIndex > 0 and frameIndex <= currentPreset.count then (
                if channelIndex > 0 and channelIndex <= modelChannels.count then (
                    local channelName = modelChannels[channelIndex][2] -- 使用实际名称，而不是显示名称
                    local channelValue = spnValue.value
                    
                    -- 添加通道到当前帧
                    append currentPreset[frameIndex][2] #(channelName, channelValue)
                    
                    -- 更新UI
                    updateChannelList()
                    
                    -- 通知用户
                    format "已添加通道 % 到帧 %\n" channelName currentPreset[frameIndex][1]
                )
            ) else (
                if frameIndex <= 0 or frameIndex > currentPreset.count then
                    messageBox "请先选择一个帧!" title:"错误"
                else
                    messageBox "请先选择一个通道!" title:"错误"
            )
        )
        
        on edtBlockedKeywords changed txt do (
            blockedKeywords = filterString txt ","
        )
        
        on edtEmptyFrames changed txt do (
            local frameStrings = filterString txt ","
            emptyFrames = #()
            for str in frameStrings do (
                try (
                    append emptyFrames (str as integer)
                ) catch ()
            )
        )
        
        on btnSavePreset pressed do (
            local presetName = edtNewPreset.text
            if presetName != "" then (
                if savePreset presetName then (
                    -- 只在这里显示成功消息
                    messageBox ("预设保存成功: " + presetName) title:"成功"
                    refreshPresetList()
                )
            ) else (
                messageBox "请输入预设名称" title:"错误"
            )
        )
        
        on btnLoadPreset pressed do (
            if ddlPresets.selection > 0 then (
                local presetName = ddlPresets.selected
                if loadPreset presetName then (
                    -- 只在这里显示成功消息
                    messageBox ("已加载预设: " + presetName) title:"成功"
                )
            ) else (
                messageBox "请先选择预设" title:"错误"
            )
        )
        
        on btnDeletePreset pressed do (
            if ddlPresets.selected != undefined then (
                local selectedPreset = ddlPresets.selected
                delINISetting morpherPresetFilePath selectedPreset
                refreshPresetList()
                messageBox ("已删除预设: " + selectedPreset) title:"成功"
            )
        )
        
        -- 应用预设的函数 - 移动到rollout内部
        fn applyMorpherPreset modelObj totalFrames frameSettings blockedKeywords = (
            -- 检查通道名是否包含屏蔽词
            fn isBlockedChannel channelName blockedKeywords = (
                for keyword in blockedKeywords do (
                    if matchPattern channelName pattern:("*" + keyword + "*") then
                        return true
                )
                return false
            )
            
            -- 跳过帧检查
            fn isEmptyFrame frameNum emptyFramesList = (
                for f in emptyFramesList do (
                    if f == frameNum then return true
                )
                return false
            )
            
            -- 保存原始自动关键帧状态
            local oldAnimButtonState = animButtonState
            
            try (
                if modelObj != undefined then (
                    -- 检查对象是否为可编辑网格或其他支持的类型
                    if isKindOf modelObj GeometryClass then (
                        -- 选择该对象
                        select modelObj
                        -- format "对象 '%' 已选择。\n" modelObj.name
                        
                        -- 查找Morpher修改器
                        local morpherMod = undefined
                        for mod in modelObj.modifiers do (
                            if classOf mod == Morpher then (
                                morpherMod = mod
                                exit
                            )
                        )
                        
                        -- 如果没有找到Morpher修改器，尝试添加一个
                        if morpherMod == undefined then (
                            morpherMod = morpher()
                            addModifier modelObj morpherMod
                            -- format "为对象添加了新的Morpher修改器\n"
                        )
                        
                        -- 确保修改器可见
                        modPanel.setCurrentObject morpherMod
                        
                        -- 确定Morpher修改器中的最大通道数量
                        local maxChannels = 1000 -- Morpher修改器的标准通道数量，与getModelChannels中保持一致
                        
                        -- 输出Morpher修改器中所有可用通道，帮助调试
                        -- format "\n===== Morpher修改器中的所有通道 =====\n"
                        -- for c = 1 to maxChannels do (
                        --     try (
                        --         local availName = WM3_MC_GetName morpherMod c
                        --         if availName != undefined and availName != "" then (
                        --             format "  索引 %: '%'\n" c availName
                        --         )
                        --     ) catch ()
                        -- )
                        -- format "=====================================\n\n"
                        
                        -- 开启动画录制模式
                        animateVertex = true
                        animButtonState = true
                        
                        -- 遍历每一帧
                        animate on (
                            for i = 0 to totalFrames do (
                                -- 寻找对应的帧设置
                                local frameData = undefined
                                for j = 1 to frameSettings.count do (
                                    if frameSettings[j][1] == i then (
                                        frameData = frameSettings[j]
                                        exit
                                    )
                                )
                                
                                -- 移动时间滑块到当前帧
                                sliderTime = i
                                
                                -- 所有帧先将所有通道设为0
                                for c = 1 to maxChannels do (
                                    try (
                                        WM3_MC_SetValue morpherMod c 0.0
                                    ) catch ()
                                )
                                
                                -- 如果找到了这一帧的设置并且有通道设置，应用通道值
                                if frameData != undefined and frameData[2].count > 0 then (
                                    local channels = frameData[2]
                                    -- format "帧 % 有 % 个通道设置\n" i channels.count
                                    
                                    -- 先为每个通道构建索引映射，以避免重复查找通道
                                    -- 使用数组代替Dictionary，每个元素为 #(通道名, 索引值)
                                    local channelIndexMap = #()
                                    
                                    -- 预处理：遍历所有通道名称，找出对应索引
                                    for channel in channels do (
                                        local channelName = channel[1]
                                        
                                        -- 如果已经有此通道，则跳过
                                        local alreadyExists = false
                                        for map in channelIndexMap do (
                                            if map[1] == channelName then (
                                                alreadyExists = true
                                                exit
                                            )
                                        )
                                        if alreadyExists then continue
                                        
                                        -- 在Morpher修改器中查找通道
                                        local channelIndex = -1
                                        for c = 1 to maxChannels do (
                                            try (
                                                local currentName = WM3_MC_GetName morpherMod c
                                                if currentName != undefined and currentName != "" then (
                                                    -- 尝试转换格式后匹配
                                                    local convertedName = convertChannelFormat channelName
                                                    
                                                    -- 记录转换前后的名称，帮助调试
                                                    -- format "比较: '%' vs '%'\n通道转换: '%' -> '%'\n" currentName channelName channelName convertedName
                                                    
                                                    -- 1. 精确匹配原始名称
                                                    if currentName == channelName then (
                                                        channelIndex = c
                                                        -- format "  精确匹配通道: '%' 在索引 %\n" channelName c
                                                        exit
                                                    )
                                                    -- 2. 转换格式后匹配
                                                    else if currentName == convertedName then (
                                                        channelIndex = c
                                                        -- format "  转换格式后匹配: '%' 在索引 %\n" convertedName c
                                                        exit
                                                    )
                                                    -- 3. 忽略大小写匹配
                                                    else if stricmp currentName convertedName == 0 then (
                                                        channelIndex = c
                                                        -- format "  忽略大小写匹配: '%' 在索引 %\n" convertedName c
                                                        exit
                                                    )
                                                    -- 4. 简化名称后匹配 (移除所有空格、括号等)
                                                    else (
                                                        -- 移除所有非字母数字字符，仅保留字母和数字用于比较
                                                        fn simplifyName inputName = (
                                                            local result = ""
                                                            for i = 1 to inputName.count do (
                                                                local char = inputName[i]
                                                                -- 只保留字母和数字
                                                                if (char >= "A" and char <= "Z") or (char >= "a" and char <= "z") or (char >= "0" and char <= "9") then (
                                                                    result += char
                                                                )
                                                            )
                                                            return result
                                                        )
                                                        
                                                        -- 简化两个名称进行比较
                                                        local simplifiedCurrent = simplifyName (currentName as string)
                                                        local simplifiedConverted = simplifyName (convertedName as string)
                                                        
                                                        if simplifiedCurrent == simplifiedConverted and simplifiedCurrent != "" then (
                                                            channelIndex = c
                                                            -- format "  简化后匹配: '%' ~ '%' 在索引 %\n" currentName convertedName c
                                                            exit
                                                        )
                                                        -- 5. 包含关系匹配 (一个是另一个的子字符串)
                                                        else if (findString simplifiedCurrent simplifiedConverted) != undefined or 
                                                                (findString simplifiedConverted simplifiedCurrent) != undefined then (
                                                            -- 只在有足够长度的匹配时使用
                                                            if simplifiedCurrent.count >= 5 and simplifiedConverted.count >= 5 then (
                                                                channelIndex = c
                                                                -- format "  包含关系匹配: '%' ~ '%' 在索引 %\n" currentName convertedName c
                                                                exit
                                                            )
                                                        )
                                                    )
                                                )
                                            ) catch ()
                                        )
                                        
                                        -- 如果找到了通道，将索引添加到映射中
                                        if channelIndex > 0 then (
                                            append channelIndexMap #(channelName, channelIndex)
                                            -- format "  通道 '%' 的索引是: %\n" channelName channelIndex
                                        )
                                    )
                                    
                                    -- 为每个通道设置值
                                    for k = 1 to channels.count do (
                                        local channelName = channels[k][1]
                                        local channelValue = channels[k][2]
                                        
                                        -- 输出详细的通道信息
                                        -- format "\n处理通道: 类型[%], 值[%]: '%'\n" (classOf channelName) (classOf channelValue) channelName
                                        
                                        -- 跳过被屏蔽的通道，但只在第一个通道中应用屏蔽词
                                        if k == 1 and isBlockedChannel channelName blockedKeywords then (
                                            -- format "跳过屏蔽通道 '%'（第一个通道）\n" channelName
                                            continue
                                        )
                                        
                                        -- 从映射中获取通道索引
                                        local channelIndex = -1
                                        for map in channelIndexMap do (
                                            if map[1] == channelName then (
                                                channelIndex = map[2]
                                                exit
                                            )
                                        )
                                        
                                        -- 如果找到了通道，设置值并创建关键帧
                                        if channelIndex > 0 then (
                                            -- 确保channelValue是数值
                                            local numValue = try(channelValue as float) catch(0.0)
                                            -- 设置通道值并创建关键帧
                                            WM3_MC_SetValue morpherMod channelIndex (numValue)
                                            -- format "帧 % 设置通道 '%' (索引%) 的值为 %\n" i channelName channelIndex numValue
                                        ) else (
                                            -- format "未找到通道 '%' - 请检查通道名称是否精确匹配\n" channelName
                                        )
                                    )
                                ) else (
                                    -- 未在预设中找到设置的帧视为空帧，已经设置了全零通道
                                    -- format "帧 % 没有设置，已创建全零关键帧\n" i
                                )
                            )
                        )
                        
                        -- 恢复原始自动关键帧状态
                        animButtonState = oldAnimButtonState
                        
                        -- 关闭动画录制模式
                        animateVertex = false
                        
                        -- messageBox ("已应用预设到 " + modelObj.name + "，并创建了关键帧动画") title:"成功" -- 移除这行
                        return #(true, modelObj.name) -- 返回成功状态和模型名称
                    ) else (
                        messageBox "所选对象不是可编辑几何体" title:"错误"
                        return #(false, "所选对象不是可编辑几何体")
                    )
                ) else (
                    messageBox "找不到指定对象" title:"错误"
                    return #(false, "找不到指定对象")
                )
            ) catch (
                local errMsg = getCurrentException()
                messageBox ("应用预设时出错: " + errMsg) title:"错误"
                format "错误详情: %\n" errMsg
                return #(false, errMsg)
            ) finally (
                -- 确保总是恢复原始自动关键帧状态
                animButtonState = oldAnimButtonState
            )
        )
        
        -- 修复应用预设时的模型查找和通道匹配问题

        -- 修改btnApplyPreset事件处理函数，从预设名称精确查找模型
        on btnApplyPreset pressed do (
            if currentPreset.count > 0 then (
                -- 直接使用保存的纯模型名称
                local presetModelName = lblModelName.text
                -- format "使用模型名称: '%'\n" presetModelName
                
                -- 如果lblModelName包含前缀，提取实际名称
                if matchPattern presetModelName pattern:"当前模型: *" then (
                    presetModelName = substring presetModelName 6 -1
                    -- format "提取后的模型名称: '%'\n" presetModelName
                )
                
                -- 根据名称查找模型对象
                local modelObj = undefined
                for obj in objects do (
                    if obj.name == presetModelName then (
                        modelObj = obj
                        -- format "找到精确匹配模型: %\n" obj.name
                        exit
                    )
                )
                
                -- 应用预设或显示错误
                if modelObj != undefined then (
                    -- format "找到模型对象: %\n" modelObj.name
                    local result = applyMorpherPreset modelObj spnTotalFrames.value currentPreset blockedKeywords
                    
                    -- 只在这里显示成功消息
                    if result[1] then (
                        messageBox ("已应用预设到 " + result[2] + "，并创建了关键帧动画") title:"成功"
                    )
                ) else (
                    messageBox ("无法找到模型对象: " + presetModelName + "\n\n请确保场景中存在名称完全匹配的对象。") title:"错误"
                )
            ) else (
                messageBox "没有加载预设，请先加载预设。" title:"错误"
            )
        )

        -- 2. 添加删除通道的事件处理函数
        on btnRemoveChannel pressed do (
            local frameIndex = lbxFrames.selection
            local channelIndex = lbxChannels.selection
            
            if frameIndex > 0 and frameIndex <= currentPreset.count then (
                if channelIndex > 0 and channelIndex <= currentPreset[frameIndex][2].count then (
                    -- 获取要删除的通道名称
                    local channelToRemove = currentPreset[frameIndex][2][channelIndex][1]
                    
                    -- 从数组中删除通道
                    deleteItem currentPreset[frameIndex][2] channelIndex
                    
                    -- 更新UI
                    updateChannelList()
                    
                    -- 提示用户
                    format "已从帧 % 删除通道 '%'\n" currentPreset[frameIndex][1] channelToRemove
                ) else (
                    messageBox "请先选择要删除的通道" title:"错误"
                )
            ) else (
                messageBox "请先选择帧" title:"错误"
            )
        )

        -- 添加屏蔽词设置功能
        on btnUpdateBlockedWords pressed do (
            -- 清空当前屏蔽词列表
            blockedKeywords = #()
            
            -- 从文本框获取输入
            local blockedStr = edtBlockedKeywords.text
            
            -- 解析屏蔽关键词
            if blockedStr != "" then (
                local keywords = filterString blockedStr ","
                for word in keywords do (
                    -- 修剪空白并添加到数组
                    word = trimLeft (trimRight word)
                    if word != "" then append blockedKeywords word
                )
            )
            
            -- 输出当前屏蔽词列表
            local resultStr = "已更新屏蔽词列表:\n"
            for i = 1 to blockedKeywords.count do (
                resultStr += "- \"" + blockedKeywords[i] + "\"\n"
            )
            
            messageBox resultStr title:"屏蔽词已更新"
        )
    )
    
    -- 删除外部的applyMorpherPreset函数定义，现在已移到rollout内部
    
    createDialog MorpherPresetRollout
)

fn createSkirtHelperDialog = (
    try(destroyDialog SkirtHelperDialog) catch()

    global SkirtHelperDialog
    rollout SkirtHelperDialog "一键嫁接" width:200
    (
        checkbox chkUmaMode "赛马娘模式" width:180
        checkbox chkFollowParentConnection "非定义辅助对象跟随父级连接" checked:true width:180 tooltip:"将未定义的辅助对象连接到其父级辅助对象所连接的骨骼上"
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
            #("Left arm", "ValveBiped.Bip01_L_UpperArm"),
            #("Left shoulder", "ValveBiped.Bip01_L_Clavicle"),
            #("Shoulder_L", "ValveBiped.Bip01_L_Clavicle")
        )
        
        local umaConnections = #(
            #("Toe_R", "ValveBiped.Bip01_R_Toe0"),
            #("Ankle_R", "ValveBiped.Bip01_R_Foot"),
            #("Knee_R", "ValveBiped.Bip01_R_Calf"),
            #("Thigh_R", "ValveBiped.Bip01_R_Thigh"),
            #("Toe_L", "ValveBiped.Bip01_L_Toe0"),
            #("Ankle_L", "ValveBiped.Bip01_L_Foot"),
            #("Knee_L", "ValveBiped.Bip01_L_Calf"),
            #("Thigh_L", "ValveBiped.Bip01_L_Thigh"),
            #("Pinky_01_R", "ValveBiped.Bip01_R_Finger4"),
            #("Pinky_02_R", "ValveBiped.Bip01_R_Finger41"),
            #("Pinky_03_R", "ValveBiped.Bip01_R_Finger42"),
            #("Ring_01_R", "ValveBiped.Bip01_R_Finger3"),
            #("Ring_02_R", "ValveBiped.Bip01_R_Finger31"),
            #("Ring_03_R", "ValveBiped.Bip01_R_Finger32"),
            #("Index_01_R", "ValveBiped.Bip01_R_Finger1"),
            #("Index_02_R", "ValveBiped.Bip01_R_Finger11"),
            #("Index_03_R", "ValveBiped.Bip01_R_Finger12"),
            #("Middle_01_R", "ValveBiped.Bip01_R_Finger2"),
            #("Middle_02_R", "ValveBiped.Bip01_R_Finger21"),
            #("Middle_03_R", "ValveBiped.Bip01_R_Finger22"),
            #("Thumb_01_R", "ValveBiped.Bip01_R_Finger0"),
            #("Thumb_02_R", "ValveBiped.Bip01_R_Finger01"),
            #("Thumb_03_R", "ValveBiped.Bip01_R_Finger02"),
            #("Wrist_R", "ValveBiped.Bip01_R_Hand"),
            #("Elbow_R", "ValveBiped.Bip01_R_Forearm"),
            #("Arm_R", "ValveBiped.Bip01_R_UpperArm"),
            #("Shoulder_R", "ValveBiped.Bip01_R_Clavicle"),
            #("Head", "ValveBiped.Bip01_Head1"),
            #("Neck", "ValveBiped.Bip01_Neck1"),
            #("Chest", "ValveBiped.Bip01_Spine4"),
            #("Spine", "ValveBiped.Bip01_Spine2"),
            #("Hip", "ValveBiped.Bip01_Pelvis"),
            #("Pinky_01_L", "ValveBiped.Bip01_L_Finger4"),
            #("Pinky_02_L", "ValveBiped.Bip01_L_Finger41"),
            #("Pinky_03_L", "ValveBiped.Bip01_L_Finger42"),
            #("Ring_01_L", "ValveBiped.Bip01_L_Finger3"),
            #("Ring_02_L", "ValveBiped.Bip01_L_Finger31"),
            #("Ring_03_L", "ValveBiped.Bip01_L_Finger32"),
            #("Index_01_L", "ValveBiped.Bip01_L_Finger1"),
            #("Index_02_L", "ValveBiped.Bip01_L_Finger11"),
            #("Index_03_L", "ValveBiped.Bip01_L_Finger12"),
            #("Middle_01_L", "ValveBiped.Bip01_L_Finger2"),
            #("Middle_02_L", "ValveBiped.Bip01_L_Finger21"),
            #("Middle_03_L", "ValveBiped.Bip01_L_Finger22"),
            #("Thumb_01_L", "ValveBiped.Bip01_L_Finger0"),
            #("Thumb_02_L", "ValveBiped.Bip01_L_Finger01"),
            #("Thumb_03_L", "ValveBiped.Bip01_L_Finger02"),
            #("Wrist_L", "ValveBiped.Bip01_L_Hand"),
            #("Elbow_L", "ValveBiped.Bip01_L_Forearm"),
            #("Arm_L", "ValveBiped.Bip01_L_UpperArm"),
            #("Shoulder_L", "ValveBiped.Bip01_L_Clavicle"),
            #("Waist", "ValveBiped.Bip01_Spine")
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
            
            -- 创建一个普通的数组而不是字典，用于存储辅助对象到骨骼的映射
            local helperBonePairs = #()
            
            -- 检查是否是同一节点或祖先节点（防止循环引用）
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
            
            -- 查找辅助对象对应的骨骼
            fn findBoneForHelper helperObj helperBonePairsArray = (
                local result = undefined
                for pair in helperBonePairsArray do (
                    if pair[1] == helperObj then (
                        result = pair[2]
                        exit
                    )
                )
                return result
            )
            
            -- 判断对象是否是辅助对象（Dummy或Point）
            fn isHelperObject obj = (
                obj != undefined and (classOf obj == Dummy or classOf obj == Point)
            )
            
            -- 判断对象是否是骨骼（Biped_Object或Bone）
            fn isBoneObject obj = (
                obj != undefined and (classOf obj == Biped_Object or classOf obj == BoneGeometry)
            )
    
            -- 创建一个数组来跟踪已处理的辅助对象
            local processedHelpers = #()
            
            -- 先保存原始的父级映射关系（在断开连接前）
            local originalParentMap = #()
            
            -- 收集所有辅助对象及其原始父级
            local allHelpers = for obj in objects where (classOf obj == Dummy or classOf obj == Point) collect obj
            for helper in allHelpers do (
                if helper.parent != undefined then (
                    append originalParentMap #(helper, helper.parent)
                )
            )
            
            -- 先定义需要优先断开连接的辅助对象
            local priorityDisconnectList = if chkUmaMode.checked then 
                #("Neck", "Arm_L", "Arm_R", "Thigh_L", "Thigh_R") 
            else 
                #("Neck", "Shoulder_L", "Shoulder_R", "Thigh_L", "Thigh_R")
            
            -- 第0步：先断开优先断开列表中的辅助对象
            for objName in priorityDisconnectList do (
                local obj = getNodeByName objName
                if obj != undefined then (
                    obj.parent = undefined
                    format "Disconnected priority helper: %\n" objName
                )
            )
            
            -- 第1步：处理脊椎辅助对象
            local spineConnections = if chkUmaMode.checked then
                #(
                    #("Waist", "ValveBiped.Bip01_Spine"),
                    #("Spine", "ValveBiped.Bip01_Spine2"),
                    #("Chest", "ValveBiped.Bip01_Spine4")
                )
            else
                #(
                    #("Spine", "ValveBiped.Bip01_Spine"),
                    #("Chest", "ValveBiped.Bip01_Spine4")
                )
                
            -- 连接脊椎辅助对象到对应骨骼
            for conn in spineConnections do (
                local helper = getNodeByName conn[1]
                local bone = getNodeByName conn[2]
                
                if helper != undefined and bone != undefined then (
                    if not isDescendantOrSelf helper bone then (
                        helper.parent = bone
                        -- 添加到映射数组
                        append helperBonePairs #(helper, bone)
                        format "Connected spine helper '%' to bone '%'\n" helper.name bone.name
                        append processedHelpers helper
                    )
                )
            )
            
            -- A. 保留Armature的处理
            local armature = getNodeByName "Armature"
            local pelvis = getNodeByName "ValveBiped.Bip01_Pelvis"
            if armature != undefined and pelvis != undefined then (
                if not isDescendantOrSelf armature pelvis then (
                    pelvis.parent = armature
                    format "Set Pelvis parent to Armature\n"
                )
            )
            
            -- 第2步：连接定义的辅助对象到骨骼（按原有的逆序处理）
            for i = connections.count to 1 by -1 do (
                local conn = connections[i]
                local helper = getNodeByName conn[1]
                local bone = getNodeByName conn[2]
                
                -- 跳过已处理的辅助对象
                if helper != undefined and bone != undefined and (findItem processedHelpers helper) == 0 then (
                    format "Connecting helper '%' to bone '%'\n" helper.name bone.name
                    
                    -- 先断开当前连接
                    helper.parent = undefined
                    
                    -- 连接主要辅助对象
                    if not isDescendantOrSelf helper bone then (
                        helper.parent = bone
                        -- 添加到映射数组
                        append helperBonePairs #(helper, bone)
                        append processedHelpers helper
                        format "Successfully connected '%' to '%'\n" helper.name bone.name
                    ) else (
                        format "Invalid parent assignment: '%' cannot be a parent of '%'.\n" helper.name bone.name
                    )
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
            
            -- 第3步：如果启用了"非定义辅助对象跟随父级连接"功能，处理未定义的辅助对象
            if chkFollowParentConnection.checked then (
                -- 处理未定义的辅助对象（未被处理过的辅助对象）
                local unprocessedHelpers = for obj in allHelpers where (findItem processedHelpers obj) == 0 collect obj
                
                -- 首先按层级排序，让更浅层级的辅助对象先处理
                fn getObjectDepth obj = (
                    local depth = 0
                    local current = obj.parent
                    while current != undefined do (
                        depth += 1
                        current = current.parent
                    )
                    return depth
                )
                
                -- 手动按深度排序
                local sortedHelpers = #()
                for helper in unprocessedHelpers do (
                    local depth = getObjectDepth helper
                    local inserted = false
                    for i = 1 to sortedHelpers.count do (
                        if depth < getObjectDepth sortedHelpers[i] then (
                            insertItem helper sortedHelpers i
                            inserted = true
                            exit
                        )
                    )
                    if not inserted do append sortedHelpers helper
                )
                unprocessedHelpers = sortedHelpers
                
                -- 为每个非定义辅助对象找到目标骨骼
                local helperTargetMap = #()
                
                -- 首先输出辅助对象和骨骼的映射情况
                format "\n--------- 已处理的辅助对象映射 ---------\n"
                for pair in helperBonePairs do (
                    format "辅助对象: % 已连接到骨骼: %\n" pair[1].name pair[2].name
                )
                format "--------- 映射结束 ---------\n\n"
                
                -- 首先准备好每个辅助对象应该连接到哪个骨骼
                for helper in unprocessedHelpers do (
                    -- 检查是否是手指辅助对象
                    local isFingerHelper = false
                    local fingerKeywords = if chkUmaMode.checked then 
                        #("Thumb_", "Index_", "Middle_", "Ring_", "Pinky_") 
                    else 
                        #("Thumb", "IndexFinger", "MiddleFinger", "RingFinger", "LittleFinger")
                    
                    for keyword in fingerKeywords do (
                        if findString helper.name keyword != undefined do isFingerHelper = true
                    )
                    
                    -- 如果是手指辅助对象，则跳过处理
                    if isFingerHelper then (
                        format "跳过手指辅助对象: % (为避免干扰骨架结构)\n" helper.name
                        continue
                    )
                    
                    -- 查找原始父级（在断开连接前的父级）
                    local originalParent = undefined
                    for pair in originalParentMap do (
                        if pair[1] == helper then (
                            originalParent = pair[2]
                            exit
                        )
                    )
                    
                    if originalParent != undefined then (
                        local originalParentName = originalParent.name
                        format "处理未定义辅助对象: %，原始父级: %\n" helper.name originalParentName
                        
                        -- 如果原始父级是辅助对象
                        if isHelperObject originalParent then (
                            -- 查找这个父级辅助对象现在连接到哪个骨骼
                            local targetBone = undefined
                            
                            -- 直接遍历辅助对象到骨骼的映射关系
                            for pair in helperBonePairs do (
                                if pair[1] == originalParent then (
                                    targetBone = pair[2]
                                    format "  找到父级辅助对象 % 的目标骨骼: %\n" originalParentName targetBone.name
                                    exit
                                )
                            )
                            
                            -- 如果找到了目标骨骼
                            if targetBone != undefined then (
                                -- 检查是否可以安全连接（确保不会造成循环引用）
                                if not isDescendantOrSelf targetBone helper then (
                                    -- 保存目标骨骼信息，但不立即连接
                                    append helperTargetMap #(helper, targetBone)
                                    format "  将连接 % 到骨骼 %\n" helper.name targetBone.name
                                ) else (
                                    format "  警告: 无效的父级分配: 循环引用检测 - '%' 是 '%' 的后代或本身\n" targetBone.name helper.name
                                )
                            ) else (
                                format "  警告: 未找到父级辅助对象 % 的目标骨骼\n" originalParentName
                            )
                        )
                        -- 如果原始父级是骨骼，就保持原样
                        else if isBoneObject originalParent then (
                            if not isDescendantOrSelf originalParent helper then (
                                append helperTargetMap #(helper, originalParent)
                                format "  将保持连接 % 到原始骨骼 %\n" helper.name originalParentName
                            ) else (
                                format "  警告: 无效的父级分配: 循环引用检测 - '%' 是 '%' 的后代或本身\n" originalParent.name helper.name
                            )
                        ) else (
                            format "  警告: 原始父级 % 既不是辅助对象也不是骨骼\n" originalParentName
                        )
                    ) else (
                        format "警告: 未找到辅助对象 % 的原始父级\n" helper.name
                    )
                )
                
                -- 然后先断开所有非定义辅助对象的连接
                for pair in helperTargetMap do (
                    local helper = pair[1]
                    local currentParent = helper.parent
                    local currentParentName = if currentParent != undefined then currentParent.name else "无"
                    format "断开辅助对象 % 与当前父级 % 的连接\n" helper.name currentParentName
                    helper.parent = undefined
                )
                
                -- 最后再连接到目标骨骼
                for pair in helperTargetMap do (
                    local helper = pair[1]
                    local targetBone = pair[2]
                    format "连接辅助对象 % 到目标骨骼 %\n" helper.name targetBone.name
                    helper.parent = targetBone
                    append helperBonePairs #(helper, targetBone)
                    append processedHelpers helper
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
                this.safeAlign spine Waist
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
                
                -- 处理手腕和前臂的缩放
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
                
                -- 缩放左前臂，使其末端位置与左手腕辅助对象的位置一致
                local leftForearmEndPos = this.findNodeByName "ValveBiped.Bip01_L_Hand"
                if leftForearmEndPos != undefined and customLeftWrist != undefined then (
                    local leftForearmLength = distance leftForearm.position leftForearmEndPos.position
                    local customLeftForearmLength = distance customLeftElbow.position customLeftWrist.position
                    local leftForearmScaleFactor = customLeftForearmLength / leftForearmLength
                    scale leftForearm [leftForearmScaleFactor, leftForearmScaleFactor, leftForearmScaleFactor]
                )
                
                -- 缩放右前臂，使其末端位置与右手腕辅助对象的位置一致
                local rightForearmEndPos = this.findNodeByName "ValveBiped.Bip01_R_Hand"
                if rightForearmEndPos != undefined and customRightWrist != undefined then (
                    local rightForearmLength = distance rightForearm.position rightForearmEndPos.position
                    local customRightForearmLength = distance customRightElbow.position customRightWrist.position
                    local rightForearmScaleFactor = customRightForearmLength / rightForearmLength
                    scale rightForearm [rightForearmScaleFactor, rightForearmScaleFactor, rightForearmScaleFactor]
                )
                
                -- 处理手腕对齐
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
                    "Waist"  -- 只保留 Waist
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

fn getScaleRatio point1 point2 =
(
    -- 根据骨骼位置判断是左边还是右边
    if point1.position.x < 0 then
    (
        -- 左边骨骼，取反计算
        return (-point1.position.x) / (-point2.position.x)
    )
    else
    (
        -- 右边骨骼，直接计算
        return point1.position.x / point2.position.x
    )
)

fn AdjustCustomHandModel = 
(
    -- 先尝试销毁已存在的对话框
    try(destroyDialog myToolRollout) catch()
    
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

    -- 确保在这里创建 GUI 界面
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
                -- 遍历所有选中的对象并根据位置存储到左右臂数组中
                for obj in selection do
                (
                    if obj.position.x < 0 then  -- 假设左侧对象的 X 坐标小于 0
                    (
                        appendIfUnique leftHandArmBones obj
                        format "左臂根骨骼对象 % 已存储。\n" obj.name
                    )
                    else if obj.position.x > 0 then  -- 假设右侧对象的 X 坐标大于 0
                    (
                        appendIfUnique rightHandArmBones obj
                        format "右臂根骨骼对象 % 已存储。\n" obj.name
                    )
                    else
                    (
                        format "对象 % 的位置无法识别为左臂或右臂。\n" obj.name
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
                -- 遍历所有选中的对象并根据位置存储到左右手腕数组中
                for obj in selection do
                (
                    if obj.position.x < 0 then
                    (
                        appendIfUnique leftHandWristBones obj
                        format "左手腕骨骼对象 % 已存储。\n" obj.name
                    )
                    else if obj.position.x > 0 then
                    (
                        appendIfUnique rightHandWristBones obj
                        format "右手腕骨骼对象 % 已存储。\n" obj.name
                    )
                    else
                    (
                        format "对象 % 的位置无法识别为左手腕或右手腕。\n" obj.name
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
                -- 遍历所有选中的对象并根据位置存储到左右小拇指数组中
                for obj in selection do
                (
                    if obj.position.x < 0 then
                    (
                        appendIfUnique leftHandPinkyBones obj
                        format "左小拇指骨骼对象 % 已存储。\n" obj.name
                    )
                    else if obj.position.x > 0 then
                    (
                        appendIfUnique rightHandPinkyBones obj
                        format "右小拇指骨骼对象 % 已存储。\n" obj.name
                    )
                    else
                    (
                        format "对象 % 的位置无法识别为左小拇指或右小拇指。\n" obj.name
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
                -- 遍历所有选中的对象并根据位置存储到左右中指末端数组中
                for obj in selection do
                (
                    if obj.position.x < 0 then
                    (
                        appendIfUnique leftHandMiddleBones obj
                        format "左中指末端骨骼对象 % 已存储。\n" obj.name
                    )
                    else if obj.position.x > 0 then
                    (
                        appendIfUnique rightHandMiddleBones obj
                        format "右中指末端骨骼对象 % 已存储。\n" obj.name
                    )
                    else
                    (
                        format "对象 % 的位置无法识别为左中指末端或右中指末端。\n" obj.name
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
                -- 遍历所有选中的对象并根据位置存储到左右中指根骨骼数组中
                for obj in selection do
                (
                    if obj.position.x < 0 then
                    (
                        appendIfUnique leftHandMiddleRootBones obj
                        format "左中指根骨骼对象 % 已存储。\n" obj.name
                    )
                    else if obj.position.x > 0 then
                    (
                        appendIfUnique rightHandMiddleRootBones obj
                        format "右中指根骨骼对象 % 已存储。\n" obj.name
                    )
                    else
                    (
                        format "对象 % 的位置无法识别为左中指根骨骼或右中指根骨骼。\n" obj.name
                    )
                )
                messageBox "左右中指根骨骼对象存储完成！" title:"完成"
            )
        )

        on btnExecute pressed do
        (
            -- 定义骨骼名称
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

            -- 遍历所有对象，根据位置和名称前缀判断
            for obj in objects do
            (
                if matchPattern obj.name pattern:"*Bip01*Clavicle*" then
                (
                    if obj.position.x < 0 then
                        leftClavicle = obj
                    else if obj.position.x > 0 then
                        rightClavicle = obj
                )
                else if matchPattern obj.name pattern:"*ValveBiped.ValveBiped*" then
                    valveBiped = obj
                else if matchPattern obj.name pattern:"*Bip01*Hand*" then
                (
                    if obj.position.x < 0 then
                        leftHand = obj
                    else if obj.position.x > 0 then
                        rightHand = obj
                )
                else if matchPattern obj.name pattern:"*Bip01*Finger4*" and not matchPattern obj.name pattern:"*Finger4[1-9]*" then
                (
                    if obj.position.x < 0 then
                        leftPinky = obj
                    else if obj.position.x > 0 then
                        rightPinky = obj
                )
                else if matchPattern obj.name pattern:"*Bip01*Finger22*" then
                (
                    if obj.position.x < 0 then
                        leftMiddle = obj
                    else if obj.position.x > 0 then
                        rightMiddle = obj
                )
                else if matchPattern obj.name pattern:"*Bip01*Finger2" and not matchPattern obj.name pattern:"*Finger2[1-9]*" then
                (
                    if obj.position.x < 0 then
                        leftMiddleRoot = obj
                    else if obj.position.x > 0 then
                        rightMiddleRoot = obj
                )
            )

            -- 输出位置信息
            if leftClavicle != undefined then
                format "左锁骨位置: %\n" leftClavicle.position
            else
                format "未找到左锁骨对象\n"

            if rightClavicle != undefined then
                format "右锁骨位置: %\n" rightClavicle.position
            else
                format "未找到右锁骨对象\n"

            if valveBiped != undefined then
                format "ValveBiped.ValveBiped 位置: %\n" valveBiped.position
            else
                format "未找到 ValveBiped.ValveBiped 对象\n"

            if leftHand != undefined then
                format "左手位置: %\n" leftHand.position
            else
                format "未找到左手对象\n"

            if rightHand != undefined then
                format "右手位置: %\n" rightHand.position
            else
                format "未找到右手对象\n"

            -- 检查是否有存储的左右臂根骨骼对象
            if leftHandArmBones.count != 0 and rightHandArmBones.count != 0 then
            (
                format "左臂根骨骼对象位置：\n"
                for obj in leftHandArmBones do
                    format "对象 % 的位置: %\n" obj.name obj.position
                format "右臂根骨骼对象位置：\n"
                for obj in rightHandArmBones do
                    format "对象 % 的位置: %\n" obj.name obj.position

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
                messageBox "请确保已存储左右臂根骨骼对象！" title:"错误"

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
                format "请确保已存储左手腕骨骼对象，并且已读取左手位置！\n"

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
                format "请确保已存储右手腕骨骼对象，并且已读取右手位置！\n"

            -- 读取并输出小拇指骨骼的位置
            if leftPinky != undefined then
                format "缩放后左小拇指位置: %\n" leftPinky.position
            else
                format "未找到左小拇指对象\n"

            if rightPinky != undefined then
                format "缩放后右小拇指位置: %\n" rightPinky.position
            else
                format "未找到右小拇指对象\n"

            -- 读取并输出小拇指辅助对象的位置
            if leftHandPinkyBones.count != 0 then
            (
                format "缩放后左小拇指辅助对象位置：\n"
                for obj in leftHandPinkyBones do
                    format "对象 % 的位置: %\n" obj.name obj.position
            )
            else
                format "未存储左小拇指辅助对象！\n"

            if rightHandPinkyBones.count != 0 then
            (
                format "缩放后右小拇指辅助对象位置：\n"
                for obj in rightHandPinkyBones do
                    format "对象 % 的位置: %\n" obj.name obj.position
            )
            else
                format "未存储右小拇指辅助对象！\n"

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
                format "左中指末端位置: %\n" leftMiddle.position
            else
                format "未找到左中指末端对象\n"

            if rightMiddle != undefined then
                format "右中指末端位置: %\n" rightMiddle.position
            else
                format "未找到右中指末端对象\n"

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
                format "请确保已存储左中指末端辅助对象，并且已读取左中指末端位置！\n"

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
                format "请确保已存储右中指末端辅助对象，并且已读取右中指末端位置！\n"

            -- 读取并输出中指根骨骼的位置，并计算差值应用于手臂辅助对象
            if leftMiddleRoot != undefined then
                format "左中指根骨骼位置: %\n" leftMiddleRoot.position
            else
                format "未找到左中指根骨骼对象\n"

            if rightMiddleRoot != undefined then
                format "右中指根骨骼位置: %\n" rightMiddleRoot.position
            else
                format "未找到右中指根骨骼对象\n"

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
                format "请确保已存储左中指根辅助对象，并且已读取左中指根骨骼位置！\n"

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
                format "请确保已存储右中指根辅助对象，并且已读取右中指根骨骼位置！\n"

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
                format "请确保已存储右小拇指辅助对象，并且已读取右小拇指位置！\n"
        )
    )

    -- 直接创建对话框
    createDialog myToolRollout
)

fn processAnkleSetup = (
    -- 保存权重数据
    local weightData = #()
    -- 添加赛马娘命名约定的支持
    local ankleHelpers = #("Right_ankle", "Left_ankle", "Ankle_R", "Ankle_L")
    
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
    
    -- 确定模型类型（标准模型或赛马娘模型）
    local isUmaModel = (getNodeByName "Ankle_L" != undefined or getNodeByName "Ankle_R" != undefined)
    
    -- 删除原来的ankle辅助骨骼
    if isUmaModel then (
        -- 赛马娘模型命名
        local leftAnkle = getNodeByName "Ankle_L"
        local rightAnkle = getNodeByName "Ankle_R"
        if leftAnkle != undefined do delete leftAnkle
        if rightAnkle != undefined do delete rightAnkle
    ) else (
        -- 标准模型命名
        local leftAnkle = getNodeByName "Left_ankle"
        local rightAnkle = getNodeByName "Right_ankle"
        if leftAnkle != undefined do delete leftAnkle
        if rightAnkle != undefined do delete rightAnkle
    )
    
    -- 处理左脚
    local leftFoot = getNodeByName "ValveBiped.Bip01_L_Foot"
    local leftToe = getNodeByName "ValveBiped.Bip01_L_Toe0"
    local leftToeDummy
    
    if isUmaModel then
        leftToeDummy = getNodeByName "Toe_L"
    else
        leftToeDummy = getNodeByName "Left toe"
    
    if leftFoot != undefined do
    (
        -- 移动到指定位置
        leftFoot.pos.z = 2.514
        -- 复制并重命名为新的ankle
        local newLeftAnkle = copy leftFoot
        -- 根据模型类型命名
        newLeftAnkle.name = if isUmaModel then "Ankle_L" else "Left_ankle"
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
    local rightToeDummy
    
    if isUmaModel then
        rightToeDummy = getNodeByName "Toe_R"
    else
        rightToeDummy = getNodeByName "Right toe"
    
    if rightFoot != undefined do
    (
        -- 移动到指定位置
        rightFoot.pos.z = 2.514
        -- 复制并重命名为新的ankle
        local newRightAnkle = copy rightFoot
        -- 根据模型类型命名
        newRightAnkle.name = if isUmaModel then "Ankle_R" else "Right_ankle"
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
                -- 首先为所有帧创建初始关键帧
                for frame in #(0, 10, 20, 30) do
                (
                    sliderTime = frame
                    for obj in footHelpers do
                    (
                        obj.rotation.controller = Euler_XYZ()
                        addNewKey obj.rotation.controller frame
                    )
                    for boneName in footBones do
                    (
                        local obj = getNodeByName boneName
                        if obj != undefined do
                        (
                            obj.rotation.controller = Euler_XYZ()
                            addNewKey obj.rotation.controller frame
                        )
                    )
                )
                
                -- 然后分别为每个帧设置具体的旋转值
                -- 第0帧保持原始状态
                
                -- 第10帧旋转足辅助对象和骨骼
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

                -- 第20帧旋转足辅助对象和骨骼
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

                -- 第30帧旋转足辅助对象和骨骼
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
            if ddlPresets.selected != undefined then (
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

fn SplitByMaterial = (
    rollout SplitByMaterialRollout "按材质拆分" width:160 height:120
(
    checkbox chkKeepOriginal "保留原始对象" checked:false
    progressBar progBar "进度:" color:blue
    button btnExecute "执行拆分" width:140 height:40 align:#center
    
    fn splitByMaterial obj = (
        if obj == undefined or not isValidNode obj do return false
        
        format "原始对象类型: %\n" (classof obj)
        
        -- 获取原始对象信息
        local origName = obj.name
        
        -- 获取材质信息
        local matArray = #()
        if classOf obj.material == MultiMaterial then (
            for i = 1 to obj.material.numsubs do (
                append matArray obj.material[i]
            )
        ) else if obj.material != undefined then (
            append matArray obj.material
        )
        
        -- 存储结果对象
        local resultObjs = #()
        
        -- 为每个材质创建对象
        for i = 1 to matArray.count do (
            progBar.value = 100.0 * i / matArray.count
            
            -- 复制对象（保留所有修改器和权重）
            local newObj = copy obj
            format "复制后对象类型: %\n" (classof newObj)
            
            local matName = if matArray[i].name != undefined then matName = matArray[i].name else "mat" + i as string
            newObj.name = origName + "_" + matName
            
            -- 设置为面选择模式
            modPanel.setCurrentObject newObj
            max modify mode
            
            -- 根据对象类型使用不同的操作方法
            case classof newObj of (
                Editable_mesh: (
                    subObjectLevel = 4  -- mesh面级别
                    -- 选择对应材质ID的面
                    local facesToKeep = #{}
                    for f = 1 to newObj.numfaces do (
                        if (getFaceMatID newObj f) == i do (
                            append facesToKeep f
                        )
                    )
                    -- 创建要删除的面的BitArray（反选）
                    local facesToDelete = #{1..newObj.numfaces} - facesToKeep
                    -- 删除不需要的面
                    meshop.deleteFaces newObj facesToDelete
                )
                
                Editable_Poly: (
                    subObjectLevel = 4  -- poly面级别
                    -- 选择对应材质ID的面
                    local facesToKeep = #{}
                    for f = 1 to polyop.getNumFaces newObj do (
                        if (polyop.getFaceMatID newObj f) == i do (
                            append facesToKeep f
                        )
                    )
                    -- 创建要删除的面的BitArray（反选）
                    local facesToDelete = #{1..polyop.getNumFaces newObj} - facesToKeep
                    -- 删除不需要的面
                    polyop.deleteFaces newObj facesToDelete
                )
                
                default: (
                    format "不支持的对象类型: %\n" (classof newObj)
                    continue
                )
            )
            
            -- 重置选择模式
            subObjectLevel = 0
            
            -- 设置单一材质
            newObj.material = matArray[i]
            
            append resultObjs newObj
        )
        
        -- 处理原始对象
        if not chkKeepOriginal.checked do (
            delete obj
        )
        
        resultObjs
    )
    
    on btnExecute pressed do (
        local sel = getCurrentSelection()
        if sel.count == 0 then (
            messageBox "请先选择要拆分的模型!" title:"提示"
            return false
        )
        
        -- 禁用按钮防止重复操作
        btnExecute.enabled = false
        
        -- 执行拆分
        with undo on (
            for obj in sel do (
                splitByMaterial obj
            )
        )
        
        -- 重置进度条
        progBar.value = 0
        
        -- 恢复按钮
        btnExecute.enabled = true
        
        messageBox "拆分完成!" title:"提示"
    )
)

-- 创建对话框
createDialog SplitByMaterialRollout 
)

fn fixFallenCharacter = (
    -- 记录当前选择，以便稍后恢复
    local currentSelection = getCurrentSelection()
    
    -- 找到ValveBiped.Bip01_Pelvis骨骼
    local pelvisBone = getNodeByName "ValveBiped.Bip01_Pelvis"
    
    if pelvisBone != undefined then (
        -- 记录所有子对象
        local childObjects = for child in objects where child.parent == pelvisBone collect child
        
        -- 断开所有连接到pelvis的骨骼
        for child in childObjects do (
            child.parent = undefined
        )
        
        -- 移动pelvis到指定位置
        pelvisBone.position = [0, -1.442, 35.35]
        
        -- 恢复所有连接
        for child in childObjects do (
            child.parent = pelvisBone
        )
        
        -- 通知用户操作完成
        messageBox "倒地修复完成！骨盆已重新定位。" title:"操作成功"
    ) else (
        -- 如果找不到pelvis骨骼，显示错误消息
        messageBox "无法找到ValveBiped.Bip01_Pelvis骨骼！" title:"错误"
    )
    
    -- 恢复原始选择
    select currentSelection
)

fn quickHeightAdjustment = (
    -- 找到Armature和ValveBiped.Bip01_Pelvis骨骼
    global gArmatureObj = getNodeByName "Armature"
    global gPelvisBone = getNodeByName "ValveBiped.Bip01_Pelvis"
    global gOriginalScale = 350.0 -- 初始默认值
    global gDisplayScale = 350.0 -- 显示用的缩放值（初始值）
    
    if gArmatureObj != undefined and gPelvisBone != undefined then (
        -- 获取Armature原始缩放值
        gOriginalScale = gArmatureObj.scale.x  -- 实际缩放值
        gDisplayScale = gOriginalScale * 100 -- 显示用的缩放值
        
        -- 打开对话框让用户输入新的缩放值
        rollout heightAdjustRollout "快速调整身高" width:300 height:140 (
            -- 当前缩放值显示（完全禁用，而不仅是只读）
            label lblCurrentScale "当前缩放值：" pos:[30,20] width:80 height:20
            edittext txtCurrentScale text:(gDisplayScale as string) pos:[110,20] width:160 height:20 readonly:true enabled:false
            
            -- 新缩放值输入框（默认为空）
            label lblNewScale "新缩放值：" pos:[30,50] width:80 height:20
            edittext txtNewScale "" pos:[110,50] width:160 height:20
            
            -- 按钮并排放置
            button btnApply "应用调整" width:120 height:30 pos:[20, 90]
            button btnReset "重置身高" width:120 height:30 pos:[160, 90] enabled:false
            
            on btnApply pressed do (
                -- 检查输入是否有效
                local newScaleStr = txtNewScale.text
                local newDisplayScale = try(newScaleStr as float) catch(undefined)
                
                if newDisplayScale == undefined then (
                    messageBox "请输入有效的数字！" title:"错误"
                    return()
                )
                
                -- 计算实际缩放值（除以100）
                local newActualScale = newDisplayScale / 100.0
                
                -- 记录Pelvis的原始父级
                local originalParent = gPelvisBone.parent
                
                -- 链接Pelvis到Armature
                gPelvisBone.parent = gArmatureObj
                
                -- 设置Armature的缩放值
                gArmatureObj.scale = [newActualScale, newActualScale, newActualScale]
                
                -- 断开连接，恢复原始父级
                gPelvisBone.parent = originalParent
                
                -- 更新当前缩放值显示
                txtCurrentScale.text = newDisplayScale as string
                
                -- 激活重置按钮
                btnReset.enabled = true
                
                -- 通知用户操作完成
                messageBox "身高调整完成！" title:"操作成功"
            )
            
            on btnReset pressed do (
                -- 记录Pelvis的原始父级
                local originalParent = gPelvisBone.parent
                
                -- 链接Pelvis到Armature
                gPelvisBone.parent = gArmatureObj
                
                -- 重置为原始缩放值
                gArmatureObj.scale = [gOriginalScale, gOriginalScale, gOriginalScale]
                
                -- 断开连接，恢复原始父级
                gPelvisBone.parent = originalParent
                
                -- 更新显示
                txtCurrentScale.text = (gDisplayScale as string)
                txtNewScale.text = ""
                
                -- 禁用重置按钮
                btnReset.enabled = false
                
                -- 通知用户操作完成
                messageBox "身高已重置为原始值！" title:"操作成功"
            )
        )
        
        createDialog heightAdjustRollout
    ) else (
        -- 如果找不到所需对象，显示错误消息
        if gArmatureObj == undefined and gPelvisBone == undefined then
            messageBox "无法找到Armature和ValveBiped.Bip01_Pelvis！" title:"错误"
        else if gArmatureObj == undefined then
            messageBox "无法找到Armature对象！" title:"错误"
        else
            messageBox "无法找到ValveBiped.Bip01_Pelvis骨骼！" title:"错误"
    )
)

-- 定义子界面的rollout
rollout buttonsRollout "工具" width:600 height:1000 (
    button btnScript12 "重命名预设管理器" pos:[10,10] width:580 height:40
    button btnScript4 "一键变形开关" pos:[10,60] width:580 height:40
    button btnScript7 "一键选中骨骼" pos:[10,110] width:580 height:40
    button btnScript2 "T-Pose预设管理器" pos:[10,160] width:580 height:40
    button btnScript8 "一键对骨" pos:[10,210] width:580 height:40
    button btnScript6 "一键嫁接" pos:[10,260] width:580 height:40
    button btnScript5 "一键表情" pos:[10,310] width:580 height:40
    button btnScript9 "智能描边" pos:[10,360] width:580 height:40
    button btnScript3 "一键VRD动作" pos:[10,410] width:580 height:40
    button btnScript11 "一键足VRD动作" pos:[10,460] width:580 height:40
    button btnScript10 "一键手模调整" pos:[10,510] width:580 height:40
    button btnScript13 "快速飘动编写" pos:[10,560] width:580 height:40
    button btnScript21 "权重合并" pos:[10,610] width:290 height:40
    button btnScript23 "模型按材质拆分" pos:[300,610] width:290 height:40
    button btnScript22 "骨骼/辅助对象名称输出" pos:[10,660] width:580 height:40
    button btnScript14 "倒地修复" pos:[10,710] width:290 height:40 -- 修改位置从760改为710
    button btnScript15 "快速调整身高" pos:[300,710] width:290 height:40 -- 修改位置从760改为710
    button btnScript1 "一键导出" pos:[10,760] width:580 height:40 -- 调整到最下方，位置从810改为760

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
    on btnScript14 pressed do (
        fixFallenCharacter()
    )
    on btnScript15 pressed do ( -- 新增按钮的事件处理
        quickHeightAdjustment()
    )
    on btnScript21 pressed do (
        WeightMerging()
    )
    on btnScript22 pressed do (
        BoneNameLister()
    )
    on btnScript23 pressed do (
        SplitByMaterial()
    )
)

-- 定义主界面的rollout
rollout mainRollout "一键工具箱" width:640 height:1100 (
    label lblInfo "制作者：B站メジロ_McQueen/ChatGPT4o/Deepseek/Claude3.5/Claude3.7" pos:[10,10] width:620 height:30
    subRollout subRolloutContainer "工具" pos:[10,50] width:620 height:1000
)

-- 创建主界面对话框并添加子界面
try (destroyDialog mainDialog) catch()
mainDialog = newRolloutFloater "一键工具箱" 640 1100
addRollout mainRollout mainDialog

-- 将子界面添加到 subRollout 容器中
addSubRollout mainRollout.subRolloutContainer buttonsRollout