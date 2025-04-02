# L4D2-MOD-Tools  
《求生之路2》MOD制作工具集  
AI-generated simple scripts and code for Left 4 Dead 2 character MOD development, significantly improving production efficiency. (Includes MaxScripts, Blender add-ons, Python utilities, and batch files)  

## Blender Add-on Features:  
### Blender插件功能：  
1. **L4Neko In-Game Switch Batch Processor** - Supports QC compilation for SMD/GLB/DMX formats with model/material exclusion lists. Features API integration for machine/AI translation and automatic edge model placement.  
   - 适配L4Neko的局内开关批量处理，支持SMD/GLB/DMQ格式QC编写，含模型/材质排除名单，支持API机器翻译，自动归集描边模型  

2. **Edge Model Generator** - Single/multi-model edge highlighting  
   - 模型描边工具（支持单选/多选）  

3. **Bone Quick Select** - Rapid selection of specific-named bones  
   - 快速选择特定名称骨骼  

4. **Custom Shape Bone Cleaner**  
   - 快速清除自定义形状骨骼  

5. **VMT Batch Generator** - Auto-generates VMT files based on Blender material mappings  
   - VMT材质批量生成（基于Blender材质映射）  

6. **Pose Tools** - Apply pose transforms/merge bones to parent or target objects/circular bone merging  
   - 姿态工具（应用变换/骨骼合并/圆周合并）  
   *[All above tools now integrated into MQ_Tools]*  

7. **Neko Template Accessory Bone QC Generator** (Modified from Source_attachment by MLUIdgb)  
   - Neko模板配件骨QC生成器（基于MLUIdgb的Source_attachment修改）  

## 3ds Max Script Features:  
### Max脚本功能：  
1. **Batch Renamer** with preset configurations  
   - 预设式批量重命名  

2. **Bone Alignment** - Official-to-custom bone alignment (Supports Uma Musume models)  
   - 官方骨骼对齐工具（支持赛马娘模型）  

3. **Non-Standard Bone Selector**  
   - 非标准骨骼快速选择  

4. **Skin Modifier Normalizer**  
   - 蒙皮修改器规范化  

5. **T-Pose Generator** with customizable presets  
   - 可预设的T-Pose生成  

6. **Bone Grafting** - Custom-to-official bone grafting (Uma Musume compatible)  
   - 骨骼嫁接工具（赛马娘兼容）  

7. **Facial Frame Generator** with presets  
   - 预设式表情帧生成  

8. **Safe Edge Model Adder** (Prevents duplication)  
   - 防重复描边添加  

9-10. **VRD Pose Tools** - 40-frame standard VRD / 30-frame foot VRD with auto QC generation/SMD export  
   - VRD动作工具（40帧标准/30帧足部，含QC自动生成）  

11. **Hand Model Aligner**  
   - 手模官方对齐  

12. **Physics Bone Generator** - Gravity/angle limits with hierarchical decay  
   - 层级式物理骨骼生成  

13. **Weight Painting Tools** - Parent/active object merging (BlenderCats style)  
   - 权重合并工具（BlenderCats风格）  

14. **Smart SMD Exporter** - Supports animations + eye-tracking meshes  
   - 智能SMD导出（含眼球追踪网格）  

15-18. Utility tools for bone naming/model splitting/pelvis adjustment/height scaling  
   - 实用工具集（骨骼命名/模型拆分/盆骨调整/身高缩放）  

## Python Utilities:  
### Python程序功能：  
1. **Material Splitter** - Component-based splitting with AddonInfo generation (Supports glow components/folder hierarchy)  
   - 组件材质拆分器（含addoninfo自动生成/夜光组件支持）  

2. **Audio Converter** - FFmpeg-powered batch processing (format/channels/sample rate)  
   - FFmpeg音频批量转换  

## Batch Scripts:  
### 批处理脚本：  
1. **MOD Packager** - Customizable VPK creation (AddonDescription/VGUI/Bill figurine support)  
   - MOD打包工具（支持动态VGUI/比尔手办）  

2. **VMT Auto-Config** - One-click VMT generation for VTF folders  
   - 一键式VMT配置  

3. **Source Glow Tool** - ImageMagick-based alpha channel processing  
   - 起源引擎夜光处理（需ImageMagick环境变量）  
