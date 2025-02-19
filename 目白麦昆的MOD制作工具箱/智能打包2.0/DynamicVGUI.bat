@echo off
setlocal enabledelayedexpansion

rem 获取用户输入的帧数
set /p frame_count=请输入动画帧数:

rem 一代角色数组 (L4D1角色)，使用中文文件夹名称和对应的VMT文件名
set l4d1_characters[0]=弗朗西斯
set l4d1_vmt_names[0]=biker

set l4d1_characters[1]=比尔
set l4d1_vmt_names[1]=namvet

set l4d1_characters[2]=路易斯
set l4d1_vmt_names[2]=manager

set l4d1_characters[3]=佐伊
set l4d1_vmt_names[3]=teenangst

rem 二代角色数组 (L4D2角色)，使用中文文件夹名称和对应的VMT文件名
set l4d2_characters[0]=教练
set l4d2_vmt_names[0]=coach

set l4d2_characters[1]=尼克
set l4d2_vmt_names[1]=gambler

set l4d2_characters[2]=埃利斯
set l4d2_vmt_names[2]=mechanic

set l4d2_characters[3]=罗雪儿
set l4d2_vmt_names[3]=producer

rem 为一代角色动态生成VMT文件路径和内容
for /l %%i in (0,1,3) do (
    set character=!l4d1_characters[%%i]!
    set vmt_name=!l4d1_vmt_names[%%i]!

    rem VMT文件路径，确保生成到正确的角色子文件夹
    set vmt_file_lobby=output\!name! !character!\materials\vgui\s_panel_lobby_!vmt_name!.vmt
    set vmt_file_portrait=output\!name! !character!\materials\vgui\s_panel_!vmt_name!.vmt
    set vmt_file_incap=output\!name! !character!\materials\vgui\s_panel_!vmt_name!_incap.vmt

    rem 确保路径存在
    if not exist "output\!name! !character!\materials\vgui" (
        mkdir "output\!name! !character!\materials\vgui"
    )

    rem 生成大厅VMT (s_panel_lobby_xxxx.vmt)
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

    rem 生成头像VMT (s_panel_xxxx.vmt)
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

    rem 生成倒地状态VMT (s_panel_xxxx_incap.vmt)
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

rem 为二代角色动态生成VMT文件路径和内容
for /l %%i in (0,1,3) do (
    set character=!l4d2_characters[%%i]!
    set vmt_name=!l4d2_vmt_names[%%i]!

    rem VMT文件路径，确保生成到正确的角色子文件夹
    set vmt_file_lobby=output\!name! !character!\materials\vgui\select_!vmt_name!.vmt
    set vmt_file_portrait=output\!name! !character!\materials\vgui\s_panel_!vmt_name!.vmt
    set vmt_file_incap=output\!name! !character!\materials\vgui\s_panel_!vmt_name!_incap.vmt

    rem 确保路径存在
    if not exist "output\!name! !character!\materials\vgui" (
        mkdir "output\!name! !character!\materials\vgui"
    )

    rem 生成大厅VMT (select_xxxx.vmt)
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

    rem 生成头像VMT (s_panel_xxxx.vmt)
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

    rem 生成倒地状态VMT (s_panel_xxxx_incap.vmt)
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

echo 动态VGUI文件已生成，帧数为: !frame_count!
pause
