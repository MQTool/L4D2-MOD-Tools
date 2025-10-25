# L4D2-MOD-Tools

面向《求生之路 2》人物 MOD 制作的工具合集，包含 Blender 插件、3ds Max 脚本、Python 程序与批处理脚本，强调高效与稳定。

## 目录
- [功能](#功能)
  - [Blender 插件（MQ Tools v1.6.1）](#blender-插件mq-tools-v161)
  - [3ds Max 工具箱（v5.7）](#3ds-max-工具箱v57)
  - [Python 程序与批处理](#python-程序与批处理)
- [仓库结构](#仓库结构)
- [文件入口](#文件入口)
- [安装](#安装)
- [兼容性与依赖](#兼容性与依赖)
- [许可证](#许可证)
- [交流与致谢](#交流与致谢)
- [English (Brief)](#english-brief)

## 功能

### Blender 插件（MQ Tools v1.6.1）
- 快速拆分助手 Pro：智能拆分与重命名，`GLB/SMD/DMX` 输出；排除对象/材质、`Uma Musume` 模式；可选 `AI` 翻译（中英互译，风格可选），生成配置文本。
- 安全拆分：保护法向与层级变换关系，自动清理形态键，降低破坏性操作风险。
- 骨骼/顶点组工具：合并到父级/活动骨骼、清除零权重、移除约束、应用姿态变换、快速重命名、左右镜像合并、`MMD` 快速合并、专项一键预处理。
- 选择与描边：名称关键词快速选骨；一键描边（合集/选中/全部），文本复制（`SMD`）。
- 材质相关：一键 `PBR` 着色（含 `Eyeblend` 支持），复制纹理到外部文件夹，输出执行日志；`VMT` 材质批量复制与路径优化；`MMD/Blender/Cycles` 材质互转。
- 导出与可视化：静态对象 `GLB` 导出（稳健命名与材质控制）；网格权重显示（定位问题区）；面数排行榜；`Decimate` 视口显示批量控制。
- 专项辅助：`Helldivers 2` 制作辅助（模型简化与缩放等）。

### 3ds Max 工具箱（v5.7）
- 一键导出：几何+骨骼+辅助对象，识别 `fe1–fe4` 表情网格并生成 Source `QC` 的 `$bodygroup faceeffect` 片段；集成 `SMD` 导出。
- 权重与骨骼：快速权重转移（`Skin_Wrap → Skin`，含 Stack 塌陷）、骨骼对齐、权重合并、名称输出、`Skin.always_deform` 开关。
- 预设管理：`T-Pose` 预设（保存/应用）、表情预设（帧-通道组合；复杂通道名转换与 `no_tooth` 等特殊标识符处理）、重命名预设与映射（统一命名）。
- 几何与材质：智能描边（`Push` 修改器控制）、按材质拆分、快速身高调整、倒地修复、手模一键调整、快速飘动编写（`Jigglebones`）。
- 动作辅助：一键 `VRD` 动作脚本与足部动作脚本，提升动画组装效率。

### Python 程序与批处理
- Python：`快速材质分件_ctk.py`（组件化拆分、夜光组件与 `addoninfo` 生成）、`快速音频转换.py`（`FFmpeg` 批量转换：格式/声道/采样率）。
- 批处理：`智能八人打包.bat`、`DynamicVGUI.bat` 等；用于 `VPK` 智能打包、动态 `VGUI`、比尔手办等常用任务。

## 仓库结构
- `目白麦昆的MOD制作工具箱/Blender插件工具箱/`：Blender 多合一插件（MQ Tools v1.6.1）
- `目白麦昆的MOD制作工具箱/Max工具箱/`：3ds Max 工具箱 v5.7（MaxScript）
- `目白麦昆的MOD制作工具箱/Python程序/`：常用 Python 脚本（材质分件、音频转换）
- `目白麦昆的MOD制作工具箱/智能打包2.0/`：`VPK` 打包与 `VGUI` 相关批处理脚本

## 文件入口
- Blender 插件：`目白麦昆的MOD制作工具箱/Blender插件工具箱/MQ_Tools_v1_6_1.py`
- Max 工具箱：`目白麦昆的MOD制作工具箱/Max工具箱/目白麦昆的MAX工具箱V5.7.ms`
- Python 程序：
  - `目白麦昆的MOD制作工具箱/Python程序/快速材质分件_ctk.py`
  - `目白麦昆的MOD制作工具箱/Python程序/快速音频转换.py`
- 批处理脚本（示例）：
  - `目白麦昆的MOD制作工具箱/智能打包2.0/智能八人打包.bat`
  - `目白麦昆的MOD制作工具箱/智能打包2.0/DynamicVGUI.bat`

## 安装
- Blender：`编辑 > 偏好设置 > 插件 > 安装`，选择 `MQ_Tools_v1_6_1.py`；面板位置 `视图3D > 侧边栏 > MQ Tools`。
- 3ds Max：将 `SMDImporter.dli`、`SMDExporter.dle`、`VTAExporter.dle` 放入 `3ds Max 安装目录\plugins\`，然后运行 `目白麦昆的MAX工具箱V5.7.ms`。
- Python/批处理：按需直接运行对应脚本/批处理文件（建议在独立环境中执行）。

## 兼容性与依赖
- Blender：建议 `4.5.0`，更高版本通常兼容。
- 3ds Max：Windows，建议 2019+（64 位，支持 DotNet）。
- 依赖（按需）：`requests`/`Pillow`（Blender Python）、`FFmpeg`（音频转换）、`ImageMagick`（夜光处理需环境变量）。

## 许可证
- 暂未设置开源许可证。若需开源或二次分发，请在 Issue 中说明或联系作者。

## 交流与致谢
- B 站：`https://space.bilibili.com/454130937`（メジロ_McQueen）
- 感谢社区对 Blender/3ds Max 与 Source 工具链的贡献。

## English (Brief)
Toolbox for L4D2 MODs: Blender add-on (MQ Tools v1.6.1), 3ds Max script (v5.7), Python utilities, and batch scripts. Highlights: smart split & naming (GLB/SMD/DMX + optional AI translation), safe split, bone/vertex tools, one-click PBR shading with external texture copy & logs, static GLB export, faceeffect recognition for QC, VPK packaging and VGUI scripts.
