# L4D2-MOD-Tools  
《求生之路2》MOD制作工具集  
AI-generated simple scripts and code for Left 4 Dead 2 character MOD development, significantly improving production efficiency. (Includes MaxScripts, Blender add-ons, Python utilities, and batch files)  

# MQ Tools v1.6.1 — Blender 模组制作工具箱  

MQ Tools 是一个面向 Blender 的多合一工具箱，专为高效的模型导入、拆分、材质处理、骨骼与权重管理以及导出流程而设计。该版本集成了 10+ 个常用模块，包括快速拆分助手 Pro（支持 GLB/SMD/DMX 输出与 AI 翻译）、安全拆分、快速选择骨骼、一键描边、骨骼形状清除、VMT 材质批量复制、骨骼与顶点组工具、一键 PBR 材质着色、网格权重显示、静态对象 GLB 导出，以及 Helldivers 2 模组制作辅助等。  

## 兼容性与位置  
- Blender 版本：`4.5.0`（更高版本通常兼容）  
- 面板位置：`视图3D > 侧边栏 > MQ Tools`  
  
## 安装  
- 方式一：在 Blender 中打开 `编辑 > 偏好设置 > 插件`，点击“安装”，选择 `MQ_Tools_v1_6_1.py`，启用插件。  
- 方式二：将仓库打包为 ZIP（保留目录结构），在插件管理中安装该 ZIP。  
  
## 快速上手（推荐流程）  
1. 打开 `MQ Tools` 面板，进入“快速拆分助手 Pro”。  
2. 配置需要排除的对象/材质、翻译模式与输出模式；执行“智能拆分”。  
3. 进入“一键 PBR 材质着色”，生成统一的 PBR 着色并可复制外部纹理。  
4. 如需静态模型导出，使用“静态对象 GLB 导出”。  
  
## 功能模块总览  
- 快速拆分助手 Pro：智能拆分与重命名，支持 GLB/SMD/DMX 输出与 AI 翻译。  
- 安全拆分：保护法向与变换关系，自动清理形态键、减少破坏性操作。  
- 快速根据名称选择骨骼：关键词筛选并选择骨骼，提升权重与骨架处理效率。  
- 一键描边：快速生成描边合集、支持选中/全部描边及文本复制（SMD）。  
- 骨骼形状清除工具：一键移除骨骼自定义形状，清理可视化干扰。  
- VMT 材质批量复制：面向 Source 引擎材质批处理，优化路径处理并输出日志。  
- 骨骼工具：合并到父级/活动骨骼、清除零权重、移除约束、应用姿态变换、快速重命名、左右对称合并、MMD 快速合并、少前2一键预处理等。  
- 顶点组工具：合并顶点组等常用操作。  
- 一键 PBR 材质着色：智能匹配贴图通道，支持外部纹理复制与日志输出。  
- 网格权重显示：隔离零权重网格，定位权重问题区。  
- MMD 材质转换：在 Blender/Cycles/MMD 材质间快速互转。  
- 静态对象 GLB 导出：更稳健的命名管理与材质导出控制，适合静态场景打包。  
- 绝地潜兵 2 模组制作分支：模型简化与缩放等专项辅助。  
- 面数排行榜：统计并展示对象面数，快速发现高面模型。  
- 精简修改器实时显示控制：批量开启/关闭 `Decimate` 修改器的视口显示。  
  
## 使用说明（精选）  
  
### 快速拆分助手 Pro  
- 在场景中选择需要处理的网格，打开“快速拆分助手 Pro”。  
- 配置“排除对象”“排除材质”（避免被拆分与重命名），可选“Uma Musume 模式”（保留 `.001` 后缀）。  
- 选择输出模式：`GLB / SMD / DMX`。  
- 翻译模式：`不翻译 / 中译英 / 英译中 / AI中译英 / AI英译中`，可设置 API 密钥与翻译风格（`二次元 / 写实`）。  
- 可选“启用自动前置预处理”“启用总合集并命名”，用于导出前的对象组织。  
- 执行“智能拆分”，插件会生成配置文本/DefineVariable 并可一键复制。  
  
### 一键 PBR 材质着色  
- 打开“一键 PBR 材质着色”面板。  
- 可指定 `Eyeblend` 贴图文件；启用“复制纹理到外部文件夹”，将材质纹理复制到指定路径（避免导出合并）；支持将执行日志输出到文件。  
- 点击“一键 PBR 材质着色 (重构版)”生成统一的 PBR 着色结构。  
  
### 静态对象 GLB 导出  
- 选择要导出的对象，打开“静态对象 GLB 导出”。  
- 配置命名与材质导出选项，执行“导出静态 GLB”。  
  
## 依赖与可选组件  
- 网络与翻译：AI 翻译功能会使用 `requests` 访问外部服务，请按需配置 API 密钥与网络环境。  
- Pillow（可选）：如在某些材质处理流程中出现 `No module named 'PIL'`，可安装 Pillow 以启用相关能力（Blender Python 环境）。  
- 生态配套：可与 Cats-Blender-Plugin（非官方 Dev）与 MMD Tools Local 搭配使用以获得更完善的工作流。  
  
## 常见问题  
- 面板未显示：确认插件已启用，并在 `视图3D > 侧边栏 > MQ Tools` 查看。  
- 修改代码后未生效：需在偏好设置中取消并重新勾选插件，或重启 Blender。  
- 输出路径设置与排错：可参考仓库内《输出路径设置说明.md》。  
  
## 版本与变更（v1.6.1）  
- 新增：面数排行榜与 Decimate 实时显示控制面板。  
- 增强：PBR 材质设置支持外部纹理复制与日志输出。  
- 优化：快速拆分助手 Pro 增加材质级别 blank 控制与 Uma Musume 模式。  
- 修复：若干拆分与形态键处理的稳定性问题。  
  
## 贡献与反馈  
- 欢迎提交 Issue 与 PR 改进工具流程与稳定性。  
- 交流与文档：`https://space.bilibili.com/454130937?spm_id_from=333.1369.0.0`  
  
## 许可证  
- 请在仓库根目录添加 `LICENSE` 文件以明确授权条款（未指定时默认不授予商业与再分发许可）。  
  
---  
  
## English (Brief)  
  
MQ Tools is an all-in-one Blender toolbox for model splitting, material handling, rig/weights management, and exports. v1.6.1 ships 10+ modules: Quick Split Assistant Pro (GLB/SMD/DMX + AI translation), Safe Split, Bone Selector, One-click Outline, Bone Shape Cleanup, VMT batch material copy, Bone & Vertex Group tools, One-click PBR shading, Mesh Weight Display, Static GLB Export, and Helldivers 2 mod helper.  
  
- Compatibility: Blender `4.5.0` (newer usually compatible)  
- Location: `3D View > Sidebar > MQ Tools`  
- Install: Add-on preferences > Install `MQ_Tools_v1_6_1.py` (or ZIP), enable.  
- Highlights: smarter splitting and naming, PBR shading with external texture copy & logging, static GLB export, face count ranking, decimate viewport toggles.  
- Optional deps: `requests` for AI translation; install Pillow in Blender Python if material routines require it.  
  
Contributions are welcome. Please add a `LICENSE` file to clarify permissions.  
  
# 目白麦昆的 MAX 工具箱 V5.7  
  
一站式 3ds Max MaxScript 工具集，涵盖骨骼对齐、权重处理、表情预设、批量重命名、导出支持等常用流程，开箱即用，专注提效与稳定性。  
  
## 目录  
- [特性总览](#特性总览)  
- [环境要求](#环境要求)  
- [安装与启动](#安装与启动)  
- [快速上手](#快速上手)  
- [功能说明](#功能说明)  
- [预设与数据存储位置](#预设与数据存储位置)  
- [常见问题](#常见问题)  
- [版本记录](#版本记录)  
- [致谢](#致谢)  
- [许可证](#许可证)  
  
## 特性总览  
- 一键导出：几何 + 骨骼 + 辅助对象，自动识别 `fe1`–`fe4` 表情网格并生成 QC `bodygroup` 片段。  
- T-Pose 预设管理器：保存/应用所选对象的旋转预设，支持批量恢复 T-Pose。  
- 表情预设管理器：帧-通道值组合预设，内置复杂通道名转换（含 `no_tooth` 等特殊标识符）。  
- 重命名预设管理器 / 创建重命名映射：维护批量重命名规则，便于模型标准化。  
- 骨骼与权重工具：骨骼对齐、权重合并、快速权重转移（Skin_Wrap→Skin，含 Stack 塌陷）。  
- 几何与材质工具：智能描边（Push 修改器控制）、按材质拆分、快速调整身高、倒地修复、手模一键调整。  
- 动作辅助：一键 VRD 动作脚本生成、足部动作脚本、骨骼/辅助对象名称输出。  
  
## 环境要求  
- 操作系统：Windows  
- Autodesk 3ds Max（64 位，建议 2019+，支持 DotNet）  
- 必需插件（置于 `3ds Max 安装目录\plugins\`）：  
  - `SMDImporter.dli`  
  - `SMDExporter.dle`  
  - `VTAExporter.dle`  
  
脚本会在启动前自动检测上述插件，缺失时弹窗提示并终止，以避免后续导出失败。  
  
## 安装与启动  
1. 下载脚本文件：`目白麦昆的MAX工具箱V5.7.ms`  
2. 打开 3ds Max：  
   - 菜单 `MAXScript → Run Script...` 选择该脚本；或  
   - 将脚本直接拖拽到视窗运行。  
3. 启动成功后会显示主窗口标题：`一键工具箱`。若未显示，请先按“环境要求”安装 SMD 插件后重试。  
  
也可在监听器中通过如下方式加载：  
  
```maxscript
filein @"C:\路径\到\目白麦昆的MAX工具箱V5.7.ms"
```
  
## 快速上手  
- 快速权重转移（Skin_Wrap→Skin，含 Stack 塌陷）  
  - 打开“快速权重转移”，选择一个用作参考的“官方模型”。  
  - 将不参与转换的对象加入“排除列表”。  
  - 点击“开始执行”，自动完成：Stack 塌陷 → 添加 `Skin_Wrap` → 转为 `Skin` → 清理无用修改器。  
- 一键导出  
  - 选中需要导出的几何/骨骼/辅助对象后执行，弹出保存对话框。  
  - 自动调用 SMD 导出器，并识别 `fe1`–`fe4` 表情网格，生成 Source QC 的 `$bodygroup faceeffect` 片段。  
- T-Pose 预设管理器  
  - 选择目标对象 → “设置目标对象” → 输入名称 → “保存预设”。  
  - 选择预设后点击“应用预设”即可恢复对应姿态。  
- 表情预设管理器  
  - 支持帧与通道值组合的预设；可设置屏蔽词（默认包含“歯”）。  
  - 内置复杂通道名转换与特殊标识符处理（如 `no_tooth`），避免匹配/索引错误。  
- 重命名预设管理器 / 创建重命名映射  
  - 维护批量重命名规则，便于不同来源模型统一命名。  
  
## 功能说明  
主窗口（`一键工具箱`）集成如下入口，点击即打开对应子工具：  
- `一键导出` → `exportGeometryWithAllBonesAndHelpers()`  
- `T-Pose预设管理器` → `TPosePresetManager()`  
- `一键VRD动作` / `一键足VRD动作` → 生成 `$NekoDriverBone` 文本与足部动作辅助。  
- `一键变形开关` → 切换 `Skin.always_deform`。  
- `一键表情` → `MorpherPresetRollout` 预设管理与应用。  
- `一键嫁接` → `SkirtHelperDialog` 快速生成/管理嫁接辅助对象。  
- `一键选中骨骼` → 辅助批量选择骨骼。  
- `一键对骨` → `BoneAlignmentToolManager()` 骨骼对齐工具。  
- `智能描边` → `rollout_push` 控制 Push 修改器参数。  
- `一键手模调整` → `adjustCustomHandModel()`。  
- `快速飘动编写` → `FastJigglebones()`，便捷设置飘动骨骼。  
- `权重合并` → `WeightMerging()`。  
- `模型按材质拆分` → `SplitByMaterial()`。  
- `骨骼/辅助对象名称输出` → `BoneNameLister()`。  
- `快速调整身高` → `quickHeightAdjustment()`。  
- `快速权重转移` → `ConvertWithSkinWrapAndConvertToSkin()`。  
  
## 预设与数据存储位置  
- T-Pose 预设：`TPosePresets.ini`（路径：`getDir #userScripts`）  
- 表情预设：`MorpherPresets.ini`（路径：`getDir #userScripts`）  
- 重命名预设：`RenamePresets.ini`（路径：`getDir #userScripts`）  
  
通常等价于：`C:\Users\<你的用户名>\Autodesk\3ds Max <版本>\scripts\`。  
  
## 常见问题  
- 启动提示插件缺失：按“环境要求”将 `SMDImporter.dli`、`SMDExporter.dle`、`VTAExporter.dle` 放入 `3ds Max 安装目录\plugins\` 后重试。  
- SMD 导出失败：确认模型已为可编辑网格/多边形；必要时先执行“快速权重转移”或手动 Stack 塌陷；检查 `Skin/Skin_Wrap` 设置。  
- 预设未生效：检查 INI 文件是否存在；确保对象名称与预设中存储的名称一致。  
- 表情网格识别：已采用精确匹配避免 `fe1` 错误命中 `fe10`。  
- 通道名转换：内置动态检测避免 `no_tooth` 等特殊标识符被错误截断或索引错配。  
  
## 版本记录  
- v5.7  
  - 新增“快速权重转移（Skin_Wrap→Skin，含 Stack 塌陷）”。  
  - 加强 SMD 插件检测与友好提示，减少运行时错误。  
  - 改进 Morpher 通道名称转换和索引映射的鲁棒性。  
- v5.4 / v5.1  
  - 功能布局与主要模块相近，逐步增强兼容性与可用性。  
  
## 致谢  
- 制作者与贡献：B 站 `メジロ_McQueen`、ChatGPT、Deepseek、Claude 3.5 / 3.7/ 4.0。  
- 感谢社区对 3ds Max 与 SMD/VTA 工具链的持续贡献。  
  
## 许可证  
- 暂未设置开源许可证。若需开源或二次分发，请与作者联系或在仓库 Issue 中说明需求。  
  
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
