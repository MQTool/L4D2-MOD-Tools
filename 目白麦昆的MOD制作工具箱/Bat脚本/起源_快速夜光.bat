@echo off
:: 获取当前文件夹路径
set "source_folder=%~dp0"

:: 创建 Selfillum 文件夹（如果不存在）
if not exist "%source_folder%Selfillum" (
    mkdir "%source_folder%Selfillum"
)

:: 遍历当前文件夹中的所有 .tga 文件
for %%f in ("%source_folder%*.tga") do (
    :: 获取文件名（不含路径和扩展名）
    set "filename=%%~nf"
    
    :: 输出当前处理的文件
    echo Processing: %%f

    :: 1. 为图像添加全白的 Alpha 通道
    magick "%%f" -alpha set -channel A -evaluate set 100%% +channel "%%~dpn_full_alpha.tga"
    if %errorlevel% neq 0 (
        echo Error setting full white alpha for %%f
        pause
        exit /b
    )

    :: 2. 将 Alpha 通道降低到 5%
    magick "%%~dpn_full_alpha.tga" -channel A -evaluate multiply 0.05 +channel "%source_folder%Selfillum\%%~nf.tga"
    if %errorlevel% neq 0 (
        echo Error reducing alpha to 5%% for %%f
        pause
        exit /b
    )

    :: 删除临时文件
    del "%%~dpn_full_alpha.tga"

    :: 输出提示信息
    echo Successfully processed: %%f to Selfillum\%%~nf.tga
)

echo All files processed!
pause
