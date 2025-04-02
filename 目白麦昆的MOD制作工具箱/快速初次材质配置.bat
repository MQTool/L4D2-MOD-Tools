@echo off
setlocal enabledelayedexpansion

rem 获取当前文件夹的完整路径
set "current_path=%cd%"

rem 检查路径中是否包含"materials"
echo !current_path! | findstr /i "materials" >nul
if errorlevel 1 (
    echo 错误：当前路径不包含"materials"文件夹
    exit /b 1
)

rem 提取"materials"之后的路径部分
for /f "tokens=*" %%a in ('echo !current_path! ^| powershell -command "$input | ForEach-Object {$_ -replace '.*\\materials\\', ''}"') do (
    set "after_materials=%%a"
)

if "!after_materials!"=="" (
    echo 错误：无法提取"materials"之后的路径
    exit /b 1
)

rem 将反斜杠替换为正斜杠并去除多余空格
set "after_materials=!after_materials:\=/!"
for /f "tokens=*" %%a in ('echo !after_materials! ^| powershell -command "$input | ForEach-Object {$_.Trim()}"') do (
    set "after_materials=%%a"
)

echo 当前路径：!current_path!
echo Materials之后的路径：!after_materials!

rem 创建shader文件夹
if not exist "shader" (
    mkdir "shader"
    echo 已创建shader文件夹
)

rem 创建vmt-base.vmt文件
(
    echo "VertexLitGeneric"
    echo {
    echo 	"$basetexture" "basetexture"
    echo 	//"$bumpmap"					"normal"	// 法线贴图。没有用到就不要启用。
    echo 																	// 特别地，引用所谓纯色法线贴图可能会导致 UV 边缘出现光照异常。
    echo.
    echo 	"$lightwarptexture" 			"diyu2025\UMA\Almond_Eye\shader\toon_light"			// 色彩校正。二次元必加。不推荐自制，一般会有格式问题导致效果异常。
    echo.
    echo     "$nocull" 						"1"			// 双面渲染。单面模型正反两处都暴露的话，一般都开。模型的边缝漏色严重可以关。
    echo 	"$nodecal" 						"1"			// 贴花阻止。关闭血迹。可以防止一些神秘闪退。
    echo 	"$phong" 						"1"			// 冯氏反射开关。半透明面和全息面可以关。
    echo 	"$halflambert" 					"1"			// 半兰伯特光照。让光照过渡更加自然，必开。
    echo.
    echo 	"$phongboost"					".04"       // 冯氏反射亮度。亮度区分取决于法线贴图的A通道，越白则越亮。
    echo 												// 若为了金属而修改了该通道，其值应需要进一步增加，参考翻 100 倍（ .04 → 4 ）
    echo 												// 启用 $phongexponenttexture 之后，其值或许需要进一步增加，参考翻 20 倍（ 4 → 80 ）。
    echo.	
    echo 	//"$phongexponenttexture"		"ko/vrc/lime/def/ppp_exp"		// 冯氏密度贴图 / 高光贴图。原理较为复杂，详见文档。一般不启用。
    echo 																	// 为启用 $phongalbedotint，引用所谓纯色高光贴图或许是可以接受的。
    echo.														
    echo 	"$phongalbedotint"				"1" 				// 按颜色贴图区分冯氏反射颜色。必须启用 $phongexponenttexture 才有效。效果需仔细观察。
    echo 	//"$phongexponent" 				"5.0" 				// 冯氏反射密度。启用后将覆盖 $phongexponenttexture。默认即5.0。一般不做修改。
    echo 	//"$phongtint" 					"[1 1 1]" 			// 全局冯氏反射通道强度。启用后将覆盖 $phongalbedotint。为比例关系，只能调色。
    echo 	"$phongfresnelranges"			"[1 .1 .1]" 		// 冯氏反射菲涅尔参数。原理较为复杂，详见文档。不要乱调。
    echo.
    echo 	//"$envmap"						"env_cubemap" 		// 镜面反射。和冯氏反射不同，与所处地图位置而非与光源有关。不做金属不要开。
    echo 	"$normalmapalphaenvmapmask"		"1" 				// 将法线贴图 A 通道作为镜面反射蒙版。镜面反射效果区分将取决于法线贴图的A通道，越白越显著。保持启用。
    echo 	"$envmapfresnel"				"1" 				// 启用镜面反射菲涅尔效果。该值将与冯氏反射菲涅尔参数做乘法。不要乱调。
    echo 	"$envmaptint"					"[ 0.4 0.4 0.4 ]" 	// 镜面反射通道强度。整体越大，镜面反射越明显。不单为比例关系，可以调色。
    echo.
    echo 	//"$selfillum" 					"1" 				// 开启自发光。亮度区分取决于颜色贴图的 A 通道，越白则越亮。不做自发光必须关掉。
    echo 	//"$selfillummask"                "diyu2024/share/selfillum/mask"         //自发光通道，可以在使用A透的情况下与夜光共存。
    echo 	//"$additive"					"1"					// 开启颜色叠加，具有半透明效果，透明程度区分取决于颜色贴图的 RGB 通道（灰度），黑色为完全透明。
    echo 														// 可与自发光一同开启，用以制作全息镜效果。
    echo 	//"$translucent"				"1" 				// 开启半透明。透明程度区分取决于颜色贴图的 A 通道，越白则越不透明。和自发光冲突。
    echo 	//"$alpha" 						"0.5" 				// 透明度缩放。该透明效果不会影响阴影效果。
    echo 														// 特别地，通过材质代理影响该参数时，手电阴影将会失效。
    echo.
    echo.
    echo 	// 文档：https://developer.valvesoftware.com/wiki/$phong/en // 冯氏反射
    echo }
) > "shader\vmt-base.vmt"
echo 已创建shader\vmt-base.vmt文件

rem 更新lightwarptexture路径使用当前材质的路径，并使用无BOM的UTF-8编码保存
powershell -command "$content = Get-Content 'shader\vmt-base.vmt' -Raw; $content = $content -replace 'diyu2025\\UMA\\Almond_Eye', '!after_materials!'; $content = $content -replace '\\', '/'; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllText('shader\vmt-base.vmt', $content, $Utf8NoBomEncoding)"
echo 已更新shader\vmt-base.vmt中的路径

rem 查找所有vtf文件并创建对应的vmt文件
set "count=0"
set "eye_count=0"
for %%f in (*.vtf) do (
    set /a "count+=1"
    set "vtf_file=%%~nf"
    
    echo 处理文件：%%f
    
    rem 如果不是eye文件，则创建普通的vmt文件
    if /i not "!vtf_file!"=="eye" (
        (
            echo patch
            echo {
            echo 	include	"materials/!after_materials!/shader/vmt-base.vmt"
            echo 	insert
            echo 	{
            echo 	}
            echo 	replace
            echo 	{
            echo 	"$basetexture" "!after_materials!/!vtf_file!"
            echo }
            echo }
        ) > "!vtf_file!.vmt"
        
        echo 已创建：!vtf_file!.vmt
    ) else (
        rem 检测到eye文件，创建特殊的vmt文件
        set /a "eye_count+=1"
        set /a "count-=1"
        echo 检测到eye文件，创建特殊的eye_r.vmt、eye_l.vmt和shader\eye_base.vmt文件...
        
        rem 创建eye_base.vmt文件在shader文件夹中
        (
            echo "EyeRefract"
            echo {
            echo 	"$iris" 			  "!after_materials!/eye"	  //基础贴图路径
            echo 	"$AmbientOcclTexture" "!after_materials!/ambient"  // RGB的环境遮挡，Alpha未使用
            echo 	"$Envmap"             "Engine/eye-reflection-cubemap-"   		  // Reflection environment map
            echo 	"$CorneaTexture"      "Engine/eye-cornea"                 		  // Special texture that has 2D cornea normal in RG and other data in BA
            echo 	"$EyeballRadius" "0.5"				// 默认 0.5
            echo 	"$AmbientOcclColor" "[0.1 0.1 0.1]"	// 默认 0.33, 0.33, 0.33
            echo 	"$Dilation" "0.5"					// 默认 0.5
            echo 	"$ParallaxStrength" "0.30"          // 默认 0.25
            echo 	"$CorneaBumpStrength" "0.5"			// 默认 1.0
            echo 	"$NoDecal" "1"
            echo 	// 这些效果仅在ps.2.0b及以后版本中可用
            echo 	"$RaytraceSphere" "0"	 // 默认 1 - 在像素着色器中启用光线追踪，使眼球朝四周看
            echo 	"$SphereTexkillCombo" "0"// 默认 1 - Enables killing pixels that don't ray-intersect the sphere
            echo 	"$lightwarptexture" 			"!after_materials!/shader/toon_light"
            echo 	"$EmissiveBlendEnabled" 		"1"
            echo 	"$EmissiveBlendStrength" 		"0.05"
            echo 	"$EmissiveBlendTexture" 		"vgui/white"
            echo 	"$EmissiveBlendBaseTexture" 	"!after_materials!/Eye"
            echo 	"$EmissiveBlendFlowTexture" 	"vgui/white"
            echo 	"$EmissiveBlendTint" 			" [ 1 1 1 ] "
            echo 	"$EmissiveBlendScrollVector" 	" [ 0 0 ] "
            echo }
        ) > "shader\eye_base.vmt"
        
        rem 使用PowerShell确保eye_base.vmt使用无BOM的UTF-8编码
        powershell -command "$content = Get-Content 'shader\eye_base.vmt' -Raw; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllText('shader\eye_base.vmt', $content, $Utf8NoBomEncoding)"
        echo 已创建shader\eye_base.vmt文件
        
        rem 创建eye_r.vmt和eye_l.vmt，使用eye_base.vmt作为include
        (
            echo patch
            echo {
            echo 	include	"materials/!after_materials!/shader/eye_base.vmt"
            echo 	insert
            echo 	{
            echo 	}
            echo 	replace
            echo 	{
            echo 	"$iris" "!after_materials!/!vtf_file!"
            echo 	}
            echo }
        ) > "!vtf_file!_r.vmt"
        
        (
            echo patch
            echo {
            echo 	include	"materials/!after_materials!/shader/eye_base.vmt"
            echo 	insert
            echo 	{
            echo 	}
            echo 	replace
            echo 	{
            echo 	"$iris" "!after_materials!/!vtf_file!"
            echo 	}
            echo }
        ) > "!vtf_file!_l.vmt"
        
        echo 已创建：!vtf_file!_r.vmt
        echo 已创建：!vtf_file!_l.vmt
    )
)

echo 处理完成！共创建了 !count! 个普通VMT文件。
if !eye_count! gtr 0 (
    echo 另外检测到 !eye_count! 个eye文件，并为其创建了左右眼特殊VMT文件和shader\eye_base.vmt。
)
pause 