@echo off
setlocal enabledelayedexpansion

rem ��ȡ�û������֡��
set /p frame_count=�����붯��֡��:

rem һ����ɫ���� (L4D1��ɫ)��ʹ�������ļ������ƺͶ�Ӧ��VMT�ļ���
set l4d1_characters[0]=������˹
set l4d1_vmt_names[0]=biker

set l4d1_characters[1]=�ȶ�
set l4d1_vmt_names[1]=namvet

set l4d1_characters[2]=·��˹
set l4d1_vmt_names[2]=manager

set l4d1_characters[3]=����
set l4d1_vmt_names[3]=teenangst

rem ������ɫ���� (L4D2��ɫ)��ʹ�������ļ������ƺͶ�Ӧ��VMT�ļ���
set l4d2_characters[0]=����
set l4d2_vmt_names[0]=coach

set l4d2_characters[1]=���
set l4d2_vmt_names[1]=gambler

set l4d2_characters[2]=����˹
set l4d2_vmt_names[2]=mechanic

set l4d2_characters[3]=��ѩ��
set l4d2_vmt_names[3]=producer

rem Ϊһ����ɫ��̬����VMT�ļ�·��������
for /l %%i in (0,1,3) do (
    set character=!l4d1_characters[%%i]!
    set vmt_name=!l4d1_vmt_names[%%i]!

    rem VMT�ļ�·����ȷ�����ɵ���ȷ�Ľ�ɫ���ļ���
    set vmt_file_lobby=output\!name! !character!\materials\vgui\s_panel_lobby_!vmt_name!.vmt
    set vmt_file_portrait=output\!name! !character!\materials\vgui\s_panel_!vmt_name!.vmt
    set vmt_file_incap=output\!name! !character!\materials\vgui\s_panel_!vmt_name!_incap.vmt

    rem ȷ��·������
    if not exist "output\!name! !character!\materials\vgui" (
        mkdir "output\!name! !character!\materials\vgui"
    )

    rem ���ɴ���VMT (s_panel_lobby_xxxx.vmt)
    (
        echo UnlitGeneric {
        echo    $translucent 1
        echo    $basetexture "VGUI\s_panel_lobby_!vmt_name!"
        echo    $vertexcolor 1
        echo    $vertexalpha 1
        echo    $no_fullbright 1
        echo    $ignorez 1
        echo    $additive 0
        echo    "Proxies"
        echo    {
        echo        "MaterialModifyAnimated"
        echo        {
        echo            "animatedtexturevar" "$basetexture"
        echo            "animatedtextureframenumvar" "$frame"
        echo            "animatedtextureframerate" "!frame_count!"
        echo        }
        echo    }
        echo }
    ) > "!vmt_file_lobby!"

    rem ����ͷ��VMT (s_panel_xxxx.vmt)
    (
        echo UnlitGeneric {
        echo    $translucent 1
        echo    $basetexture "VGUI\s_panel_!vmt_name!"
        echo    $vertexcolor 1
        echo    $vertexalpha 1
        echo    $no_fullbright 1
        echo    $ignorez 1
        echo    $additive 0
        echo    "Proxies"
        echo    {
        echo        "MaterialModifyAnimated"
        echo        {
        echo            "animatedtexturevar" "$basetexture"
        echo            "animatedtextureframenumvar" "$frame"
        echo            "animatedtextureframerate" "!frame_count!"
        echo        }
        echo    }
        echo }
    ) > "!vmt_file_portrait!"

    rem ���ɵ���״̬VMT (s_panel_xxxx_incap.vmt)
    (
        echo UnlitGeneric {
        echo    $translucent 1
        echo    $basetexture "VGUI\s_panel_!vmt_name!_incap"
        echo    $vertexcolor 1
        echo    $vertexalpha 1
        echo    $no_fullbright 1
        echo    $ignorez 1
        echo    $additive 0
        echo    "Proxies"
        echo    {
        echo        "MaterialModifyAnimated"
        echo        {
        echo            "animatedtexturevar" "$basetexture"
        echo            "animatedtextureframenumvar" "$frame"
        echo            "animatedtextureframerate" "!frame_count!"
        echo        }
        echo    }
        echo }
    ) > "!vmt_file_incap!"
)

rem Ϊ������ɫ��̬����VMT�ļ�·��������
for /l %%i in (0,1,3) do (
    set character=!l4d2_characters[%%i]!
    set vmt_name=!l4d2_vmt_names[%%i]!

    rem VMT�ļ�·����ȷ�����ɵ���ȷ�Ľ�ɫ���ļ���
    set vmt_file_lobby=output\!name! !character!\materials\vgui\select_!vmt_name!.vmt
    set vmt_file_portrait=output\!name! !character!\materials\vgui\s_panel_!vmt_name!.vmt
    set vmt_file_incap=output\!name! !character!\materials\vgui\s_panel_!vmt_name!_incap.vmt

    rem ȷ��·������
    if not exist "output\!name! !character!\materials\vgui" (
        mkdir "output\!name! !character!\materials\vgui"
    )

    rem ���ɴ���VMT (select_xxxx.vmt)
    (
        echo UnlitGeneric {
        echo    $translucent 1
        echo    $basetexture "VGUI\select_!vmt_name!"
        echo    $vertexcolor 1
        echo    $vertexalpha 1
        echo    $no_fullbright 1
        echo    $ignorez 1
        echo    $additive 0
        echo    "Proxies"
        echo    {
        echo        "MaterialModifyAnimated"
        echo        {
        echo            "animatedtexturevar" "$basetexture"
        echo            "animatedtextureframenumvar" "$frame"
        echo            "animatedtextureframerate" "!frame_count!"
        echo        }
        echo    }
        echo }
    ) > "!vmt_file_lobby!"

    rem ����ͷ��VMT (s_panel_xxxx.vmt)
    (
        echo UnlitGeneric {
        echo    $translucent 1
        echo    $basetexture "VGUI\s_panel_!vmt_name!"
        echo    $vertexcolor 1
        echo    $vertexalpha 1
        echo    $no_fullbright 1
        echo    $ignorez 1
        echo    $additive 0
        echo    "Proxies"
        echo    {
        echo        "MaterialModifyAnimated"
        echo        {
        echo            "animatedtexturevar" "$basetexture"
        echo            "animatedtextureframenumvar" "$frame"
        echo            "animatedtextureframerate" "!frame_count!"
        echo        }
        echo    }
        echo }
    ) > "!vmt_file_portrait!"

    rem ���ɵ���״̬VMT (s_panel_xxxx_incap.vmt)
    (
        echo UnlitGeneric {
        echo    $translucent 1
        echo    $basetexture "VGUI\s_panel_!vmt_name!_incap"
        echo    $vertexcolor 1
        echo    $vertexalpha 1
        echo    $no_fullbright 1
        echo    $ignorez 1
        echo    $additive 0
        echo    "Proxies"
        echo    {
        echo        "MaterialModifyAnimated"
        echo        {
        echo            "animatedtexturevar" "$basetexture"
        echo            "animatedtextureframenumvar" "$frame"
        echo            "animatedtextureframerate" "!frame_count!"
        echo        }
        echo    }
        echo }
    ) > "!vmt_file_incap!"
)

echo ��̬VGUI�ļ������ɣ�֡��Ϊ: !frame_count!
pause
