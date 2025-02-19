@echo off
setlocal enabledelayedexpansion

rem ����������ȡ�û�������滻����
set /p name=�������滻������:

rem ����������ȡ��������
set /p author=��������������:

rem ����������ȡ�汾��
set /p version=������汾��:

rem ��Ӷ�̬VGUI����ѡ��
set /p dynamic_vgui=�Ƿ�������̬VGUI��(��/��):

rem �����û��Ѿ�������һ����Ϊmultiline.txt���ļ����洢��������
set "multi_line_file=Description.txt"

rem ����VPK.exe���ڵ�Ŀ¼
set VPK_PATH="E:\SteamLibrary\steamapps\common\Left 4 Dead 2\bin\vpk.exe"


rem �滻�ļ���������ǰ����
set names[0]=������˹
set names[1]=����
set names[2]=���
set names[3]=·��˹
set names[4]=����˹
set names[5]=�ȶ�
set names[6]=��ѩ��
set names[7]=����
set names[8]=�ȶ�ʬ��

rem ����output�ļ��кʹ����û��������Ƶ����ļ���
mkdir "output"
for /l %%i in (0,1,8) do (
    mkdir "output\!name! !names[%%i]!\models\survivors"
    if %%i lss 8 (
        mkdir "output\!name! !names[%%i]!\models\weapons\arms"
    )
)

rem �����ȶ�ʬ���ļ���
mkdir "output\!name! �ȶ�ʬ��\models\survivors\NamVet"

rem ����survivors�ļ�����Ӧ���ļ��У�ֱ�Ӹ���Ŀ���ļ�
for %%f in ("models\survivors\*.mdl") do (
    set "basename=%%~nf"
    if "%%~nxf"=="survivor_biker.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ������˹\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ������˹\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ������˹\models\survivors\"
    ) else if "%%~nxf"=="survivor_coach.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ����\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ����\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ����\models\survivors\"
    ) else if "%%~nxf"=="survivor_gambler.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ���\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ���\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ���\models\survivors\"
    ) else if "%%~nxf"=="survivor_manager.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ·��˹\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ·��˹\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ·��˹\models\survivors\"
    ) else if "%%~nxf"=="survivor_mechanic.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ����˹\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ����˹\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ����˹\models\survivors\"
    ) else if "%%~nxf"=="survivor_namvet.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! �ȶ�\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! �ȶ�\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! �ȶ�\models\survivors\"
    ) else if "%%~nxf"=="survivor_producer.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ��ѩ��\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ��ѩ��\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ��ѩ��\models\survivors\"
    ) else if "%%~nxf"=="survivor_teenangst.mdl" (
        copy /y "models\survivors\%%~nxf" "output\!name! ����\models\survivors\"
        copy /y "models\survivors\%%~nf.dx90.vtx" "output\!name! ����\models\survivors\"
        copy /y "models\survivors\%%~nf.vvd" "output\!name! ����\models\survivors\"
    )
)

rem ���Ʊȶ�ʬ���ģ���ļ�����Ӧ�ļ���
for %%f in ("models\survivors\NamVet\*.mdl") do (
    if "%%~nxf"=="namvet_deathpose.mdl" (
        copy /y "models\survivors\NamVet\%%~nxf" "output\!name! �ȶ�ʬ��\models\survivors\NamVet\"
        copy /y "models\survivors\NamVet\%%~nf.dx90.vtx" "output\!name! �ȶ�ʬ��\models\survivors\NamVet\"
        copy /y "models\survivors\NamVet\%%~nf.vvd" "output\!name! �ȶ�ʬ��\models\survivors\NamVet\"
    )
)

rem ����weapons\arms�ļ�����Ӧ���ļ��У�ֱ�Ӹ���Ŀ���ļ�
for %%f in ("models\weapons\arms\*.mdl") do (
    set "basename=%%~nf"
    if "%%~nxf"=="v_arms_bill.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! �ȶ�\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! �ȶ�\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! �ȶ�\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_coach_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ����\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ����\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ����\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_francis.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ������˹\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ������˹\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ������˹\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_gambler_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ���\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ���\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ���\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_producer_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ��ѩ��\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ��ѩ��\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ��ѩ��\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_mechanic_new.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ����˹\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ����˹\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ����˹\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_louis.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ·��˹\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ·��˹\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ·��˹\models\weapons\arms\"
    ) else if "%%~nxf"=="v_arms_zoey.mdl" (
        copy /y "models\weapons\arms\%%~nxf" "output\!name! ����\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.dx90.vtx" "output\!name! ����\models\weapons\arms\"
        copy /y "models\weapons\arms\%%~nf.vvd" "output\!name! ����\models\weapons\arms\"
    )
)

rem ����addonimage.jpg��addoninfo.txt�������ļ����У����滻����
for /l %%i in (0,1,8) do (
    copy /y "addonimage.jpg" "output\!name! !names[%%i]!\"
    copy /y "addoninfo.txt" "output\!name! !names[%%i]!\"

    rem �滻addoninfo.txt�е����ݲ�����Ϊ��ʱ�ļ�
    (
        setlocal enabledelayedexpansion
        set "line_number=0"
        for /f "delims=" %%a in ('type "output\!name! !names[%%i]!\addoninfo.txt"') do (
            set /a line_number+=1
            set "line=%%a"
            if !line_number! equ 3 set "line=addontitle "!name!�滻!names[%%i]!""
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

    rem ʹ��PowerShell���ļ�ת��ΪUTF-8��BOM����
    powershell -Command "$txt = Get-Content 'output\!name! !names[%%i]!\addoninfo_tmp.txt'; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllLines('output\!name! !names[%%i]!\addoninfo.txt', $txt, $Utf8NoBomEncoding)"

    rem ɾ����ʱ�ļ�
    del "output\!name! !names[%%i]!\addoninfo_tmp.txt"
)

rem VGUI����ֱ�Ӹ��Ʋ�������VTF�ļ�
for /d %%D in (output\*) do (
    set "folder_name=%%~nxD"
    rem ����Ƿ��Ǳȶ�ʬ�壬�����ȶ�ʬ���VGUI����
    if "!folder_name!"=="!name! �ȶ�ʬ��" (
        echo �����ȶ�ʬ���ļ��е�VGUI����
    ) else (
        rem ����VTF�ļ����ڸ���ʱ������
        mkdir "%%D\materials\vgui" 2>nul
        if not "!folder_name!"=="!folder_name:����=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\select_zoey.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_teenangst.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_teenangst_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:�ȶ�=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\select_bill.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_namvet.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_namvet_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:������˹=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\select_francis.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_biker.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_biker_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:·��˹=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\select_louis.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_manager.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_manager_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:���=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_lobby_gambler.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_gambler.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_gambler_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:��ѩ��=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_lobby_producer.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_producer.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_producer_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:����=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_lobby_coach.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_coach.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_coach_incap.vtf"
        ) else if not "!folder_name!"=="!folder_name:����˹=!" (
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_lobby_mechanic.vtf"
            copy /y "materials\vgui\ͷ��.vtf" "%%D\materials\vgui\s_panel_mechanic.vtf"
            copy /y "materials\vgui\����.vtf" "%%D\materials\vgui\s_panel_mechanic_incap.vtf"
        )
    )
)

if /i "!dynamic_vgui!"=="��" (
    call DynamicVGUI.bat "!name!"
) else (
    echo ��ѡ���˲�������̬VGUI����������ԭ������ִ�С�
)

rem �����������ļ���
cd output
for /d %%D in (*) do (
    %VPK_PATH% "%%D"
    echo ������: %%D
)

pause
