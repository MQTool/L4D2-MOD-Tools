# L4D2-MOD-Tools
在制作求生之路2人物MOD过程中使用AI编写的一些简易程序与代码，能大大增加MOD制作的效率（包含MAX脚本/Blender插件/Python程序/批处理文件）  
AI-generated simple scripts and code (including MaxScripts, Blender add-ons, Python utilities, and batch files) can significantly streamline character MOD development for Left 4 Dead 2, boosting production efficiency.

## Blender插件功能：
1.适配L4Neko的局内开关可能批量处理合集，并且支持SMD/GLB/DMX格式的qc编写，有模型排除名单与材质排除名单，可使用自定义api进行机器翻译或ai翻译，将描边模型快速放置到最近的模型集合中，总合集功能可以将所有合集放入一个合集中  
2.为模型添加描边，可选单个与多个模型  
3.快速选择特定名称骨骼  
4.快速清除自定义形状骨骼  
5.快速VMT材质批量复制工具，根据blender模型材质批量映射生成vmt文件  
6.快速应用姿态模式变换/合并骨骼到父级或指定对象/圆周骨骼合并  
[以上工具现已合并为一个插件]  
7.适配Neko模板的配件骨QC创建插件，修改自Source_attachment，原始插件来源于MLUIdgb，不合并进入MQ_Tools中  

## Max脚本功能：
1.快速重命名场景中的对象，可在脚本中编写预设  
2.快速将官方骨骼对齐到自定义骨骼，可支持赛马娘模型特殊对骨  
3.快速选择非官方/自定义模型主体骨外的骨骼  
4.快速为场景中的所有蒙皮修改器中的取消变形   
5.快速将自定义模型摆成T-Pose，可在脚本中编写预设  
6.快速将自定义骨骼嫁接到官方骨骼上，可支持赛马娘模型特殊嫁接  
7.快速创造帧表情，可在脚本中编写预设  
8.快速为模型添加描边，有安全机制，不会重复添加  
9.快速为模型摆出40帧的标准VRD动作/生成QC/导出SMD，可自行修改角度/实验选项/某些部分的特殊开关  
10.快速为模型摆出30帧的标准足VRD动作，包含自动前置处理/QC编写/导出动作SMD  
11.快速调整手模的位置，大致与官方模型对齐  
12.快速编写重力与限制角度随骨骼层级递减的飘动  
13.仿造BlenderCats插件进行权重合并，有合并到父级与活动俩种模式可选  
14.快速导出当前场景中的SMD对象，支持动画与跟随脸部一起导出的眼球追踪网格  
15.快速输出当前场景中的骨骼或者对象名称  
16.快速根据材质拆分模型  
17.快速调整官方盆骨位置，解决倒地浮空问题  
18.快速调整整体身高，需要场景中有Armature这个名称的辅助对象 

## Python程序功能
1.快速拆分组件材质，支持父子级功能/自动生成addoninfo/夜光组件/指定文件夹层级功能  
可自定义MOD名称/addoninfo中的名称/MOD作者  
2.新增加快速音频转换程序，可以通过调用ffmpeg批量映射转换音频格式/频道/采样频率/采样大小

## 批处理脚本
1.支持快速打包MOD，可自定义addonDescription中的内容/MOD版本/MOD名称/MOD作者，支持比尔手办单独打包与跳过相关部分VGUI  
支持动态VGUI打包  

## Blender Add-on Features:  
Adapted for L4Neko's in-game switch batch processing collection, supporting QC scripting for SMD/GLB/DMX formats, with model exclusion lists and material exclusion lists. Includes custom API integration for machine translation or AI translation, enables rapid placement of outlined models into the nearest model collection, and features a master collection function to consolidate all sub-collections into a single unified collection.
Add outlines to models, with options for single or multiple models.  
Quick selection of bones by specific names.  
Rapidly clear custom bone shapes.
Fast VMT material batch-copy tool: Automatically generate VMT files based on Blender material mappings.
[All tools are now merged into a single plugin]

## 3ds Max Script Features:  
Rapidly rename objects in the scene with customizable presets.  
Align official bones to custom bones (supports Uma Musume models).  
Quickly select non-official/custom bones outside the main body skeleton.  
Disable deformations in all Skin Modifiers across the scene.  
Pose custom models into T-Pose with preset configurations.  
Graft custom bones onto official skeletons (supports Uma Musume-specific workflows).  
Create frame-based facial expressions (MMD-only support).  
Add outlines to models with safety checks to prevent duplicates.  
Pose models into 40-frame standard VRD poses, generate QC scripts, export SMDs (adjustable angles/experimental options/special case handling).  
Auto-process 30-frame standard foot VRD poses (includes QC scripting/action SMD export).  
Align hand models to official model positions.  
Simulate gravity and angle constraints with hierarchical bone decay for dynamic sway.  
Merge weights à la BlenderCats plugin (parent/active bone modes).  
Export SMD objects (animation/facial tracking meshes with eye movements).  
Output bone/object names from the current scene.  

## Python Tool Features:  
Split component materials with parent-child hierarchy support, auto-generate addoninfo, glowing components, and custom folder structures.  
Customizable MOD name, author, and addoninfo metadata. 

## Batch Script Features:  
Auto-pack MODs with customizable addonDescription, version, name, and author.  
Support Bill figurine-specific packaging, skip VGUI sections, and dynamic VGUI bundling.  
New audio conversion tool: Batch convert audio formats, channels, sampling frequency, and sample size via FFmpeg.
