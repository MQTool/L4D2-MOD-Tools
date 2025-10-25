# L4D2-MOD-Tools

面向《求生之路 2》人物 MOD 制作的工具合集，包含 Blender 插件、3ds Max 脚本、Python 程序与批处理脚本，强调高效与稳定。

## 目录
- [功能](#功能)
- [仓库结构](#仓库结构)
- [文件入口](#文件入口)
- [安装](#安装)
- [兼容性与依赖](#兼容性与依赖)
- [许可证](#许可证)
- [交流与致谢](#交流与致谢)
- [English (Brief)](#english-brief)

## 功能
- 智能拆分与命名：GLB/SMD/DMX 输出，支持可选 AI 翻译与安全拆分。
- 一键 PBR 着色：统一 PBR 材质结构，可复制纹理并输出日志（面向 Source）。
- 骨骼与权重工具：对齐、快速权重转移（Skin_Wrap→Skin）、零权重清理、批量重命名。
- 材质与导出：VMT 批量复制与路径优化、静态对象 GLB 导出、面数排行与视口简化控制。
- 表情支持：自动识别 `fe1–fe4` 表情网格并生成 QC 片段（`$bodygroup faceeffect`）。
- Python 工具：材质分件（含夜光组件与 addoninfo 生成）、音频批量转换（FFmpeg）。
- 批处理脚本：VPK 智能打包、动态 VGUI、比尔手办等常用任务。

## 仓库结构
- `目白麦昆的MOD制作工具箱/Blender插件工具箱/`：Blender 多合一插件（MQ Tools v1.6.1）
- `目白麦昆的MOD制作工具箱/Max工具箱/`：3ds Max 工具箱 v5.7（MaxScript）
- `目白麦昆的MOD制作工具箱/Python程序/`：常用 Python 脚本（材质分件、音频转换）
- `目白麦昆的MOD制作工具箱/智能打包2.0/`：VPK 打包与 VGUI 相关批处理脚本

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
Toolbox for L4D2 MODs: Blender add-on (MQ Tools v1.6.1), 3ds Max script (v5.7), Python utilities, and batch scripts. Highlights: smart split & naming (GLB/SMD/DMX), one-click PBR shading, VMT batch copy, weight transfer & bone tools, static GLB export, faceeffect recognition for QC, VPK packaging and VGUI scripts.
