@echo off
setlocal enabledelayedexpansion

rem 弹出输入框获取用户输入的替换名称
set /p name=请输入替换的名称:

rem 弹出输入框获取作者名称
set /p author=请输入作者名称:

rem 弹出输入框获取版本号
set /p version=请输入版本号:

rem 添加动态VGUI制作选项
set /p dynamic_vgui=是否制作动态VGUI？(是/否):

rem 假设用户已经创建了一个名为multiline.txt的文件来存储多行内容
set "multi_line_file=Description.txt"

rem 设置VPK.exe所在的目录
set VPK_PATH="E:\SteamLibrary\steamapps\common\Left 4 Dead 2\bin\vpk.exe"


rem 替换文件夹名称提前处理
set names[0]=弗朗西斯
set names[1]=教练
set names[2]=尼克
set names[3]=路易斯
set names[4]=埃利斯
set names[5]=比尔
set names[6]=罗雪儿
set names[7]=佐伊
set names[8]=比尔尸体

rem 创建output文件夹和带有用户输入名称的子文件夹
mkdir "output"
for /l %%i in (0,1,8) do (
    mkdir "output\!name! !names[%%i]!\models\survivors"
    if %%i lss 8 (
        mkdir "output\!name! !names[%%i]!\models\weapons\arms"
    )
)

rem 创建比尔尸体文件夹
mkdir "output\!name! 比尔尸体\models\survivors\NamVet"

rem 复制survivors文件到相应的文件夹，直接覆盖目标文件
for %%f in ("models\survivors\*.mdl") do (
    set "basename=%%~nf"
    if "%%~nxf"=="survivor_biker.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 弗朗西斯\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 弗朗西斯\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 弗朗西斯\models\survivors\"
    ) else if "%%~nxf"=="survivor_coach.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 教练\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 教练\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 教练\models\survivors\"
    ) else if "%%~nxf"=="survivor_gambler.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 尼克\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 尼克\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 尼克\models\survivors\"
    ) else if "%%~nxf"=="survivor_manager.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 路易斯\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 路易斯\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 路易斯\models\survivors\"
    ) else if "%%~nxf"=="survivor_mechanic.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 埃利斯\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 埃利斯\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 埃利斯\models\survivors\"
    ) else if "%%~nxf"=="survivor_namvet.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 比尔\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 比尔\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 比尔\models\survivors\"
    ) else if "%%~nxf"=="survivor_producer.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 罗雪儿\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 罗雪儿\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 罗雪儿\models\survivors\"
    ) else if "%%~nxf"=="survivor_teenangst.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! 佐伊\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! 佐伊\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! 佐伊\models\survivors\"
    )
)

rem 复制比尔尸体的模型文件到相应文件夹
for %%f in ("models\survivors\NamVet\*.mdl") do (
    if "%%~nxf"=="namvet_deathpose.mdl" (
        copy /y "models\survivors\NamVet\%%~nxf" "output\!name! 比尔尸体\models\survivors\NamVet\"
        copy /y "models\survivors\NamVet\%%~nf.dx90.vtx" "output\!name! 比尔尸体\models\survivors\NamVet\"
        copy /y "models\survivors\NamVet\%%~nf.vvd" "output\!name! 比尔尸体\models\survivors\NamVet\"
    )
)

rem 复制weapons\arms文件到相应的文件夹，直接覆盖目标文件
for %%f in ("models\weapons\arms\*.mdl") do (
    set "basename=%%~nf"
    if "%%~nxf"=="v_arms_bill.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 比尔\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 比尔\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 比尔\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_coach_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 教练\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 教练\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 教练\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_francis.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 弗朗西斯\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 弗朗西斯\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 弗朗西斯\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_gambler_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 尼克\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 尼克\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 尼克\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_producer_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 罗雪儿\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 罗雪儿\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 罗雪儿\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_mechanic_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 埃利斯\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 埃利斯\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 埃利斯\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_louis.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 路易斯\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 路易斯\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 路易斯\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_zoey.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! 佐伊\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! 佐伊\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! 佐伊\models\weapons\arms\"
    )
)

rem 复制addonimage.jpg和addoninfo.txt到各个文件夹中，并替换内容
for /l %%i in (0,1,8) do (
    copy /y "addonimage.jpg" "output\!name! !names[%%i]!\"
    copy /y "addoninfo.txt" "output\!name! !names[%%i]!\"

    rem 替换addoninfo.txt中的内容并保存为临时文件
    (
        setlocal enabledelayedexpansion
        set "line_number=0"
        for /f "delims=" %%a in ('type "output\!name! !names[%%i]!\addoninfo.txt"') do (
            set /a line_number+=1
            set "line=%%a"
            if !line_number! equ 3 set "line=addontitle "!name!替换!names[%%i]!""
            if !line_number! equ 6 set "line=addonversion "!version!""
            if !line_number! equ 7 set "line=addonauthor "!author!""
            if !line_number! equ 8 set "line=addonauthorSteamID "!author!""
            if !line_number! equ 10 (
                type "%multi_line_file%"
            ) else (
                echo !line!
            )
        )
        endlocal
    ) > "output\!name! !names[%%i]!\addoninfo_tmp.txt"

    rem 使用PowerShell将文件转换为UTF-8无BOM编码
    powershell -Command "$txt = Get-Content 'output\!name! !names[%%i]!\addoninfo_tmp.txt'; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllLines('output\!name! !names[%%i]!\addoninfo.txt', $txt, $Utf8NoBomEncoding)"

    rem 删除临时文件
    del "output\!name! !names[%%i]!\addoninfo_tmp.txt"
)

rem VGUI部分直接复制并重命名VTF文件
for /d %%D in (output\*) do (
    set "folder_name=%%~nxD"
    rem 检查是否是比尔尸体，跳过比尔尸体的VGUI复制
    if "!folder_name!"=="!name! 比尔尸体" (
        echo 跳过比尔尸体文件夹的VGUI复制
    ) else (
        rem 复制VTF文件并在复制时重命名
        mkdir "%%D\materials\vgui" 2>nul
        if not "!folder_name!"=="!folder_name:佐伊=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\select_zoey.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_teenangst.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_teenangst_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:比尔=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\select_bill.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_namvet.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_namvet_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:弗朗西斯=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\select_francis.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_biker.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_biker_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:路易斯=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\select_louis.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_manager.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_manager_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:尼克=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\s_panel_lobby_gambler.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_gambler.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_gambler_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:罗雪儿=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\s_panel_lobby_producer.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_producer.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_producer_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:教练=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\s_panel_lobby_coach.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_coach.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_coach_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:埃利斯=!" (
            copy /y "materials\vgui\大厅.vtf" "%%D\materials\vgui\s_panel_lobby_mechanic.vtf"
            copy /y "materials\vgui\头像.vtf" "%%D\materials\vgui\s_panel_mechanic.vtf"
            copy /y "materials\vgui\倒地.vtf" "%%D\materials\vgui\s_panel_mechanic_incap.vtf"
        )
    )
)

if /i "!dynamic_vgui!"=="是" (
    call DynamicVGUI.bat "!name!"
) else (
    echo 你选择了不制作动态VGUI，继续按照原有流程执行。
)

rem 打包处理完的文件夹
cd output
for /d %%D in (*) do (
    %VPK_PATH% "%%D"
    echo 打包完成: %%D
)

pause
