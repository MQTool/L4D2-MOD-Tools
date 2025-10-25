import bpy
import os
import time
import requests
import shutil
import re
import math
import random
import uuid
import logging
import datetime
from typing import Dict, Set, List, Optional
from dataclasses import dataclass
from collections import defaultdict, Counter
from bpy.props import (StringProperty, BoolProperty, FloatProperty, EnumProperty,
                       IntProperty, PointerProperty, CollectionProperty)
from bpy.types import (Panel, Operator, PropertyGroup, UIList, Menu)
from mathutils import Vector
import bmesh

bl_info = {
    "name": "MQ Tools",
    "author": "地狱酱",
    "version": (1, 6, 1),
    "blender": (4, 5, 0),
    "location": "视图3D > 侧边栏 > MQ Tools",
    "description": "目白麦昆的MOD制作工具箱 - 集成10大功能模块：快速拆分助手Pro(支持GLB/SMD/DMX输出+AI翻译)、材质拆分(保护法向和变换关系+自动清理形态键)、快速选择骨骼、一键描边工具、清除骨骼形状、VMT材质批量复制(优化路径处理+日志输出)、骨骼工具集(权重转移/合并/预处理/姿态应用)、一键PBR材质着色(智能匹配+外部复制)、网格权重显示工具、静态对象GLB导出(优化名称管理+材质导出控制)、绝地潜兵2MOD制作工具(模型简化+缩放)",
    "warning": "",
    "doc_url": "https://space.bilibili.com/454130937?spm_id_from=333.1369.0.0",
    "tracker_url": "",
    "category": "Object",
}

# PBR材质设置属性组
class PBRMaterialSettings(PropertyGroup):
    """PBR材质着色工具的设置"""
    eyeblend_texture_path: StringProperty(
        name="Eyeblend贴图文件",
        description="手动指定eyeblend贴图文件",
        subtype='FILE_PATH'
    )

    log_to_file: BoolProperty(
        name="输出日志到文件",
        description="将详细执行日志输出到文件中",
        default=False
    )
    log_file_path: StringProperty(
        name="日志文件路径",
        description="指定日志文件输出的路径和文件名",
        subtype='FILE_PATH',
        default="//pbr_material_log.txt"  # 默认在Blender文件同目录
    )
    # 添加复制外部纹理设置
    copy_textures_externally: BoolProperty(
        name="复制纹理到外部文件夹",
        description="为每个材质创建纹理文件的物理副本到指定文件夹，避免导出合并",
        default=False
    )
    external_texture_directory: StringProperty(
        name="外部纹理文件夹",
        description="选择存储复制纹理的目标文件夹",
        subtype='DIR_PATH'
    )

# --------------------------------------------------------------------------
# 工具 1: 快速拆分助手 Pro
# --------------------------------------------------------------------------

# ------------------------- 辅助函数 -------------------------
def remove_file_extension(name, uma_musume_mode=False):
    """去除文件扩展名后缀"""
    # 常见的图片和纹理文件扩展名
    extensions = ['.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff', '.exr', '.hdr', '.dds']
    name_lower = name.lower()
    for ext in extensions:
        if name_lower.endswith(ext):
            name = name[:-len(ext)]
            break
    
    # 赛马娘模式：保留.001等数字后缀
    if uma_musume_mode:
        return name
    
    # 默认模式：移除.001等数字后缀
    import re
    # 移除末尾的.数字后缀（如.001, .002等）
    name = re.sub(r'\.\d{3}$', '', name)
    return name

def check_material_duplicate(self, context):
    """检查材质是否重复选择"""
    settings = context.scene.qseparator_settings
    current_item = None
    
    # 找到当前正在更新的项
    for item in settings.excluded_materials:
        if item == self:
            current_item = item
            break
    
    if not current_item or not current_item.material:
        return
    
    # 检查是否有其他项已经选择了相同的材质
    for item in settings.excluded_materials:
        if item != current_item and item.material == current_item.material:
            # 如果发现重复，清除当前选择
            current_item.material = None
            break

# ------------------------- 属性定义 -------------------------
class ExcludedItem(bpy.types.PropertyGroup):
    def poll_target(self, obj):
        # 只允许选择网格对象，且不能是已经被选择的对象
        settings = bpy.context.scene.qseparator_settings
        excluded_objects = {item.target for item in settings.excluded_items if item.target and item != self}
        return obj.type == 'MESH' and obj not in excluded_objects
    
    target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="排除对象",
        description="选择要排除的网格对象",
        poll=poll_target
    )

class ExcludedMaterial(bpy.types.PropertyGroup):
    def poll_material(self, material):
        # 只允许选择未被选择的材质
        settings = bpy.context.scene.qseparator_settings
        excluded_materials = {item.material for item in settings.excluded_materials if item.material and item != self}
        return material not in excluded_materials
    
    material: bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="排除材质",
        description="选择要排除的材质",
        poll=poll_material
    )

class MaterialBlankControl(bpy.types.PropertyGroup):
    def poll_material(self, material):
        # 只允许选择未被选择的材质
        settings = bpy.context.scene.qseparator_settings
        selected_materials = {item.material for item in settings.material_blank_controls if item.material and item != self}
        return material not in selected_materials
    
    material: bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="材质",
        description="选择要控制blank行的材质",
        poll=poll_material
    )
    
    blank_mode: bpy.props.EnumProperty(
        name="Blank模式",
        items=[
            ('INCLUDE', "包含blank", "此材质的QC配置包含blank行"),
            ('EXCLUDE', "排除blank", "此材质的QC配置不包含blank行"),
        ],
        default='INCLUDE',
        description="控制此材质是否包含blank行"
    )

class QSeparatorSettings(bpy.types.PropertyGroup):
    excluded_items: bpy.props.CollectionProperty(type=ExcludedItem)
    active_index: bpy.props.IntProperty(default=-1)
    affect_output: bpy.props.BoolProperty(
        name="应用排除列表",
        default=True,
        description="启用时排除列表会影响所有生成内容"
    )
    blank_control_mode: bpy.props.EnumProperty(
        name="Blank行控制",
        items=[
            ('AUTO', "自动模式", "根据排除列表自动决定是否生成blank行（默认行为）"),
            ('ALWAYS', "总是生成", "每个QC配置都包含blank行，无论是否被排除"),
            ('NEVER', "从不生成", "所有QC配置都不包含blank行"),
        ],
        default='AUTO',
        description="控制QC配置中blank行的生成策略"
    )
    export_mode: bpy.props.EnumProperty(
        name="输出模式",
        items=[
            ('GLB', "GLB模式", "生成GLB配置"),
            ('SMD', "SMD模式", "生成SMD配置"),
            ('DMX', "DMX模式", "生成DMX配置"),
        ],
        default='GLB',
        description="选择生成的配置类型"
    )
    translate_mode: bpy.props.EnumProperty(
        name="翻译模式",
        items=[
            ('NONE', "不翻译", "保持原始名称"),
            ('CH2EN', "中译英", "将中文翻译为英文并重命名材质"),
            ('EN2CH', "英译中", "将英文翻译为中文"),
            ('AI_CH2EN', "AI中译英", "使用AI将中文专业翻译为英文"),
            ('AI_EN2CH', "AI英译中", "使用AI将英文专业翻译为中文"),
        ],
        default='NONE',
        description="选择翻译模式"
    )
    api_key: bpy.props.StringProperty(
        name="API密钥",
        description="输入用于翻译的API密钥"
    )
    translation_style: bpy.props.EnumProperty(
        name="翻译风格",
        items=[
            ('ANIME', "二次元风格", "适用于二次元角色模型，使用特定术语翻译"),
            ('REALISTIC', "写实风格", "适用于写实风格模型，使用通用术语翻译"),
        ],
        default='ANIME',
        description="选择翻译风格，影响特定术语的翻译方式"
    )
    enable_auto_preprocess: bpy.props.BoolProperty(
        name="启用自动前置预处理",
        default=False,
        description="启用时将自动创建合集并整理对象"
    )
    enable_total_collection: bpy.props.BoolProperty(
        name="启用总合集",
        default=False,
        description="启用时将所有内容放入指定的总合集中"
    )
    total_collection_name: bpy.props.StringProperty(
        name="总合集名称",
        default="总合集",
        description="GLB模式下创建的总合集名称"
    )
    excluded_materials: bpy.props.CollectionProperty(type=ExcludedMaterial)
    material_active_index: bpy.props.IntProperty(default=-1)
    affect_materials: bpy.props.BoolProperty(
        name="应用材质排除",
        default=True,
        description="启用时材质排除列表会影响所有生成内容"
    )
    material_blank_controls: bpy.props.CollectionProperty(type=MaterialBlankControl)
    blank_control_active_index: bpy.props.IntProperty(default=-1)
    enable_material_blank_control: bpy.props.BoolProperty(
        name="启用材质级别blank控制",
        default=False,
        description="启用时可以为每个材质单独设置是否包含blank行"
    )
    uma_musume_mode: bpy.props.BoolProperty(
        name="赛马娘模式",
        description="启用后，.001后缀的重复材质不会被分离",
        default=False
    )

# ------------------------- 核心逻辑 -------------------------
@dataclass
class CollectionInfo:
    """集合信息缓存类"""
    level: int
    parent: Optional[str]
    objects: List[str]

class CollectionCache:
    """集合缓存管理器"""
    def __init__(self):
        self.cache: Dict[str, CollectionInfo] = {}
        self.last_update = 0
    
    def update_cache(self, context) -> None:
        """更新集合缓存"""
        current_time = time.time()
        # 每秒最多更新一次缓存
        if current_time - self.last_update < 1.0:
            return
            
        self.cache.clear()
        scene_coll = context.scene.collection
        
        def process_collection(coll, parent_name: Optional[str], level: int):
            self.cache[coll.name] = CollectionInfo(
                level=level,
                parent=parent_name,
                objects=[obj.name for obj in coll.objects]
            )
            for child in coll.children:
                process_collection(child, coll.name, level + 1)
                
        process_collection(scene_coll, None, 0)
        self.last_update = current_time

# 创建全局缓存实例
collection_cache = CollectionCache()

def get_second_level_collections(context) -> List[str]:
    """获取所有第二层级的集合"""
    collection_cache.update_cache(context)
    return [name for name, info in collection_cache.cache.items() 
            if info.level == 2 and info.parent != "Collection"]

def generate_bodygroups(context):
    settings = context.scene.qseparator_settings
    excluded_objects = {item.target for item in settings.excluded_items if item.target} if settings.affect_output else set()
    excluded_materials = {item.material for item in settings.excluded_materials if item.material} if settings.affect_materials else set()
    
    # 构建材质级别blank控制字典
    material_blank_controls = {}
    if settings.enable_material_blank_control:
        for item in settings.material_blank_controls:
            if item.material:
                material_blank_controls[item.material.name] = item.blank_mode == 'INCLUDE'
    
    config_entries = []
    second_level_colls = get_second_level_collections(context)
    
    for coll_name in second_level_colls:
        coll = bpy.data.collections.get(coll_name)
        if not coll or not coll.objects:
            continue
            
        # 检查集合是否包含排除对象或材质
        contains_excluded_obj = any(obj in excluded_objects for obj in coll.objects)
        contains_excluded_mat = any(mat in excluded_materials 
                                  for obj in coll.objects 
                                  for mat in obj.data.materials if mat)

        # 根据blank控制模式决定是否包含blank行
        include_blank = True
        
        if settings.enable_material_blank_control:
            # 材质级别控制模式：检查集合名称是否在材质blank控制列表中
            if coll_name in material_blank_controls:
                include_blank = material_blank_controls[coll_name]
            else:
                # 如果没有特别设置，使用全局模式
                if settings.blank_control_mode == 'ALWAYS':
                    include_blank = True
                elif settings.blank_control_mode == 'NEVER':
                    include_blank = False
                else:  # AUTO模式
                    include_blank = not (contains_excluded_obj or contains_excluded_mat)
        else:
            # 全局控制模式
            if settings.blank_control_mode == 'ALWAYS':
                include_blank = True
            elif settings.blank_control_mode == 'NEVER':
                include_blank = False
            else:  # AUTO模式
                include_blank = not (contains_excluded_obj or contains_excluded_mat)
        
        # 生成配置条目
        config_entry = generate_config_entry(
            coll, 
            settings.export_mode, 
            settings.translate_mode, 
            include_blank=include_blank,
            material_blank_controls=material_blank_controls,
            contains_excluded_mat=contains_excluded_mat
        )
        if config_entry:
            config_entries.append(config_entry)
    
    return '\n'.join(config_entries) if config_entries else "// 没有可生成的配置内容"

def generate_define_variable(context):
    """生成DefineVariable QC代码"""
    settings = context.scene.qseparator_settings
    
    # 获取总集合名称
    total_collection_name = settings.total_collection_name.strip() or "总合集"
    
    # 生成DefineVariable语句
    define_variable = f'$DefineVariable custom_model "{total_collection_name}.glb"'
    
    return define_variable

def translate_text(text: str, mode: str) -> str:
    """统一的翻译处理函数"""
    settings = bpy.context.scene.qseparator_settings
    
    if mode == 'NONE' or not settings.api_key:
        return text

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.api_key}"
    }
    
    if mode.startswith('AI_'):
        # 获取翻译风格设置
        translation_style = settings.translation_style
        
        if mode == 'AI_CH2EN':
            if translation_style == 'ANIME':
                system_prompt = """你是专业的二次元角色模型翻译专家。你的任务是将中文3D模型组件名称翻译为标准英文术语。

【核心翻译原则】
- 必须严格遵循二次元角色建模的专业术语标准
- 输出格式：仅返回翻译结果，绝对不允许任何解释、注释或额外文字
- 单词连接：必须使用下划线连接多个英文单词
- 质量标准：每次翻译前必须检查术语对照表，确保一致性

【关键术语对照表】
飘带→Ribbon | 护甲→Armor | 描边→Outline | 装饰→Decoration | 配件→Accessory
头发→Hair | 服装→Costume | 鞋子→Shoes | 手套→Gloves | 武器→Weapon
衣服→Cloth | 特效→Effect | 基础→Base | 头部→Head | 主体→Main | 上→Up | 下→Down

【翻译策略】
你拥有完全的翻译自主权。根据二次元角色模型的语境，智能判断并选择最合适的英文术语。对于未在对照表中的词汇，你可以：
- 分析词汇的功能和用途，选择最贴切的英文表达
- 考虑二次元文化背景，使用符合该领域习惯的术语
- 在保持专业性的前提下，优先选择简洁明了的表达
- 根据上下文语境，灵活调整翻译策略

【强制执行指令】
1. 绝对禁止输出中文或任何解释 - 违反此规则将被视为严重错误
2. 必须使用下划线连接复合词 - 这是不可违背的格式要求
3. 发挥你的专业判断，确保翻译质量
4. 如果遇到不确定的术语，优先参考对照表，其次使用领域通用术语
5. 每次输出前进行自我检查：是否符合格式要求？是否遵循术语标准？"""
            else:  # REALISTIC
                system_prompt = """你是专业的写实风格模型翻译专家。你的任务是将中文3D模型组件名称翻译为标准英文术语。

【核心翻译原则】
- 必须严格遵循写实风格建模的专业术语标准
- 输出格式：仅返回翻译结果，绝对不允许任何解释、注释或额外文字
- 单词连接：必须使用下划线连接多个英文单词
- 质量标准：每次翻译前必须检查术语对照表，确保一致性

【关键术语对照表】
缎带→Ribbon | 盔甲→Armor | 描边→Outline | 装饰→Ornament | 配件→Component
头发→Hair_Mesh | 服装→Clothing | 鞋子→Footwear | 手套→Handwear | 武器→Weapon
织物→Cloth | 特效→Effect | 基础→Base | 头部→Head | 主体→Main | 上→Up | 下→Down

【翻译策略】
你拥有完全的翻译自主权。根据写实模型的语境，智能判断并选择最合适的英文术语。对于未在对照表中的词汇，你可以：
- 分析组件的实际功能，选择最准确的技术术语
- 考虑写实建模的专业标准，使用行业认可的表达
- 在技术性和可读性之间找到最佳平衡
- 根据组件类型和用途，灵活选择最合适的术语

【强制执行指令】
1. 绝对禁止输出中文或任何解释 - 违反此规则将被视为严重错误
2. 必须使用下划线连接复合词 - 这是不可违背的格式要求
3. 发挥你的专业判断，确保翻译质量
4. 如果遇到不确定的术语，优先参考对照表，其次使用领域通用术语
5. 每次输出前进行自我检查：是否符合格式要求？是否遵循术语标准？"""
        else:  # AI_EN2CH
            if translation_style == 'ANIME':
                system_prompt = """你是专业的二次元角色模型翻译专家。你的任务是将英文3D模型组件名称翻译为标准中文术语。

【核心翻译原则】
- 必须严格遵循二次元角色建模的专业术语标准
- 输出格式：仅返回翻译结果，绝对不允许任何解释、注释或额外文字
- 术语一致性：确保相同英文术语始终对应相同中文翻译
- 质量标准：每次翻译前必须检查术语对照表，确保准确性

【关键术语对照表】
Ribbon→飘带 | Armor→护甲 | Outline→模型描边 | Decoration→装饰 | Accessory→配件
Hair→头发 | Costume→服装 | Shoes→鞋子 | Gloves→手套 | Weapon→武器
Cloth→衣服 | Effect→特效 | Base→基础 | Head→头部 | Main→主体 | Up→上 | Down→下

【翻译策略】
你拥有完全的翻译自主权。根据二次元角色模型的语境，智能判断并选择最合适的中文术语。对于未在对照表中的词汇，你可以：
- 分析英文术语的含义和功能，选择最贴切的中文表达
- 考虑二次元文化特色，使用符合该领域习惯的中文术语
- 在专业性和可读性之间找到最佳平衡
- 根据组件特性，灵活选择最自然的中文表达

【强制执行指令】
1. 绝对禁止输出英文或任何解释 - 违反此规则将被视为严重错误
2. 必须使用简洁准确的中文术语 - 这是不可违背的格式要求
3. 发挥你的专业判断，确保翻译质量
4. 如果遇到不确定的术语，优先参考对照表，其次使用领域通用术语
5. 每次输出前进行自我检查：是否符合格式要求？是否遵循术语标准？"""
            else:  # REALISTIC
                system_prompt = """你是专业的写实风格模型翻译专家。你的任务是将英文3D模型组件名称翻译为标准中文术语。

【核心翻译原则】
- 必须严格遵循写实风格建模的专业术语标准
- 输出格式：仅返回翻译结果，绝对不允许任何解释、注释或额外文字
- 术语一致性：确保相同英文术语始终对应相同中文翻译
- 质量标准：每次翻译前必须检查术语对照表，确保准确性

【关键术语对照表】
Ribbon→缎带 | Armor→盔甲 | Outline→轮廓线 | Decoration→装饰物 | Accessory→附件
Hair→毛发 | Costume→服饰 | Shoes→鞋履 | Gloves→手部防护 | Weapon→武器
Cloth→织物 | Effect→特效 | Base→基础 | Head→头部 | Main→主体 | Up→上 | Down→下

【翻译策略】
你拥有完全的翻译自主权。根据写实模型的语境，智能判断并选择最合适的中文术语。对于未在对照表中的词汇，你可以：
- 分析英文术语的技术含义，选择最准确的中文对应词
- 考虑写实建模的专业要求，使用行业标准术语
- 在技术准确性和表达清晰度之间找到最佳平衡
- 根据组件功能和用途，灵活选择最合适的中文表达

【强制执行指令】
1. 绝对禁止输出英文或任何解释 - 违反此规则将被视为严重错误
2. 必须使用简洁准确的中文术语 - 这是不可违背的格式要求
3. 发挥你的专业判断，确保翻译质量
4. 如果遇到不确定的术语，优先参考对照表，其次使用领域通用术语
5. 每次输出前进行自我检查：是否符合格式要求？是否遵循术语标准？
20. Up或者Down这类词语意思主要为方向相关

例如：
- Base_Outline -> 基础轮廓线
- Head_Armor -> 头部装甲
- Weapon_Effect -> 武器特效
- Ribbon_Decoration -> 条带装饰物
- Hair_Mesh_Component -> 毛发网格组件
- Clothing_Main -> 衣物主体"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请翻译以下游戏模组组件名称：{text}"}
        ]
    else:
        direction = "中文翻译为英文" if mode == 'CH2EN' else "英文翻译为中文"
        messages = [
            {"role": "user", "content": f"请将以下{direction}，只需要返回翻译结果：\n{text}"}
        ]
    
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.1
    }
    
    try:
        print(f"正在翻译: {text}")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        translated_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
        if translated_text:
            print(f"翻译结果: {translated_text}")
            return translated_text
        else:
            print("翻译返回为空")
            return text
            
    except Exception as e:
        print(f"翻译时出错: {str(e)}")
        return text

def generate_config_entry(collection, export_mode: str, translate_mode: str, include_blank: bool = True, material_blank_controls: dict = None, contains_excluded_mat: bool = False) -> str:
    """生成单个集合的配置条目"""
    original_name = collection.name
    translated_name = None
    settings = bpy.context.scene.qseparator_settings
    
    # 检查是否为排除的材质或集合包含排除材质
    excluded_materials = {item.material.name for item in settings.excluded_materials if item.material}
    if original_name in excluded_materials or contains_excluded_mat:
        # 如果是排除的材质或集合包含排除材质，使用原始名称，不进行任何翻译
        display_name = original_name
        node_name = original_name
    else:
        # 正常的翻译逻辑
        if translate_mode in {'CH2EN', 'AI_CH2EN'}:
            translated_name = translate_text(original_name, translate_mode)
            display_name = original_name
            node_name = translated_name
        else:
            display_name = translate_text(original_name, translate_mode) if translate_mode != 'NONE' else original_name
            node_name = original_name
    
    # 材质级别blank控制逻辑
    final_include_blank = include_blank
    if material_blank_controls and original_name in material_blank_controls:
        # 如果有材质级别控制，使用材质级别设置
        final_include_blank = material_blank_controls[original_name]
    
    # 修改：统一使用4个空格的缩进
    indent = "    "
    blank_line = "    blank\n" if final_include_blank else ""
    
    if export_mode == 'DMX':
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio "{node_name}.dmx"\n'
                f'{blank_line}'
                '}\n')
    elif export_mode == 'SMD':
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio "{node_name}.smd"\n'
                f'{blank_line}'
                '}\n')
    else:
        return (f'$bodygroup "{display_name}"\n'
                '{\n'
                f'{indent}studio $custom_model$ InNode "{node_name}"\n'
                f'{blank_line}'
                '}\n')

def auto_preprocess(context):
    """自动前置预处理：整理对象和集合结构"""
    settings = context.scene.qseparator_settings
    total_collection_name = settings.total_collection_name.strip() or "总合集"
    
    try:
        # 获取或创建总合集
        total_collection = bpy.data.collections.get(total_collection_name)
        if not total_collection:
            total_collection = bpy.data.collections.new(total_collection_name)
            context.scene.collection.children.link(total_collection)
        
        # 处理场景中的网格对象
        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
                
            # 检查对象是否已在合适的集合中
            current_collections = obj.users_collection
            
            # 如果对象没有集合或只在主集合中
            if not current_collections or (len(current_collections) == 1 and current_collections[0] == context.scene.collection):
                # 创建或获取同名集合
                obj_collection = bpy.data.collections.get(obj.name)
                if not obj_collection:
                    obj_collection = bpy.data.collections.new(obj.name)
                    total_collection.children.link(obj_collection)
                
                # 从其他集合中移除对象
                for coll in current_collections:
                    coll.objects.unlink(obj)
                
                # 将对象添加到新集合
                obj_collection.objects.link(obj)
            
            # 如果对象已在自定义集合中，确保该集合在总合集下
            else:
                for coll in current_collections:
                    if coll != context.scene.collection and coll != total_collection:
                        # 如果集合不在总合集中，移动到总合集下
                        if coll.name not in total_collection.children:
                            # 先从其他父集合中解除链接
                            for parent_coll in bpy.data.collections:
                                if coll.name in parent_coll.children:
                                    parent_coll.children.unlink(coll)
                            # 链接到总合集
                            total_collection.children.link(coll)
        
        # 清理空集合
        for coll in bpy.data.collections:
            if (coll != context.scene.collection and 
                coll != total_collection and 
                not coll.objects and 
                not coll.children):
                bpy.data.collections.remove(coll)
        
        return {'FINISHED'}
        
    except Exception as e:
        return {'CANCELLED'}

# ------------------------- 操作符 -------------------------
class QSEPARATOR_OT_CopyText(bpy.types.Operator):
    bl_idname = "qseparator.copy_text"
    bl_label = "复制配置文本"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        text = generate_bodygroups(context)
        context.window_manager.clipboard = text
        count = text.count('$bodygroup')
        
        # 只复制QC配置，不修改材质名称
        self.report({'INFO'}, f"已复制{count}个配置项" if count else "没有可生成的内容")
        return {'FINISHED'}

class QSEPARATOR_OT_CopyDefineVariable(bpy.types.Operator):
    bl_idname = "qseparator.copy_define_variable"
    bl_label = "复制DefineVariable"
    
    def execute(self, context):
        define_variable_text = generate_define_variable(context)
        context.window_manager.clipboard = define_variable_text
        self.report({'INFO'}, f"已复制DefineVariable: {define_variable_text}")
        return {'FINISHED'}

class QSEPARATOR_OT_AddSearchItem(bpy.types.Operator):
    bl_idname = "qseparator.add_search_item"
    bl_label = "添加排除项"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        settings.excluded_items.add()
        settings.active_index = len(settings.excluded_items) - 1
        return {'FINISHED'}

class QSEPARATOR_OT_RemoveSearchItem(bpy.types.Operator):
    bl_idname = "qseparator.remove_search_item"
    bl_label = "移除选中项"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        if 0 <= settings.active_index < len(settings.excluded_items):
            settings.excluded_items.remove(settings.active_index)
            settings.active_index = min(settings.active_index, len(settings.excluded_items)-1)
        return {'FINISHED'}

class QSEPARATOR_OT_ClearAllItems(bpy.types.Operator):
    bl_idname = "qseparator.clear_all_items"
    bl_label = "清空所有项"
    
    def execute(self, context):
        context.scene.qseparator_settings.excluded_items.clear()
        return {'FINISHED'}

class QSEPARATOR_OT_OptimizeMaterialNames(bpy.types.Operator):
    """一键优化材质名称：去除.png/.tga等文件扩展名后缀"""
    bl_idname = "qseparator.optimize_material_names"
    bl_label = "一键优化材质名称"
    bl_description = "去除所有材质名称中的.png/.tga等文件扩展名后缀，让材质名称更简洁"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # 常见的图片和纹理文件扩展名（按优先级排序，长的在前面避免误匹配）
        extensions = ['.jpeg', '.tiff', '.png', '.jpg', '.tga', '.bmp', '.exr', '.hdr', '.dds']
        
        optimized_count = 0
        processed_materials = []
        skipped_materials = []
        
        # 遍历所有材质
        for material in bpy.data.materials:
            if not material:
                continue
                
            original_name = material.name
            new_name = original_name
            
            # 检查并去除文件扩展名
            name_lower = original_name.lower()
            for ext in extensions:
                if name_lower.endswith(ext):
                    new_name = original_name[:-len(ext)]
                    break
            
            # 如果名称发生了变化
            if new_name != original_name:
                # 检查新名称是否为空或只包含空白字符
                if not new_name.strip():
                    skipped_materials.append(f"{original_name} (新名称为空)")
                    continue
                
                # 确保新名称不会与现有材质冲突
                final_name = new_name.strip()
                counter = 1
                while final_name in bpy.data.materials and bpy.data.materials[final_name] != material:
                    final_name = f"{new_name.strip()}.{counter:03d}"
                    counter += 1
                
                material.name = final_name
                processed_materials.append(f"{original_name} → {final_name}")
                optimized_count += 1
        
        # 报告结果
        if optimized_count > 0:
            self.report({'INFO'}, f"成功优化了 {optimized_count} 个材质名称")
            # 在控制台输出详细信息
            print("=== 材质名称优化结果 ===")
            for change in processed_materials:
                print(f"  {change}")
            
            if skipped_materials:
                print("=== 跳过的材质 ===")
                for skipped in skipped_materials:
                    print(f"  {skipped}")
        else:
            self.report({'INFO'}, "没有找到需要优化的材质名称")
            
        if skipped_materials:
            self.report({'WARNING'}, f"跳过了 {len(skipped_materials)} 个材质（新名称为空）")
        
        return {'FINISHED'}

def log_message(context, message):
    # Simple logger that prints to the console.
    # A more advanced version could write to a file or a text block in Blender.
    print(f"[MQ Tools Log] {message}")

def log_message(context, message):
    settings = context.scene.mmd_separator_settings
    if settings.enable_file_logging and settings.log_file_path:
        log_path = bpy.path.abspath(settings.log_file_path)
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception as e:
            print(f"Error writing to log file: {e}")
    else:
        print(f"[MMD Separator] {message}")

def clean_shape_keys(obj):
    """清理对象上无用的形态键"""
    if obj.type != 'MESH' or not obj.data.shape_keys:
        return

    key_blocks = obj.data.shape_keys.key_blocks
    if not key_blocks:
        return

    print(f"--- MQ_Tools: 开始清理对象 '{obj.name}' 的形态键，共有 {len(key_blocks)} 个形态键")

    # 确定哪些形态键可以被移除
    to_remove = []
    for kb in key_blocks:
        if kb.relative_key == kb:  # 这是基础形态键
            print(f"--- MQ_Tools: 跳过基础形态键 '{kb.name}'")
            continue
        
        is_unused = True
        # 比较顶点坐标，使用容差值避免浮点数精度问题
        tolerance = 0.00000001
        for v0, v1 in zip(kb.relative_key.data, kb.data):
            distance_sq = (v0.co - v1.co).length_squared
            if distance_sq > tolerance:
                is_unused = False
                break
        
        if is_unused:
            print(f"--- MQ_Tools: 标记删除无用形态键 '{kb.name}'")
            to_remove.append(kb.name)  # 存储名称而不是对象引用
        else:
            print(f"--- MQ_Tools: 保留有用形态键 '{kb.name}'")

    # 移除无用的形态键
    for kb_name in to_remove:
        kb = obj.data.shape_keys.key_blocks.get(kb_name)
        if kb:
            obj.shape_key_remove(kb)
            print(f"--- MQ_Tools: 已删除形态键 '{kb_name}'")

    # 如果清理后只剩下基础形态键，也移除它
    if obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) == 1:
        last_kb = obj.data.shape_keys.key_blocks[0]
        last_kb_name = last_kb.name  # 在删除前保存名称
        obj.shape_key_remove(last_kb)
        print(f"--- MQ_Tools: 已删除最后的基础形态键 '{last_kb_name}'")
    
    remaining_count = len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0
    print(f"--- MQ_Tools: 对象 '{obj.name}' 清理完成，剩余 {remaining_count} 个形态键")

def separate_by_materials_safe(mesh_obj, context):
    if not mesh_obj or mesh_obj.type != 'MESH':
        log_message(context, f"Invalid object for separation: {mesh_obj.name}")
        return []

    log_message(context, f"Starting safe separation for: {mesh_obj.name}")

    # Ensure we are in Object Mode
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Deselect all and select the target object
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    context.view_layer.objects.active = mesh_obj

    # Store original properties
    original_name = mesh_obj.name
    original_parent = mesh_obj.parent
    original_matrix = mesh_obj.matrix_world.copy()
    log_message(context, f"Stored original transform for '{original_name}'. Parent: {original_parent.name if original_parent else 'None'}")

    # Get unique materials from the object
    all_materials = [mat for mat in mesh_obj.data.materials if mat is not None]
    
    # 检查赛马娘模式设置
    uma_musume_mode = False
    if hasattr(context.scene, 'mmd_separator_settings'):
        uma_musume_mode = context.scene.mmd_separator_settings.uma_musume_mode
    elif hasattr(context.scene, 'qseparator_settings'):
        uma_musume_mode = context.scene.qseparator_settings.uma_musume_mode
    
    if uma_musume_mode:
        # 赛马娘模式：按基础名称分组材质（去除.001等后缀）
        import re
        material_groups = {}
        for mat in all_materials:
            base_name = re.sub(r'\.\d{3}$', '', mat.name)
            if base_name not in material_groups:
                material_groups[base_name] = []
            material_groups[base_name].append(mat)
        
        # 只有当材质组数量大于1时才需要分离
        if len(material_groups) <= 1:
            log_message(context, "Uma Musume mode: Object has one or zero unique material groups, no separation needed.")
            return [mesh_obj]
        
        # 使用每组的第一个材质作为代表
        unique_materials = [group[0] for group in material_groups.values()]
        log_message(context, f"Uma Musume mode: Found {len(material_groups)} material groups: {list(material_groups.keys())}")
    else:
        # 默认模式：按材质名称分离
        unique_materials = list(set(all_materials))
        # If there's only one or no material, no need to separate
        if len(unique_materials) <= 1:
            log_message(context, "Object has one or zero unique materials, no separation needed.")
            return [mesh_obj]
    
    log_message(context, f"Found {len(unique_materials)} unique materials: {[m.name for m in unique_materials]}")

    separated_objects = []

    # Process each material one by one, creating a fresh copy each time.
    for mat in unique_materials:
        # Create a fresh copy from the original object for each material
        new_obj = mesh_obj.copy()
        new_obj.data = mesh_obj.data.copy()
        context.collection.objects.link(new_obj)
        
        log_message(context, f"Processing material '{mat.name}'")
        
        # Ensure the new object is active and selected
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = new_obj
        new_obj.select_set(True)

        if uma_musume_mode:
            # 赛马娘模式：选择同一组的所有材质面
            import re
            base_name = re.sub(r'\.\d{3}$', '', mat.name)
            group_materials = [m for m in new_obj.data.materials if re.sub(r'\.\d{3}$', '', m.name) == base_name]
            group_indices = [new_obj.data.materials.find(m.name) for m in group_materials if new_obj.data.materials.find(m.name) != -1]
            
            if not group_indices:
                log_message(context, f"  - ERROR: No materials found for group '{base_name}'. Skipping.")
                bpy.data.objects.remove(new_obj, do_unlink=True)
                continue
            
            # Go into Edit Mode to select faces for all materials in the group
            try:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='DESELECT')
                
                # Select faces for all materials in the group
                for idx in group_indices:
                    new_obj.active_material_index = idx
                    bpy.ops.object.material_slot_select()
                
                # Invert selection and delete unwanted faces
                bpy.ops.mesh.select_all(action='INVERT')
                bpy.ops.mesh.delete(type='FACE')
                log_message(context, f"  - Isolated faces for material group '{base_name}' (materials: {[m.name for m in group_materials]})")
            finally:
                bpy.ops.object.mode_set(mode='OBJECT')
            
            # Keep all materials in the group
            group_material_names = [m.name for m in group_materials]
            # Remove materials not in the group
            materials_to_keep = []
            for i, slot_mat in enumerate(new_obj.data.materials):
                if slot_mat and slot_mat.name in group_material_names:
                    materials_to_keep.append(slot_mat)
            
            new_obj.data.materials.clear()
            for mat_to_keep in materials_to_keep:
                new_obj.data.materials.append(mat_to_keep)
            
            log_message(context, f"  - Kept {len(materials_to_keep)} materials in group '{base_name}'.")
        else:
            # 默认模式：只保留一个材质
            # Find the material index on the new object by name
            mat_index = new_obj.data.materials.find(mat.name)

            if mat_index == -1:
                log_message(context, f"  - ERROR: Material '{mat.name}' could not be found on its fresh copy. Skipping.")
                bpy.data.objects.remove(new_obj, do_unlink=True)
                continue
            
            new_obj.active_material_index = mat_index

            # Go into Edit Mode to delete faces
            try:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.object.material_slot_select()
                bpy.ops.mesh.select_all(action='INVERT')
                bpy.ops.mesh.delete(type='FACE')
                log_message(context, f"  - Isolated faces for material '{mat.name}'")
            finally:
                bpy.ops.object.mode_set(mode='OBJECT')

            # Manually rebuild material slots to be safe
            active_mat = new_obj.data.materials[mat_index]
            new_obj.data.materials.clear()
            new_obj.data.materials.append(active_mat)
            log_message(context, "  - Manually cleaned and set the single material.")

        # Set final name and transform
        if uma_musume_mode:
            # 赛马娘模式：使用基础材质名称
            import re
            base_name = re.sub(r'\.\d{3}$', '', mat.name)
            new_obj.name = f"{original_name}_{base_name}"
        else:
            # 默认模式：使用完整材质名称
            new_obj.name = f"{original_name}_{mat.name}"
        
        new_obj.matrix_world = original_matrix
        if original_parent:
            new_obj.parent = original_parent
        
        separated_objects.append(new_obj)
        log_message(context, f"  - Finalized object '{new_obj.name}'")

    # Finally, remove the original object now that all parts are created
    if separated_objects: # Only remove if separation was successful
        log_message(context, f"Removing original object: {mesh_obj.name}")
        bpy.data.objects.remove(mesh_obj, do_unlink=True)

    log_message(context, f"Separation complete. Created {len(separated_objects)} new objects.")
    return separated_objects

class QSEPARATOR_OT_QuickSeparate(bpy.types.Operator):
    bl_idname = "qseparator.quick_separate"
    bl_label = "执行智能拆分"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.qseparator_settings
        total_collection = None
        
        # 如果是GLB模式且启用了总合集功能，处理总合集
        if (settings.export_mode == 'GLB' and 
            settings.enable_total_collection and 
            settings.total_collection_name.strip()):
            
            total_collection_name = settings.total_collection_name.strip()
            
            # 获取或创建总合集
            total_collection = bpy.data.collections.get(total_collection_name)
            if not total_collection:
                total_collection = bpy.data.collections.new(total_collection_name)
                context.scene.collection.children.link(total_collection)
            
            # 将所有非主集合移动到总合集下
            for coll in bpy.data.collections:
                if (coll != context.scene.collection and 
                    coll != total_collection and 
                    coll.name not in total_collection.children):
                    # 从当前父级解除链接
                    for parent_coll in bpy.data.collections:
                        if coll.name in parent_coll.children:
                            parent_coll.children.unlink(coll)
                    # 从场景集合中解除链接
                    if coll.name in context.scene.collection.children:
                        context.scene.collection.children.unlink(coll)
                    # 链接到总合集
                    total_collection.children.link(coll)
            
            # 处理骨架对象
            for obj in context.scene.objects:
                if obj.type == 'ARMATURE':
                    # 从其他集合中移除
                    for coll in obj.users_collection:
                        coll.objects.unlink(obj)
                    # 添加到总合集
                    total_collection.objects.link(obj)

        excluded_objects = {item.target for item in settings.excluded_items if item.target}

        target_objects = [
            obj for obj in context.scene.objects 
            if obj.type == 'MESH' 
            and obj not in excluded_objects
            and obj.name.lower() != "face"
        ]

        if not target_objects:
            self.report({'WARNING'}, "没有可操作的对象")
            return {'CANCELLED'}

        original_active = context.view_layer.objects.active
        original_selected = set(context.selected_objects)

        try:
            bpy.ops.object.select_all(action='DESELECT')
            
            # 使用安全分离方法处理每个对象
            all_separated_objects = []
            for obj in target_objects:
                separated = separate_by_materials_safe(obj, context)
                all_separated_objects.extend(separated)

            # 处理分离后的对象
            for obj in all_separated_objects:
                if obj.type != 'MESH' or not obj.data.materials:
                    continue

                mat_name = obj.data.materials[0].name
                # 去除文件扩展名后缀
                settings = context.scene.qseparator_settings
                clean_name = remove_file_extension(mat_name, settings.uma_musume_mode)
                obj.name = clean_name  # 使用去除扩展名的名称
                
                # 创建/获取材质集合
                collection = bpy.data.collections.get(clean_name)
                if not collection:
                    collection = bpy.data.collections.new(clean_name)
                    # 如果启用了总合集，将新集合放入总合集
                    if total_collection and settings.enable_total_collection:
                        total_collection.children.link(collection)
                    else:
                        context.scene.collection.children.link(collection)
                else:
                    # 如果集合已存在且启用了总合集，确保它在正确的位置
                    if total_collection and settings.enable_total_collection:
                        if collection.name not in total_collection.children:
                            # 从其他父级解除链接
                            for parent_coll in bpy.data.collections:
                                if collection.name in parent_coll.children:
                                    parent_coll.children.unlink(collection)
                            # 从场景集合中解除链接
                            if collection.name in context.scene.collection.children:
                                context.scene.collection.children.unlink(collection)
                            # 链接到总合集
                            total_collection.children.link(collection)
                
                # 移动对象到集合
                for coll in obj.users_collection:
                    coll.objects.unlink(obj)
                collection.objects.link(obj)

            # 清理空集合
            self.cleanup_empty_collections()

            # 清理所有分离对象的形态键
            for obj in all_separated_objects:
                if obj.type == 'MESH':
                    clean_shape_keys(obj)

        finally:
            bpy.ops.object.select_all(action='DESELECT')
            # 安全地恢复选择状态，避免ReferenceError
            for obj in original_selected:
                try:
                    if obj and hasattr(obj, 'name') and obj.name in bpy.data.objects:
                        obj.select_set(True)
                except ReferenceError:
                    pass  # 对象已被删除，跳过
            
            try:
                if original_active and hasattr(original_active, 'name') and original_active.name in bpy.data.objects:
                    context.view_layer.objects.active = original_active
            except ReferenceError:
                pass  # 对象已被删除，跳过

        return {'FINISHED'}

    def cleanup_empty_collections(self):
        """清理所有空集合"""
        empty_collections = [
            coll for coll in bpy.data.collections
            if coll.name != "Collection"
            and not coll.children
            and len(coll.objects) == 0
        ]

        for coll in reversed(empty_collections):
            try:
                for scene in bpy.data.scenes:
                    scene_collection = scene.collection
                    if coll.name in scene_collection.children:
                        scene_collection.children.unlink(coll)
                bpy.data.collections.remove(coll)
            except Exception as e:
                print(f"清理集合时出错: {str(e)}")

class QSEPARATOR_OT_MMDSeparate(bpy.types.Operator):
    bl_idname = "qseparator.mmd_separate"
    bl_label = "按材质拆分"
    bl_description = "按材质分离网格，同时保留自定义法线、UV和顶点组。分离后会自动清理无用的形态键。"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 获取选中的网格对象
        target_objects = [
            obj for obj in context.selected_objects 
            if obj.type == 'MESH'
        ]

        if not target_objects:
            self.report({'WARNING'}, "请选择至少一个网格对象")
            return {'CANCELLED'}

        # 获取赛马娘模式设置
        settings = context.scene.mmd_separator_settings
        uma_musume_mode = settings.uma_musume_mode

        original_active = context.view_layer.objects.active
        original_selected = set(context.selected_objects)
        processed_count = 0

        try:
            bpy.ops.object.select_all(action='DESELECT')
            
            # 使用安全分离方法处理每个对象
            all_separated_objects = []
            for obj in target_objects:
                if len(obj.data.materials) < 2:
                    # 如果只有一个材质，直接重命名
                    if obj.data.materials:
                        mat_name = obj.data.materials[0].name
                        clean_name = remove_file_extension(mat_name, uma_musume_mode)
                        obj.name = clean_name
                    all_separated_objects.append(obj)
                    processed_count += 1
                else:
                    # 多材质对象需要分离
                    separated = separate_by_materials_safe(obj, context)
                    all_separated_objects.extend(separated)
                    processed_count += len(separated)

            # 处理分离后的对象，确保名称正确并清理形态键
            for obj in all_separated_objects:
                if obj.type == 'MESH':
                    if obj.data.materials:
                        mat_name = obj.data.materials[0].name
                        clean_name = remove_file_extension(mat_name, uma_musume_mode)
                        obj.name = clean_name
                    
                    # 在这里调用清理函数
                    clean_shape_keys(obj)

            self.report({'INFO'}, f"已处理 {len(target_objects)} 个对象，生成 {processed_count} 个分离对象，并已清理无用形态键")

        finally:
            # 恢复选择状态
            bpy.ops.object.select_all(action='DESELECT')
            for obj in all_separated_objects:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)
            
            # 设置活动对象为第一个分离的对象
            if all_separated_objects and all_separated_objects[0].name in bpy.data.objects:
                context.view_layer.objects.active = all_separated_objects[0]

        return {'FINISHED'}

    def cleanup_empty_collections(self):
        """清理所有空集合"""
        empty_collections = [
            coll for coll in bpy.data.collections
            if coll.name != "Collection"
            and not coll.children
            and len(coll.objects) == 0
        ]

        for coll in reversed(empty_collections):
            try:
                for scene in bpy.data.scenes:
                    scene_collection = scene.collection
                    if coll.name in scene_collection.children:
                        scene_collection.children.unlink(coll)
                bpy.data.collections.remove(coll)
            except Exception as e:
                print(f"清理集合时出错: {str(e)}")

# 添加材质列表操作符 
class QSEPARATOR_OT_AddMaterialItem(bpy.types.Operator):
    bl_idname = "qseparator.add_material_item"
    bl_label = "添加材质排除"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        # 获取已选择的材质
        excluded_mats = {item.material for item in settings.excluded_materials if item.material}
        # 检查是否还有未选择的材质
        available_mats = [mat for mat in bpy.data.materials if mat not in excluded_mats]
        
        if available_mats:
            item = settings.excluded_materials.add()
            settings.material_active_index = len(settings.excluded_materials) - 1
        else:
            self.report({'WARNING'}, "没有可用的材质可以添加")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class QSEPARATOR_OT_RemoveMaterialItem(bpy.types.Operator):
    bl_idname = "qseparator.remove_material_item"
    bl_label = "移除材质"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        if 0 <= settings.material_active_index < len(settings.excluded_materials):
            settings.excluded_materials.remove(settings.material_active_index)
            settings.material_active_index = min(settings.material_active_index, len(settings.excluded_materials)-1)
        return {'FINISHED'}

class QSEPARATOR_OT_ClearAllMaterials(bpy.types.Operator):
    bl_idname = "qseparator.clear_all_materials"
    bl_label = "清空材质"
    
    def execute(self, context):
        context.scene.qseparator_settings.excluded_materials.clear()
        return {'FINISHED'}

class QSEPARATOR_OT_AddBlankControlItem(bpy.types.Operator):
    bl_idname = "qseparator.add_blank_control_item"
    bl_label = "添加材质blank控制"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        # 获取已选择的材质
        selected_mats = {item.material for item in settings.material_blank_controls if item.material}
        # 检查是否还有未选择的材质
        available_mats = [mat for mat in bpy.data.materials if mat not in selected_mats]
        
        if available_mats:
            item = settings.material_blank_controls.add()
            settings.blank_control_active_index = len(settings.material_blank_controls) - 1
        else:
            self.report({'WARNING'}, "没有可用的材质可以添加")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class QSEPARATOR_OT_RemoveBlankControlItem(bpy.types.Operator):
    bl_idname = "qseparator.remove_blank_control_item"
    bl_label = "移除材质blank控制"
    
    def execute(self, context):
        settings = context.scene.qseparator_settings
        if 0 <= settings.blank_control_active_index < len(settings.material_blank_controls):
            settings.material_blank_controls.remove(settings.blank_control_active_index)
            settings.blank_control_active_index = min(settings.blank_control_active_index, len(settings.material_blank_controls)-1)
        return {'FINISHED'}

class QSEPARATOR_OT_ClearAllBlankControls(bpy.types.Operator):
    bl_idname = "qseparator.clear_all_blank_controls"
    bl_label = "清空材质blank控制"
    
    def execute(self, context):
        context.scene.qseparator_settings.material_blank_controls.clear()
        return {'FINISHED'}

class QSEPARATOR_OT_OrganizeOutlines(bpy.types.Operator):
    bl_idname = "qseparator.organize_outlines"
    bl_label = "整理描边合集"
    bl_description = "将Outline前缀的合集放入对应的基础合集中"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        collections = bpy.data.collections
        outline_collections = {}
        base_collections = {}
        
        # 分类合集
        for coll in collections:
            if coll.name.startswith("Outline_"):
                # 获取基础名称（去掉Outline_前缀）
                base_name = coll.name[8:]  # 跳过"Outline_"
                outline_collections[base_name] = coll
            else:
                base_collections[coll.name] = coll
        
        processed_count = 0
        
        # 整理描边合集
        for base_name, outline_coll in outline_collections.items():
            # 严格匹配基础名称
            matching_base = base_collections.get(base_name)
            
            if matching_base:
                # 检查描边合集是否已经在正确的位置
                already_child = False
                for child in matching_base.children:
                    if child == outline_coll:
                        already_child = True
                        break
                
                if not already_child:
                    # 从当前父级解除链接
                    for parent_coll in collections:
                        try:
                            if outline_coll.name in parent_coll.children:
                                parent_coll.children.unlink(outline_coll)
                        except:
                            continue
                    
                    # 链接到新的父级
                    try:
                        matching_base.children.link(outline_coll)
                        processed_count += 1
                        print(f"已移动 {outline_coll.name} 到 {matching_base.name}")
                    except Exception as e:
                        print(f"移动合集 {outline_coll.name} 时出错: {str(e)}")
        
        if processed_count > 0:
            self.report({'INFO'}, f"已整理 {processed_count} 个描边合集")
        else:
            self.report({'INFO'}, "没有需要整理的描边合集")
            
        return {'FINISHED'}

class QSEPARATOR_OT_SelectItem(bpy.types.Operator):
    bl_idname = "qseparator.select_item"
    bl_label = "选择列表项"
    index: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.qseparator_settings.active_index = self.index
        return {'FINISHED'}

class QS_UL_ExcludedItems(bpy.types.UIList):
    """优化的排除列表UI"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # 显示对象图标和名称
            if item.target:
                obj = bpy.data.objects.get(item.target)
                if obj:
                    row.label(text="", icon=f'OUTLINER_OB_{obj.type}')
                    row.prop(item, "target", text="", emboss=False)
                    # 显示所属集合
                    if obj.users_collection:
                        row.label(text=f"在 {obj.users_collection[0].name} 中")
                else:
                    row.label(text="无效对象", icon='ERROR')
            else:
                row.label(text="未选择对象", icon='QUESTION')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OBJECT_DATA')

class QS_UL_BlankControlItems(bpy.types.UIList):
    """材质blank控制列表UI"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # 显示材质图标和名称
            if item.material:
                row.label(text="", icon='MATERIAL')
                row.prop(item, "material", text="", emboss=False)
                # 显示blank模式
                row.prop(item, "blank_mode", text="", emboss=False)
            else:
                row.label(text="未选择材质", icon='QUESTION')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='MATERIAL')

# --------------------------------------------------------------------------
# 工具 2: 快速选择特定名称骨骼
# --------------------------------------------------------------------------

class BONE_OT_SelectBonesByKeyword(bpy.types.Operator):
    bl_idname = "object.select_bones_by_keyword"
    bl_label = "快速根据名称选择骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        keyword = scene.bone_keyword
        case_sensitive = scene.case_sensitive

        if not keyword:
            self.report({'WARNING'}, "关键词不能为空")
            return {'CANCELLED'}

        # 确保我们在对象模式中清除选择
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in bpy.context.object.data.bones:
            bone.select = False

        # 切换到姿态模式以选择骨骼
        bpy.ops.object.mode_set(mode='POSE')

        for bone in bpy.context.object.pose.bones:
            # 根据区分大小写选项比较关键词
            if (keyword in bone.name if case_sensitive else keyword.lower() in bone.name.lower()):
                bone.bone.select = True

        # 返回到姿态模式
        bpy.ops.object.mode_set(mode='POSE')

        self.report({'INFO'}, "已成功选择骨骼")
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 工具 3: 目白麦昆的一键描边插件
# --------------------------------------------------------------------------

def add_outline(context, size, all_objects):
    """实际执行描边操作的函数"""
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    if all_objects:
        objs = [obj for obj in bpy.data.objects if obj.type == 'MESH' and not obj.name.startswith("Outline_")]  # 只选择网格对象，排除描边对象
    else:
        objs = [obj for obj in context.selected_objects if obj.type == 'MESH' and not obj.name.startswith("Outline_")]  # 只选择选中的网格对象，排除描边对象

    outline_mode = context.scene.outline_mode

    for obj in objs:
        # 跳过名称包含 "smd_bone_vis" 的对象
        if "smd_bone_vis" in obj.name.lower():
            print(f"跳过 {obj.name}，因为它与 'smd_bone_vis' 相关。")
            continue

        outline_obj_name = "Outline_" + obj.name

        # 检查是否已有对应的描边对象，避免重复创建
        if bpy.data.objects.get(outline_obj_name):
            print(f"{outline_obj_name} 已存在，跳过描边创建。")
            continue

        outline_obj = obj.copy()
        outline_obj.data = obj.data.copy()  # 复制网格数据
        outline_obj.name = outline_obj_name  # 新对象的名称为 "Outline_原对象名"

        # 根据用户选择的模式放置描边对象到相应的集合中
        if outline_mode == 'ORIGINAL':
            # 放到与原始对象相同的集合
            for collection in obj.users_collection:
                collection.objects.link(outline_obj)
        elif outline_mode == 'SINGLE':
            # 放到统一的集合中
            outline_collection = bpy.data.collections.get("Outline_Collection")
            if not outline_collection:
                outline_collection = bpy.data.collections.new(name="Outline_Collection")
                bpy.context.scene.collection.children.link(outline_collection)
            outline_collection.objects.link(outline_obj)
        elif outline_mode == 'SEPARATE':
            # 为每个描边对象创建单独的集合
            collection_name = outline_obj_name
            if collection_name not in bpy.data.collections:
                new_collection = bpy.data.collections.new(name=collection_name)
                bpy.context.scene.collection.children.link(new_collection)
            new_collection = bpy.data.collections[collection_name]
            new_collection.objects.link(outline_obj)

        obj.select_set(False)

        new_materials = []

        # **执行逻辑 1: 使用特定材质**
        if context.scene.use_named_materials:
            if "hair" in obj.name.lower():
                hair_material = bpy.data.materials.get("Outline_Hair")
                if hair_material is None:
                    hair_material = bpy.data.materials.new(name="Outline_Hair")
                    hair_material.diffuse_color = (0, 0, 0, 1)
                new_materials.append(hair_material)

            elif "face" in obj.name.lower():
                face_material = bpy.data.materials.get("Outline_Face")
                if face_material is None:
                    face_material = bpy.data.materials.new(name="Outline_Face")
                    face_material.diffuse_color = (0, 0, 0, 1)
                new_materials.append(face_material)

            else:
                # 如果既不是 "hair" 也不是 "face"，第一个材质使用 Outline_Base
                outline_base_material = bpy.data.materials.get("Outline_Base")
                if outline_base_material is None:
                    outline_base_material = bpy.data.materials.new(name="Outline_Base")
                    outline_base_material.diffuse_color = (0, 0, 0, 1)
                new_materials.append(outline_base_material)

        # **执行逻辑 2: 使用统一 Outline_Base 材质**
        elif context.scene.use_outline_base:
            outline_base_material = bpy.data.materials.get("Outline_Base")
            if outline_base_material is None:
                outline_base_material = bpy.data.materials.new(name="Outline_Base")
                outline_base_material.diffuse_color = (0, 0, 0, 1)
            new_materials.append(outline_base_material)

        # **执行逻辑 3: 只加 Outline_ 前缀 (当两者关闭时)**
        for mat in obj.data.materials[len(new_materials):]:  # 确保保留其他材质
            new_material = bpy.data.materials.new(name="Outline_" + mat.name)
            new_material.diffuse_color = (0, 0, 0, 1)
            new_materials.append(new_material)

        # 清除并重新分配材质
        outline_obj.data.materials.clear()
        for new_material in new_materials:
            outline_obj.data.materials.append(new_material)

        # 保留原模型的材质分配（即面与材质插槽的关系）
        outline_mesh = outline_obj.data
        for poly in outline_mesh.polygons:
            poly.material_index = obj.data.polygons[poly.index].material_index

        bpy.ops.object.select_all(action='DESELECT')
        outline_obj.select_set(True)
        bpy.context.view_layer.objects.active = outline_obj

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.flip_normals()

        bpy.ops.transform.shrink_fatten(value=size)

        bpy.ops.object.mode_set(mode='OBJECT')

        print(f"已为 {obj.name} 添加描边")

def delete_outline_objects_and_collections(context):
    """删除所有描边对象和相关的集合，并清理孤立数据"""
    outline_objects = [obj for obj in bpy.data.objects if obj.name.startswith("Outline_")]
    outline_collections = [col for col in bpy.data.collections if col.name.startswith("Outline_")]

    if outline_objects:
        bpy.ops.object.select_all(action='DESELECT')  # 清除所有选择
        for obj in outline_objects:
            # 检查对象是否在当前视图层中
            if obj.visible_get():
                obj.select_set(True)  # 选择描边对象
        bpy.ops.object.delete()  # 删除选中的对象

        # 删除空的 Outline_ 开头的集合
        for collection in outline_collections:
            if not collection.objects:  # 只有集合为空时才删除
                bpy.data.collections.remove(collection)

        # 清理孤立数据（孤立的材质、网格、集合等）
        bpy.ops.outliner.orphans_purge(do_recursive=True)

        print("所有描边对象及相关集合已删除，并清理孤立数据。")
    else:
        print("没有找到描边对象或集合。")

def copy_smd_to_clipboard(context):
    """生成 SMD 文本并复制到剪贴板，根据不同模式输出不同的 SMD 内容"""
    smd_export_lines = []
    outline_mode = context.scene.outline_mode
    include_all_models = context.scene.include_all_models

    if outline_mode == 'SINGLE':
        # 统一集合模式，输出单个 $body，集合名为 "Outline_Collection"
        outline_collection = bpy.data.collections.get("Outline_Collection")
        if outline_collection:
            smd_line = f"$body {outline_collection.name} \"{outline_collection.name}.smd\""
            smd_export_lines.append(smd_line)

    elif outline_mode == 'ORIGINAL':
        # 原集合模式，输出每个原模型所在集合
        for obj in bpy.data.objects:
            if obj.name.startswith("Outline_") and obj.type == 'MESH':
                for collection in obj.users_collection:
                    smd_line = f"$body {collection.name} \"{collection.name}.smd\""
                    smd_export_lines.append(smd_line)

    elif outline_mode == 'SEPARATE':
        # 单独集合模式，输出每个描边对象的名称
        for obj in bpy.data.objects:
            if obj.name.startswith("Outline_") and obj.type == 'MESH':
                smd_line = f"$body {obj.name} \"{obj.name}.smd\""
                smd_export_lines.append(smd_line)

    # 如果选择了 "输出全部" 选项，添加原始模型的 SMD 文本
    if include_all_models:
        for obj in bpy.data.objects:
            # 排除名称包含 "smd_bone_vis" 和 "face" 的对象
            if obj.type == 'MESH' and not obj.name.lower().startswith("outline_") and "face" not in obj.name.lower() and "smd_bone_vis" not in obj.name.lower():
                smd_line = f"$body {obj.name} \"{obj.name}.smd\""
                smd_export_lines.append(smd_line)

    # 将生成的 SMD 文本复制到剪贴板
    smd_text = "\n".join(smd_export_lines)
    context.window_manager.clipboard = smd_text
    return smd_text

class OUTLINE_OT_AddAll(bpy.types.Operator):
    """为所有模型对象添加描边"""
    bl_idname = "outline.add_all"
    bl_label = "快速描边"

    def execute(self, context):
        add_outline(context, -abs(context.scene.outline_size), all_objects=True)  # 将输入值转为负值
        return {'FINISHED'}

class OUTLINE_OT_AddSelected(bpy.types.Operator):
    """为选中的模型对象添加描边"""
    bl_idname = "outline.add_selected"
    bl_label = "选择描边"

    def execute(self, context):
        add_outline(context, -abs(context.scene.outline_size), all_objects=False)  # 将输入值转为负值
        bpy.context.space_data.shading.show_backface_culling = True
        return {'FINISHED'}

class OUTLINE_OT_DeleteAll(bpy.types.Operator):
    """删除所有描边对象"""
    bl_idname = "outline.delete_all"
    bl_label = "删除所有描边"

    def execute(self, context):
        delete_outline_objects_and_collections(context)
        return {'FINISHED'}

class OUTLINE_OT_CopySMD(bpy.types.Operator):
    """生成 SMD 文本并复制到剪贴板"""
    bl_idname = "outline.copy_smd"
    bl_label = "复制描边模型文本"

    def execute(self, context):
        smd_text = copy_smd_to_clipboard(context)  # 调用复制到剪贴板的函数
        self.report({'INFO'}, "SMD 文本已复制到剪贴板")
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 工具 4: 清除骨骼自定义形状
# --------------------------------------------------------------------------

class BONE_OT_ClearCustomShapes(bpy.types.Operator):
    bl_idname = "bone.clear_custom_shapes"
    bl_label = "清除自定义形状"
    bl_description = "清除所有骨骼的自定义形状"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # A获取当前选中的骨架
        armature = context.active_object
        
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选择一个骨架")
            return {'CANCELLED'}
            
        # 切换到姿态模式以访问骨骼属性
        original_mode = armature.mode
        bpy.ops.object.mode_set(mode='POSE')
        
        # 清除所有骨骼的自定义形状
        cleared_count = 0
        for bone in armature.pose.bones:
            if bone.custom_shape:
                bone.custom_shape = None
                cleared_count += 1
                
        # 恢复原始模式
        bpy.ops.object.mode_set(mode=original_mode)
        
        self.report({'INFO'}, f"已清除 {cleared_count} 个骨骼的自定义形状")
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 工具 5: VMT材质批量复制工具
# --------------------------------------------------------------------------

def clean_material_name(name):
    """清理材质名称（去除扩展名和数字后缀）"""
    # 去除所有文件扩展名（.png, .vmt等）
    name = re.sub(r'\.[^.]+$', '', name)
    # 去除数字后缀（如.001）
    name = re.sub(r'\.\d+$', '', name)
    return name.lower()  # 转换为小写以进行比较

class MaterialGroupItem(PropertyGroup):
    is_selected: BoolProperty(
        name="选择",
        default=False
    )
    name: StringProperty(name="材质名称")
    source_vmt: StringProperty(
        name="源VMT",
        description="选择源VMT文件",
        subtype='FILE_PATH'
    )

class VMT_OT_RefreshList(Operator):
    bl_idname = "vmt.refresh_list"
    bl_label = "刷新材质列表"
    
    def write_log(self, scene, log_lines):
        """写入日志到文件"""
        if not scene.vmt_enable_logging or not scene.vmt_log_path:
            return
        
        try:
            # 确保日志文件夹存在
            log_dir = bpy.path.abspath(scene.vmt_log_path)
            os.makedirs(log_dir, exist_ok=True)
            
            # 生成日志文件名（包含时间戳）
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"VMT_材质刷新日志_{timestamp}.txt"
            log_filepath = os.path.join(log_dir, log_filename)
            
            # 写入日志
            with open(log_filepath, 'w', encoding='utf-8') as f:
                f.write(f"VMT材质批量复制工具 - 刷新材质列表日志\n")
                f.write(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                
                for line in log_lines:
                    f.write(line + "\n")
            
            print(f"日志已保存到: {log_filepath}")
            
        except Exception as e:
            print(f"写入日志文件失败: {str(e)}")
    
    def execute(self, context):
        scene = context.scene
        log_lines = []  # 用于收集日志信息
        
        # 清除现有列表
        scene.material_groups.clear()
        log_lines.append("开始刷新材质列表...")
        
        if not scene.source_vmt_path:
            error_msg = "请先选择源VMT文件夹"
            log_lines.append(f"错误: {error_msg}")
            self.write_log(scene, log_lines)
            self.report({'ERROR'}, error_msg)
            return {'CANCELLED'}
        
        log_lines.append(f"源VMT文件夹: {scene.source_vmt_path}")
        
        # 获取源文件夹中的材质名称
        source_materials = set()
        vmt_files_found = []
        
        # 将Blender的相对路径转换为绝对路径
        source_path = bpy.path.abspath(scene.source_vmt_path)
        log_lines.append(f"原始路径: {scene.source_vmt_path}")
        log_lines.append(f"转换后绝对路径: {source_path}")
        
        if os.path.exists(source_path):
            log_lines.append(f"正在扫描源文件夹: {source_path}")
            for f in os.listdir(source_path):
                if f.endswith('.vmt'):
                    vmt_files_found.append(f)
                    base_name = clean_material_name(f)
                    source_materials.add(base_name)
                    log_lines.append(f"找到源材质: {f} -> 清理后: {base_name}")
                    print(f"Found source material: {f} -> cleaned: {base_name}")
        else:
            error_msg = f"源文件夹不存在: {source_path} (原始路径: {scene.source_vmt_path})"
            log_lines.append(f"错误: {error_msg}")
            self.write_log(scene, log_lines)
            self.report({'ERROR'}, error_msg)
            return {'CANCELLED'}
        
        log_lines.append(f"\n在源文件夹中找到 {len(vmt_files_found)} 个VMT文件")
        log_lines.append(f"源材质清理后名称集合: {sorted(source_materials)}\n")
        
        # 报告找到的VMT文件数量
        self.report({'INFO'}, f"在源文件夹中找到 {len(vmt_files_found)} 个VMT文件")
        
        # 添加场景中的所有不同名材质到列表
        excluded_keywords = {'点笔划', '点', '笔划', 'stroke', 'dot'}  # 添加更多需要排除的关键词
        matched_materials = []
        unmatched_materials = []
        
        log_lines.append("开始检查场景中的材质...")
        log_lines.append(f"排除关键词: {excluded_keywords}\n")
        
        for mat in bpy.data.materials:
            # 检查材质名称是否包含任何需要排除的关键词
            should_exclude = any(keyword.lower() in mat.name.lower() for keyword in excluded_keywords)
            if not mat.name.startswith('.') and not should_exclude:
                clean_name = clean_material_name(mat.name)
                log_lines.append(f"检查材质: {mat.name} (清理后: {clean_name})")
                print(f"Checking material: {mat.name} (cleaned: {clean_name})")
                
                # 详细检查匹配过程
                if clean_name in source_materials:
                    matched_materials.append(mat.name)
                    log_lines.append(f"  -> 已匹配: {mat.name} -> {clean_name}")
                    print(f"MATCHED: {mat.name} -> {clean_name}")
                else:
                    unmatched_materials.append(mat.name)
                    item = scene.material_groups.add()
                    item.name = mat.name
                    item.is_selected = False
                    log_lines.append(f"  -> 未匹配: {mat.name} -> {clean_name} (添加到待处理列表)")
                    print(f"UNMATCHED: {mat.name} -> {clean_name} (添加到待处理列表)")
            else:
                if mat.name.startswith('.'):
                    log_lines.append(f"跳过隐藏材质: {mat.name}")
                elif should_exclude:
                    log_lines.append(f"跳过排除材质: {mat.name} (包含排除关键词)")
        
        # 详细报告匹配结果
        log_lines.append(f"\n=== 匹配结果统计 ===")
        log_lines.append(f"已匹配的材质 ({len(matched_materials)}个):")
        for mat in matched_materials:
            log_lines.append(f"  - {mat}")
        
        log_lines.append(f"\n未匹配的材质 ({len(unmatched_materials)}个):")
        for mat in unmatched_materials:
            log_lines.append(f"  - {mat}")
        
        if matched_materials:
            print(f"已匹配的材质 ({len(matched_materials)}个): {matched_materials}")
        if unmatched_materials:
            print(f"未匹配的材质 ({len(unmatched_materials)}个): {unmatched_materials}")
        

        
        # 写入日志文件
        self.write_log(scene, log_lines)
        
        if len(scene.material_groups) == 0:
            self.report({'INFO'}, "没有需要处理的新材质")
        else:
            self.report({'INFO'}, f"找到 {len(scene.material_groups)} 个需要处理的材质")
        
        return {'FINISHED'}

class VMT_OT_AssignSource(Operator):
    bl_idname = "vmt.assign_source"
    bl_label = "指定源材质"
    
    filepath: StringProperty(
        name="源VMT文件",
        description="选择要应用的VMT文件",
        subtype='FILE_PATH'
    )
    
    filter_glob: StringProperty(
        default="*.vmt",
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "请选择源VMT文件")
            return {'CANCELLED'}
            
        # 将Blender的相对路径转换为绝对路径
        abs_filepath = bpy.path.abspath(self.filepath)
        abs_filepath = os.path.normpath(abs_filepath)
        
        # 为所有选中项设置源材质
        for item in context.scene.material_groups:
            if item.is_selected:
                item.source_vmt = abs_filepath
                item.is_selected = False  # 自动取消选择已指定的材质
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class VMT_OT_CopyMaterials(Operator):
    bl_idname = "vmt.copy_materials"
    bl_label = "复制材质"
    
    def execute(self, context):
        scene = context.scene
        if not scene.target_vmt_path:
            self.report({'ERROR'}, "请先选择目标路径")
            return {'CANCELLED'}
            
        # 将Blender的相对路径转换为绝对路径
        target_path = bpy.path.abspath(scene.target_vmt_path)
        
        # 确保路径格式正确并使用正确的分隔符
        target_path = os.path.normpath(target_path)
        
        # 确保目标路径存在
        try:
            os.makedirs(target_path, exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, f"创建目标路径失败: {str(e)}")
            return {'CANCELLED'}
        
        # 复制材质文件
        copied_count = 0
        for item in scene.material_groups:
            if item.source_vmt:
                # 将源文件路径转换为绝对路径
                source_path = bpy.path.abspath(item.source_vmt)
                source_path = os.path.normpath(source_path)
                
                if os.path.exists(source_path):
                    # 构建目标文件路径
                    target_file = os.path.join(target_path, f"{clean_material_name(item.name)}.vmt")
                    try:
                        shutil.copy2(source_path, target_file)
                        copied_count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"复制材质 {item.name} 时出错: {str(e)}")
                else:
                    self.report({'WARNING'}, f"源文件不存在: {item.source_vmt} -> {source_path}")
        
        self.report({'INFO'}, f"成功复制 {copied_count} 个材质文件")
        return {'FINISHED'}

class VMT_OT_SelectAll(Operator):
    bl_idname = "vmt.select_all"
    bl_label = "全选"
    
    def execute(self, context):
        for item in context.scene.material_groups:
            if not item.source_vmt:  # 只选择未指定源材质的项
                item.is_selected = True
        return {'FINISHED'}

class VMT_OT_DeselectAll(Operator):
    bl_idname = "vmt.deselect_all"
    bl_label = "取消全选"
    
    def execute(self, context):
        for item in context.scene.material_groups:
            item.is_selected = False
        return {'FINISHED'}

# --------------------------------------------------------------------------
# 主面板 - 工具选择器
# --------------------------------------------------------------------------

class MQT_PT_SeparatorPanel(Panel):
    bl_label = "快速拆分助手 Pro"
    bl_idname = "MQT_PT_SeparatorPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.qseparator_settings
        
        # 添加关于信息
        info_box = layout.box()
        info_box.label(text="MQ Tools 版本 1.3.4", icon='INFO')
        info_box.label(text="作者: 地狱酱")
        
        # 只在GLB模式下显示总合集相关设置
        if settings.export_mode == 'GLB':
            box = layout.box()
            box.label(text="总合集设置:", icon='OUTLINER_COLLECTION')
            box.prop(settings, "enable_total_collection")
            if settings.enable_total_collection:
                box.prop(settings, "total_collection_name")
        
        # 主操作区
        main_col = layout.column(align=True)
        main_col.prop(settings, "uma_musume_mode")
        main_col.operator(QSEPARATOR_OT_QuickSeparate.bl_idname, icon='MOD_EXPLODE')
        
        # 材质工具区
        material_box = layout.box()
        material_box.label(text="材质工具:", icon='MATERIAL')
        material_box.operator(QSEPARATOR_OT_OptimizeMaterialNames.bl_idname, 
                             text="一键优化材质名称", 
                             icon='FILE_REFRESH')
        
        # 配置生成区
        config_box = layout.box()
        config_box.label(text="配置生成设置:", icon='SETTINGS')
        config_box.prop(settings, "export_mode", text="输出模式")
        config_box.prop(settings, "affect_output", text="应用排除")
        config_box.prop(settings, "blank_control_mode", text="Blank行控制")
        
        # 材质级别blank控制
        config_box.prop(settings, "enable_material_blank_control", text="启用材质级别控制")
        
        if settings.enable_material_blank_control:
            blank_ctrl_box = config_box.box()
            blank_ctrl_box.label(text="材质Blank控制:", icon='MATERIAL')
            
            # 控制按钮
            ctrl_row = blank_ctrl_box.row(align=True)
            
            # 检查是否还有可选择的材质
            available_materials = [mat for mat in bpy.data.materials 
                                 if mat not in {item.material for item in settings.material_blank_controls if item.material}]
            
            add_row = ctrl_row.row()
            add_row.enabled = bool(available_materials)
            add_row.operator(QSEPARATOR_OT_AddBlankControlItem.bl_idname, text="添加", icon='ADD')
            
            ctrl_row.operator(QSEPARATOR_OT_RemoveBlankControlItem.bl_idname, text="移除", icon='REMOVE')
            ctrl_row.operator(QSEPARATOR_OT_ClearAllBlankControls.bl_idname, text="清空", icon='TRASH')
            
            # 材质blank控制列表
            if settings.material_blank_controls:
                blank_ctrl_box.template_list(
                    "QS_UL_BlankControlItems", "",
                    settings, "material_blank_controls",
                    settings, "blank_control_active_index",
                    rows=3
                )
                
                # 当前选中项的详细设置
                if 0 <= settings.blank_control_active_index < len(settings.material_blank_controls):
                    active_item = settings.material_blank_controls[settings.blank_control_active_index]
                    detail_box = blank_ctrl_box.box()
                    detail_box.prop(active_item, "material", text="材质")
                    detail_box.prop(active_item, "blank_mode", text="Blank模式")
        
        # 操作按钮
        config_box.operator(QSEPARATOR_OT_CopyText.bl_idname, 
                          text="生成QC配置", 
                          icon='TEXT')
        config_box.operator(QSEPARATOR_OT_CopyDefineVariable.bl_idname, 
                          text="复制DefineVariable", 
                          icon='COPYDOWN')
        
        # 排除列表管理
        ex_box = layout.box()
        ex_box.label(text="对象排除列表:", icon='CANCEL')
        
        # 列表控制按钮
        ctrl_row = ex_box.row(align=True)
        
        # 检查是否还有可选择的对象
        available_objects = [obj for obj in context.scene.objects 
                           if obj.type == 'MESH' and 
                           obj not in {item.target for item in settings.excluded_items if item.target}]
        
        # 使用子行来控制启用状态
        add_row = ctrl_row.row()
        add_row.enabled = bool(available_objects)
        add_row.operator(QSEPARATOR_OT_AddSearchItem.bl_idname, icon='ADD')
        
        ctrl_row.operator(QSEPARATOR_OT_RemoveSearchItem.bl_idname, icon='REMOVE')
        ctrl_row.operator(QSEPARATOR_OT_ClearAllItems.bl_idname, icon='TRASH')
        
        # 动态列表项
        list_col = ex_box.column(align=True)
        for idx, item in enumerate(settings.excluded_items):
            row = list_col.row(align=True)
            # 只显示未被选择的网格对象
            row.prop_search(
                item, "target",
                context.scene, "objects",
                text="",
                icon='OBJECT_DATA'
            )
            row.operator("qseparator.select_item", 
                        text="", 
                        icon='RADIOBUT_ON' if idx == settings.active_index else 'RADIOBUT_OFF', 
                        emboss=False).index = idx

        # 翻译设置
        translate_box = layout.box()
        translate_box.label(text="翻译设置:", icon='WORLD_DATA')
        translate_box.prop(settings, "translate_mode")
        
        # 仅在选择了AI翻译模式时显示翻译风格选择
        if settings.translate_mode.startswith('AI_'):
            translate_box.prop(settings, "translation_style")
        
        # 仅在选择了需要API的翻译模式时显示API密钥输入框
        if settings.translate_mode != 'NONE':
            translate_box.prop(settings, "api_key")

        # 材质排除列表
        mat_box = layout.box()
        mat_box.label(text="材质排除列表:", icon='MATERIAL')
        mat_box.prop(settings, "affect_materials", text="应用材质排除")
        
        # 检查是否还有可选择的材质
        available_materials = [mat for mat in bpy.data.materials 
                             if mat not in {item.material for item in settings.excluded_materials if item.material}]
        
        # 材质列表控制按钮
        mat_row = mat_box.row(align=True)
        add_mat_row = mat_row.row()
        add_mat_row.enabled = bool(available_materials)
        add_mat_row.operator(QSEPARATOR_OT_AddMaterialItem.bl_idname, icon='ADD')
        
        mat_row.operator(QSEPARATOR_OT_RemoveMaterialItem.bl_idname, icon='REMOVE')
        mat_row.operator(QSEPARATOR_OT_ClearAllMaterials.bl_idname, icon='TRASH')
        
        # 材质列表
        mat_list_col = mat_box.column(align=True)
        for item in settings.excluded_materials:
            row = mat_list_col.row(align=True)
            row.prop_search(item, "material", bpy.data, "materials", text="")

        # 确保描边整理按钮显示
        layout.separator()
        outline_box = layout.box()
        outline_box.label(text="描边整理:", icon='OUTLINER_OB_LIGHT')
        outline_box.operator(QSEPARATOR_OT_OrganizeOutlines.bl_idname, icon='OUTLINER_COLLECTION')

# --------------------------------------------------------------------------
# 安全拆分面板
# --------------------------------------------------------------------------
class MMDSeparatorSettings(bpy.types.PropertyGroup):
    enable_file_logging: BoolProperty(
        name="启用文件日志",
        description="将日志信息输出到指定的文本文件中",
        default=False
    )
    log_file_path: StringProperty(
        name="日志文件路径",
        description="选择用于保存日志的文本文件",
        subtype='FILE_PATH',
        default="//mmd_separator_log.txt"
    )
    uma_musume_mode: BoolProperty(
        name="赛马娘模式",
        description="启用后，.001后缀的重复材质不会被分离",
        default=False
    )

class MQT_PT_SafeSeparatePanel(Panel):
    bl_label = "安全拆分"
    bl_idname = "MQT_PT_SafeSeparatePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.mmd_separator_settings
        
        # MMD安全拆分区
        mmd_box = layout.box()
        mmd_box.label(text="MMD材质拆分:", icon='MESH_DATA')
        mmd_box.prop(settings, "uma_musume_mode")
        mmd_box.operator(QSEPARATOR_OT_MMDSeparate.bl_idname, text="按材质安全拆分", icon='MESH_MONKEY')

        # 日志设置
        log_box = layout.box()
        log_box.prop(settings, "enable_file_logging")
        if settings.enable_file_logging:
            log_box.prop(settings, "log_file_path")

        
        # 说明信息
        info_box = layout.box()
        info_box.label(text="功能说明:", icon='INFO')
        info_box.label(text="• 按材质分离网格对象")
        info_box.label(text="• 保留自定义法线、UV和顶点组")
        info_box.label(text="• 根据材质名称重命名网格")
        info_box.label(text="• 自动清理无用的形态键")
        info_box.label(text="• 避免破坏模型几何结构")
        if settings.uma_musume_mode:
            info_box.label(text="• 赛马娘模式：保留.001等数字后缀", icon='CHECKMARK')

# --------------------------------------------------------------------------
# 骨骼选择器面板
# --------------------------------------------------------------------------
class MQT_PT_BoneSelectorPanel(Panel):
    bl_label = "快速根据名称选择骨骼"
    bl_idname = "MQT_PT_BoneSelectorPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 输入关键字和选项
        layout.prop(scene, "bone_keyword")
        layout.prop(scene, "case_sensitive")
        
        # 选择骨骼按钮
        layout.operator("object.select_bones_by_keyword", text="选择骨骼")

# 描边工具面板
class MQT_PT_OutlinePanel(Panel):
    bl_label = "一键描边"
    bl_idname = "MQT_PT_OutlinePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 描边大小输入框
        layout.prop(scene, "outline_size", text="描边大小 (米)")

        # 描边模式选择
        layout.prop(scene, "outline_mode", text="描边放置模式")

        # 材质开关
        layout.prop(scene, "use_outline_base", text="使用统一 Outline_Base 材质")
        
        # 分类材质开关，禁用状态取决于 use_outline_base 的值
        row = layout.row()
        row.enabled = scene.use_outline_base
        row.prop(scene, "use_named_materials", text="根据名称使用特定材质")

        # 输出全部选项
        layout.prop(scene, "include_all_models", text="输出全部")

        # 快速描边按钮（为所有对象添加描边）
        row = layout.row()
        row.operator("outline.add_all", text="快速描边")

        # 选择描边按钮（只为选中的对象添加描边）
        row = layout.row()
        row.operator("outline.add_selected", text="选择描边")

        # 删除描边按钮
        row = layout.row()
        row.operator("outline.delete_all", text="删除所有描边")

        # 复制描边模型文本按钮
        row = layout.row()
        row.operator("outline.copy_smd", text="复制描边模型文本")

# --------------------------------------------------------------------------
# 工具 4: 清除骨骼自定义形状面板
# --------------------------------------------------------------------------
class MQT_PT_BoneShapePanel(Panel):
    bl_label = "骨骼形状清除工具"
    bl_idname = "MQT_PT_BoneShapePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        
        # 添加操作按钮
        box = layout.box()
        box.operator("bone.clear_custom_shapes", icon='BONE_DATA')
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明:", icon='INFO')
        box.label(text="1. 选择目标骨架")
        box.label(text="2. 点击清除按钮即可")

# --------------------------------------------------------------------------
# VMT材质批量复制工具面板
# --------------------------------------------------------------------------
class MQT_PT_VMTPanel(Panel):
    bl_label = "VMT材质批量复制工具"
    bl_idname = "MQT_PT_VMTPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # 路径设置
        box = layout.box()
        box.label(text="路径设置:")
        box.prop(scene, "source_vmt_path", text="源VMT文件夹")
        box.prop(scene, "target_vmt_path", text="目标VMT路径")
        
        # 日志设置
        log_box = layout.box()
        log_box.label(text="日志设置:")
        log_box.prop(scene, "vmt_enable_logging", text="启用日志输出")
        if scene.vmt_enable_logging:
            log_box.prop(scene, "vmt_log_path", text="日志输出文件夹")
        
        # 刷新按钮
        layout.operator("vmt.refresh_list", text="刷新材质列表", icon='FILE_REFRESH')
        
        # 材质列表
        if len(scene.material_groups) > 0:
            # 未指定源材质的材质列表
            box = layout.box()
            box.label(text="待处理材质:")
            
            # 全选按钮（只针对未指定源材质的材质）
            row = box.row()
            row.operator("vmt.select_all", text="全选")
            row.operator("vmt.deselect_all", text="取消全选")
            
            # 显示未指定源材质的材质
            for item in scene.material_groups:
                if not item.source_vmt:  # 只显示未指定源材质的材质
                    row = box.row()
                    row.prop(item, "is_selected", text="")
                    row.label(text=item.name)
            
            # 已指定源材质的材质列表
            box = layout.box()
            box.label(text="已指定材质:")
            for item in scene.material_groups:
                if item.source_vmt:  # 显示已指定源材质的材质
                    row = box.row()
                    row.label(text=item.name)
                    row.label(text=os.path.basename(item.source_vmt))
            
            # 源材质指定和复制按钮
            row = layout.row()
            row.operator("vmt.assign_source", text="指定源材质")
            row.operator("vmt.copy_materials", text="复制材质")
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明:", icon='INFO')
        box.label(text="1. 设置源VMT文件夹和目标路径")
        box.label(text="2. 点击'刷新材质列表'")
        box.label(text="3. 选择要分组的材质")
        box.label(text="4. 点击'指定源材质'选择VMT文件")
        box.label(text="5. 重复3-4步骤处理其他组")
        box.label(text="6. 点击'复制材质'完成操作")

# --------------------------------------------------------------------------
# 工具 4: 骨骼工具
# --------------------------------------------------------------------------

# ------------------------- 骨骼捕捉设置与工具 -------------------------
class BoneCaptureSettings(PropertyGroup):
    capture_enabled: BoolProperty(
        name="开始捕捉",
        description="开启后记录骨骼相关操作到txt",
        default=False
    )
    capture_dir: StringProperty(
        name="保存路径",
        description="txt输出目录",
        subtype='DIR_PATH',
        default=""
    )
    capture_filename: StringProperty(
        name="文件名",
        description="自定义txt文件名",
        default="bone_ops.txt"
    )
    include_timestamp: BoolProperty(
        name="写入时间戳",
        description="在每条记录前添加时间戳",
        default=True
    )

_bone_capture_snapshot: Dict[str, Set[str]] = {}
_bone_capture_handler_registered: bool = False


def _get_capture_full_path(context) -> str:
    s = getattr(context.scene, "bone_capture_settings", None)
    if not s:
        return ""
    directory = s.capture_dir if s.capture_dir else bpy.path.abspath("//")
    filename = s.capture_filename if s.capture_filename else "bone_ops.txt"
    full = bpy.path.abspath(os.path.join(directory, filename))
    return full


def _write_capture_line(context, line: str):
    s = getattr(context.scene, "bone_capture_settings", None)
    if not s or not s.capture_enabled:
        return
    path = _get_capture_full_path(context)
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ts_prefix = ""
    if s.include_timestamp:
        ts_prefix = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] "
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(ts_prefix + line + "\n")
    except Exception as e:
        print(f"BoneCapture write error: {e}")


def log_bone_operation(context, op: str, details: str):
    s = getattr(context.scene, "bone_capture_settings", None)
    if not s or not s.capture_enabled:
        return
    _write_capture_line(context, f"{op}: {details}")


def _snapshot_armatures() -> Dict[str, Set[str]]:
    snap: Dict[str, Set[str]] = {}
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            try:
                bones = set(b.name for b in obj.data.bones)
            except Exception:
                bones = set()
            snap[obj.name] = bones
    return snap


def _diff_and_log(context, before: Dict[str, Set[str]], after: Dict[str, Set[str]]):
    for arm_name in after.keys() | before.keys():
        bset = before.get(arm_name, set())
        aset = after.get(arm_name, set())
        removed = bset - aset
        added = aset - bset
        for bn in sorted(removed):
            log_bone_operation(context, "BoneRemoved", f"{arm_name}.{bn}")
        for bn in sorted(added):
            log_bone_operation(context, "BoneAdded", f"{arm_name}.{bn}")


def bone_capture_handler(scene):
    s = getattr(scene, "bone_capture_settings", None)
    if not s or not s.capture_enabled:
        return
    global _bone_capture_snapshot
    try:
        after = _snapshot_armatures()
        _diff_and_log(bpy.context, _bone_capture_snapshot, after)
        _bone_capture_snapshot = after
    except Exception as e:
        print(f"BoneCapture handler error: {e}")


class BONECAPTURE_OT_Start(Operator):
    bl_idname = "bonecapture.start"
    bl_label = "开始捕捉骨骼操作"
    bl_options = {'REGISTER'}

    def execute(self, context):
        s = getattr(context.scene, "bone_capture_settings", None)
        if not s:
            self.report({'ERROR'}, "捕捉设置未注册")
            return {'CANCELLED'}
        s.capture_enabled = True
        global _bone_capture_snapshot, _bone_capture_handler_registered
        _bone_capture_snapshot = _snapshot_armatures()
        if not _bone_capture_handler_registered:
            bpy.app.handlers.depsgraph_update_post.append(bone_capture_handler)
            _bone_capture_handler_registered = True
        _write_capture_line(context, "--- Bone capture started ---")
        self.report({'INFO'}, "骨骼捕捉已开启")
        return {'FINISHED'}


class BONECAPTURE_OT_Stop(Operator):
    bl_idname = "bonecapture.stop"
    bl_label = "停止捕捉骨骼操作"
    bl_options = {'REGISTER'}

    def execute(self, context):
        s = getattr(context.scene, "bone_capture_settings", None)
        if not s:
            self.report({'ERROR'}, "捕捉设置未注册")
            return {'CANCELLED'}
        s.capture_enabled = False
        global _bone_capture_handler_registered
        if _bone_capture_handler_registered:
            try:
                bpy.app.handlers.depsgraph_update_post.remove(bone_capture_handler)
            except ValueError:
                pass
            _bone_capture_handler_registered = False
        _write_capture_line(context, "--- Bone capture stopped ---")
        self.report({'INFO'}, "骨骼捕捉已停止")
        return {'FINISHED'}


class MQT_PT_BoneCapturePanel(Panel):
    bl_label = "骨骼捕捉"
    bl_idname = "MQT_PT_BoneCapturePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.bone_capture_settings
        col = layout.column(align=True)
        col.prop(s, "capture_dir")
        col.prop(s, "capture_filename")
        col.prop(s, "include_timestamp")
        row = layout.row(align=True)
        row.operator("bonecapture.start", text="开始捕捉", icon='REC')
        row.operator("bonecapture.stop", text="停止", icon='CANCEL')


def transfer_weights(self, from_bone_name, to_bone_name, mesh):
    """
    改进的权重转移函数
    """
    # 确保目标权重组存在
    if to_bone_name not in mesh.vertex_groups:
        mesh.vertex_groups.new(name=to_bone_name)
    
    # 获取源和目标权重组
    from_group = mesh.vertex_groups.get(from_bone_name)
    to_group = mesh.vertex_groups.get(to_bone_name)
    
    if not from_group:
        return
    
    # 存储每个顶点的权重
    weights = {}
    for vertex in mesh.data.vertices:
        try:
            weight = from_group.weight(vertex.index)
            if weight > 0:
                weights[vertex.index] = weight
        except RuntimeError:
            continue
    
    # 转移权重
    if weights:
        # 添加新权重
        for vertex_index, weight in weights.items():
            try:
                current_weight = 0
                try:
                    current_weight = to_group.weight(vertex_index)
                except RuntimeError:
                    pass
                # 使用 'REPLACE' 模式确保权重正确设置
                to_group.add([vertex_index], current_weight + weight, 'REPLACE')
            except RuntimeError:
                continue
    
    # 删除原始权重组
    mesh.vertex_groups.remove(from_group)

class BONE_OT_merge_to_parent(Operator):
    bl_idname = "bone.merge_to_parent"
    bl_label = "合并到父级"
    bl_description = "将选中的骨骼合并到它们的父级骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    @staticmethod
    def transfer_weights(from_bone_name, to_bone_name, mesh):
        """
        改进的权重转移函数
        """
        # 确保目标权重组存在
        if to_bone_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=to_bone_name)
        
        # 获取源和目标权重组
        from_group = mesh.vertex_groups.get(from_bone_name)
        to_group = mesh.vertex_groups.get(to_bone_name)
        
        if not from_group:
            return
        
        # 存储每个顶点的权重
        weights = {}
        for vertex in mesh.data.vertices:
            try:
                weight = from_group.weight(vertex.index)
                if weight > 0:
                    weights[vertex.index] = weight
            except RuntimeError:
                continue
        
        # 转移权重
        if weights:
            # 添加新权重
            for vertex_index, weight in weights.items():
                try:
                    current_weight = 0
                    try:
                        current_weight = to_group.weight(vertex_index)
                    except RuntimeError:
                        pass
                    # 使用 'REPLACE' 模式确保权重正确设置
                    to_group.add([vertex_index], current_weight + weight, 'REPLACE')
                except RuntimeError:
                    continue
        
        # 删除原始权重组
        mesh.vertex_groups.remove(from_group)
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE' and
                context.selected_pose_bones)
    
    def get_final_parent(self, bone, bones_to_process):
        """
        获取骨骼的最终父级（考虑多层级合并）
        """
        current = bone.parent
        while current:
            # 检查当前父级是否也在处理列表中
            is_parent_processed = any(b[0] == current for b in bones_to_process)
            if is_parent_processed:
                current = current.parent
            else:
                break
        return current
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        
        # 存储要处理的骨骼，并按层级深度排序
        bones_to_process = []
        for pose_bone in context.selected_pose_bones:
            if pose_bone.parent:
                # 计算骨骼的层级深度
                depth = 0
                temp_bone = pose_bone
                while temp_bone.parent:
                    depth += 1
                    temp_bone = temp_bone.parent
                bones_to_process.append((pose_bone, pose_bone.parent, depth))
        
        # 按深度从大到小排序（先处理子骨骼）
        bones_to_process.sort(key=lambda x: x[2], reverse=True)
        
        # 切换到对象模式以修改骨骼
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 处理每个选中的骨骼
        for bone, _, _ in bones_to_process:
            # 获取最终的父级骨骼
            final_parent = self.get_final_parent(bone, bones_to_process)
            if not final_parent:
                continue
            
            # 直接转移权重到最终父级
            for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
                self.transfer_weights(bone.name, final_parent.name, mesh)
        
        # 切换到编辑模式删除骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 删除骨骼
        for bone, _, _ in bones_to_process:
            if bone.name in armature.edit_bones:
                edit_bone = armature.edit_bones[bone.name]
                # 如果骨骼有子级，先将子级的父级设置为最终父级
                if edit_bone.children:
                    final_parent = self.get_final_parent(bone, bones_to_process)
                    if final_parent and final_parent.name in armature.edit_bones:
                        for child in edit_bone.children:
                            child.parent = armature.edit_bones[final_parent.name]
                armature.edit_bones.remove(edit_bone)
                log_target = self.get_final_parent(bone, bones_to_process)
                log_bone_operation(context, "MergeToParent", f"{bone.name} -> {(log_target.name if log_target else 'None')} on {obj.name}")
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        return {'FINISHED'}

class BONE_OT_merge_to_active(Operator):
    bl_idname = "bone.merge_to_active"
    bl_label = "合并到活动骨骼"
    bl_description = "将选中的骨骼合并到活动骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    @staticmethod
    def transfer_weights(from_bone_name, to_bone_name, mesh):
        """
        改进的权重转移函数
        """
        # 确保目标权重组存在
        if to_bone_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=to_bone_name)
        
        # 获取源和目标权重组
        from_group = mesh.vertex_groups.get(from_bone_name)
        to_group = mesh.vertex_groups.get(to_bone_name)
        
        if not from_group:
            return
        
        # 存储每个顶点的权重
        weights = {}
        for vertex in mesh.data.vertices:
            try:
                weight = from_group.weight(vertex.index)
                if weight > 0:
                    weights[vertex.index] = weight
            except RuntimeError:
                continue
        
        # 转移权重
        if weights:
            # 添加新权重
            for vertex_index, weight in weights.items():
                try:
                    current_weight = 0
                    try:
                        current_weight = to_group.weight(vertex_index)
                    except RuntimeError:
                        pass
                    # 使用 'REPLACE' 模式确保权重正确设置
                    to_group.add([vertex_index], current_weight + weight, 'REPLACE')
                except RuntimeError:
                    continue
        
        # 删除原始权重组
        mesh.vertex_groups.remove(from_group)
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_pose_bone and
                len(context.selected_pose_bones) > 1)
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        active_bone = context.active_pose_bone
        
        # 存储要处理的骨骼
        bones_to_process = [bone for bone in context.selected_pose_bones if bone != active_bone]
        
        # 切换到对象模式以修改骨骼
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 处理每个选中的骨骼
        for bone in bones_to_process:
            # 转移权重到活动骨骼
            for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
                self.transfer_weights(bone.name, active_bone.name, mesh)
        
        # 切换到编辑模式删除骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in bones_to_process:
            if bone.name in armature.edit_bones:
                edit_bone = armature.edit_bones[bone.name]
                armature.edit_bones.remove(edit_bone)
                log_bone_operation(context, "MergeToActive", f"{bone.name} -> {active_bone.name} on {obj.name}")
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        return {'FINISHED'}

class BONE_OT_remove_zero_weight(Operator):
    bl_idname = "bone.remove_zero_weight"
    bl_label = "清除零权重骨骼"
    bl_description = "删除所有没有权重的骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    include_with_children: BoolProperty(
        name="包含有子级的骨骼",
        description="同时删除带有子骨骼的零权重骨骼",
        default=False
    )
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE')
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        bones_to_remove = []
        
        # 收集所有骨骼的权重信息
        weight_data = {}
        for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
            for vertex_group in mesh.vertex_groups:
                # 初始化权重数据
                if vertex_group.name not in weight_data:
                    weight_data[vertex_group.name] = 0.0
                
                # 计算该骨骼的总权重
                for vertex in mesh.data.vertices:
                    try:
                        weight = vertex_group.weight(vertex.index)
                        weight_data[vertex_group.name] += weight
                    except RuntimeError:
                        continue
        
        # 检查每个骨骼
        for bone in armature.bones:
            # 如果骨骼没有权重组或权重为0
            if bone.name not in weight_data or weight_data[bone.name] < 0.0001:
                # 根据选项决定是否包含有子级的骨骼
                if not bone.children or self.include_with_children:
                    bones_to_remove.append(bone.name)
        
        if not bones_to_remove:
            self.report({'INFO'}, "没有找到零权重骨骼")
            return {'CANCELLED'}
        
        # 切换到编辑模式删除骨骼
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 删除收集到的零权重骨骼
        removed_count = 0
        for bone_name in bones_to_remove:
            if bone_name in armature.edit_bones:
                edit_bone = armature.edit_bones[bone_name]
                # 如果骨骼有子级，先将子级的父级设置为当前骨骼的父级
                if self.include_with_children and edit_bone.children:
                    parent = edit_bone.parent
                    for child in edit_bone.children:
                        child.parent = parent
                armature.edit_bones.remove(edit_bone)
                removed_count += 1
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        self.report({'INFO'}, f"已删除 {removed_count} 个零权重骨骼")
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "include_with_children")

class OBJECT_OT_RemoveRigidbodiesJoints(Operator):
    bl_idname = "object.remove_rigidbodies_joints"
    bl_label = "移除刚体与关节"
    bl_description = "删除名为 'rigidbodies' 或 'joints' 的对象及其所有子层级"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        targets = [obj for obj in bpy.data.objects if obj.name and obj.name.lower() in ("rigidbodies", "joints")]
        if not targets:
            self.report({'INFO'}, "未找到 'rigidbodies' 或 'joints' 对象")
            return {'CANCELLED'}
        total_deleted = 0
        for obj in targets:
            total_deleted += self._delete_hierarchy(obj)
        self.report({'INFO'}, f"已移除 {len(targets)} 个根对象，共删除 {total_deleted} 个对象")
        return {'FINISHED'}

    def _delete_hierarchy(self, root_obj):
        to_delete = []
        stack = [root_obj]
        seen = set()
        while stack:
            current = stack.pop()
            if not current or current.name in seen:
                continue
            seen.add(current.name)
            to_delete.append(current)
            for child in current.children:
                stack.append(child)
        deleted = 0
        for o in reversed(to_delete):
            try:
                bpy.data.objects.remove(o, do_unlink=True)
                deleted += 1
            except Exception:
                pass
        return deleted

class BONE_OT_remove_constraints(Operator):
    bl_idname = "bone.remove_constraints"
    bl_label = "移除骨骼约束"
    bl_description = "移除当前骨架所有 Pose 骨骼上的约束"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        arm_obj = obj
        prev_mode = arm_obj.mode if hasattr(arm_obj, "mode") else 'OBJECT'
        removed = 0
        try:
            bpy.ops.object.mode_set(mode='POSE')
        except Exception:
            pass
        for pbone in arm_obj.pose.bones:
            for c in list(pbone.constraints):
                try:
                    pbone.constraints.remove(c)
                    removed += 1
                except Exception:
                    continue
        try:
            bpy.ops.object.mode_set(mode=prev_mode)
        except Exception:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
        self.report({'INFO'}, f"已移除 {removed} 个骨骼约束")
        return {'FINISHED'}

class BONE_OT_apply_pose_transform(Operator):
    bl_idname = "bone.apply_pose_transform"
    bl_label = "应用姿态变换"
    bl_description = "将当前姿态设为静止姿态"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE')
    
    def execute(self, context):
        armature_obj = context.active_object
        
        # 存储所有使用该骨架的网格对象及其修改器信息
        mesh_modifiers = []
        # Get a reference to view layer objects for quicker access
        view_layer_objects = context.view_layer.objects
        for obj_iter in bpy.data.objects:
            if obj_iter.type == 'MESH':
                # Ensure the object is in the current view layer
                if obj_iter.name not in view_layer_objects:
                    continue # Skip this object if it's not in the view layer

                for mod in obj_iter.modifiers:
                    if mod.type == 'ARMATURE' and mod.object == armature_obj:
                        mesh_modifiers.append((obj_iter, mod.name))

        # 切换到物体模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 处理每个网格对象
        for obj, mod_name in mesh_modifiers:
            # 确保网格数据是单独的
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            
            # 如果对象有形态键，我们需要特殊处理
            if obj.data.shape_keys:
                # --- BEGIN MODIFIED SHAPE KEY HANDLING ---
                original_shape_key_data = []
                
                # 尝试查找基础形态键，支持多种可能的名称
                basis_key_names = ["Basis", "基态", "Base", "基础", "basis", "Key 1"]
                basis_key_block = None
                
                for basis_name in basis_key_names:
                    basis_key_block = obj.data.shape_keys.key_blocks.get(basis_name)
                    if basis_key_block:
                        print(f"Found basis key '{basis_name}' for {obj.name}")
                        break

                if not basis_key_block:
                    print(f"Warning: Object {obj.name} has shape keys but no recognized basis key. Will try to use first key as basis.")
                    # 如果没有找到标准的基础键，尝试使用第一个形态键作为基础
                    if len(obj.data.shape_keys.key_blocks) > 0:
                        basis_key_block = obj.data.shape_keys.key_blocks[0]
                        print(f"Using '{basis_key_block.name}' as basis key for {obj.name}")
                    else:
                        print(f"No shape keys found in {obj.name}, skipping shape key processing.")
                        basis_key_block = None

                if basis_key_block:
                    # 获取基础坐标
                    basis_coords = [v.co.copy() for v in basis_key_block.data]

                    for kb in obj.data.shape_keys.key_blocks:
                        if kb == basis_key_block: # 跳过基础键
                            continue
                        
                        key_name = kb.name
                        key_value = kb.value
                        current_shape_key_coords = [v.co.copy() for v in kb.data]
                        
                        if len(current_shape_key_coords) != len(basis_coords):
                            print(f"Warning: Vertex count mismatch for shape key {key_name} in object {obj.name}. Skipping this shape key.")
                            continue
                            
                        deltas = [current_shape_key_coords[i] - basis_coords[i] for i in range(len(basis_coords))]
                        original_shape_key_data.append({
                            'name': key_name,
                            'value': key_value,
                            'deltas': deltas
                        })
                    print(f"Stored delta data for {len(original_shape_key_data)} shape keys in {obj.name}")

                # Remove old logic for storing original_values, shape_key_positions, base_positions
                # Commenting out the old block:
                # # 存储原始形态键值
                # original_values = {}
                # for kb in obj.data.shape_keys.key_blocks:
                #     original_values[kb.name] = kb.value
                # 
                # # 存储每个形态键的变形位置
                # shape_key_positions = {}
                # 
                # # 对每个形态键创建一个临时对象
                # for kb in obj.data.shape_keys.key_blocks:
                #     if kb.name != "Basis":
                #         # 创建临时对象
                #         temp_obj = obj.copy()
                #         temp_obj.data = obj.data.copy()
                #         bpy.context.scene.collection.objects.link(temp_obj)
                #         
                #         # 重置所有形态键值为0，然后设置当前形态键为1
                #         for temp_kb in temp_obj.data.shape_keys.key_blocks:
                #             temp_kb.value = 1.0 if temp_kb.name == kb.name else 0.0
                #         
                #         # 让形态键生效
                #         bpy.context.view_layer.update()
                #         
                #         # 评估修改器
                #         depsgraph = bpy.context.evaluated_depsgraph_get()
                #         temp_obj_eval = temp_obj.evaluated_get(depsgraph)
                #         
                #         # 创建一个新的网格数据来存储当前状态
                #         temp_mesh = bpy.data.meshes.new_from_object(temp_obj_eval)
                #         
                #         # 删除原始临时对象
                #         bpy.data.objects.remove(temp_obj, do_unlink=True)
                #         
                #         # 存储变形后的位置
                #         shape_key_positions[kb.name] = [v.co.copy() for v in temp_mesh.vertices]
                #         
                #         # 删除临时网格
                #         bpy.data.meshes.remove(temp_mesh)
                # 
                # # 创建基础形状的临时对象
                # base_obj = obj.copy()
                # base_obj.data = obj.data.copy()
                # bpy.context.scene.collection.objects.link(base_obj)
                # 
                # # 重置所有形态键值为0
                # for kb_base in base_obj.data.shape_keys.key_blocks:
                #     kb_base.value = 0
                # 
                # # 让形态键生效
                # bpy.context.view_layer.update()
                # 
                # # 评估修改器
                # depsgraph_base = bpy.context.evaluated_depsgraph_get()
                # base_obj_eval = base_obj.evaluated_get(depsgraph_base)
                # 
                # # 创建一个新的网格数据来存储当前状态
                # base_mesh = bpy.data.meshes.new_from_object(base_obj_eval)
                # 
                # # 删除原始基础对象
                # bpy.data.objects.remove(base_obj, do_unlink=True)
                # 
                # # 存储基础位置
                # base_positions = [v.co.copy() for v in base_mesh.vertices]
                # 
                # # 删除基础网格
                # bpy.data.meshes.remove(base_mesh)
                
                # 只有当我们有形态键数据时才删除和重建形态键
                if basis_key_block:
                    # 删除原始对象的形态键 (This will be followed by reconstruction)
                    obj.shape_key_clear()
                    
                    # 应用原始对象的修改器
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    bpy.ops.object.modifier_apply(modifier=mod_name)
                    
                    # --- NEW SHAPE KEY RECONSTRUCTION --- 
                    # 重新创建Basis形态键
                    new_basis_key = obj.shape_key_add(name="Basis")
                    new_basis_key.interpolation = 'KEY_LINEAR'
                    # After applying modifier, new_basis_key.data contains the posed mesh vertices

                    # 重建其他形态键
                    if original_shape_key_data:
                        for sk_data in original_shape_key_data:
                            key_name = sk_data['name']
                            key_value = sk_data['value']
                            deltas = sk_data['deltas']

                            new_key = obj.shape_key_add(name=key_name)
                            new_key.interpolation = 'KEY_LINEAR'

                            if len(new_basis_key.data) != len(deltas):
                                print(f"Error: Vertex count mismatch during reconstruction for shape key {key_name} in object {obj.name}. Cannot reconstruct.")
                                continue

                            for i in range(len(new_basis_key.data)):
                                new_key.data[i].co = new_basis_key.data[i].co + deltas[i]
                            
                            new_key.value = key_value
                        print(f"Reconstructed {len(original_shape_key_data)} shape keys for {obj.name} using delta method.")
                    else:
                        print(f"No additional shape keys to reconstruct for {obj.name}")
                else:
                    # 如果没有有效的形态键数据，直接应用修改器而不处理形态键
                    print(f"No valid shape key data found for {obj.name}, applying modifier without shape key processing.")
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    bpy.ops.object.modifier_apply(modifier=mod_name)
                
                # --- END MODIFIED SHAPE KEY HANDLING ---

                # 重新添加骨架修改器
                mod = obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = armature_obj
                mod.use_vertex_groups = True
                mod.use_bone_envelopes = False
                
                obj.select_set(False)
            else:
                # 对于没有形态键的对象，直接应用修改器
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.modifier_apply(modifier=mod_name)
                
                # 重新添加骨架修改器
                mod = obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = armature_obj
                mod.use_vertex_groups = True
                mod.use_bone_envelopes = False
                
                obj.select_set(False)
        
        # 选择骨架对象
        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)
        
        # 切换到姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        # 应用姿态为静止姿态
        bpy.ops.pose.armature_apply(selected=False)
        
        # 切换回物体模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 应用骨架的变换
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        
        # 切换回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        self.report({'INFO'}, "已成功应用姿态变换")
        return {'FINISHED'}

class BONE_OT_GFL2_preprocess(Operator):
    bl_idname = "object.gfl2_preprocess" # 修改 bl_idname 以反映操作对象
    bl_label = "少前2模型一键预处理" # 修改 bl_label
    bl_description = "一键处理少前2模型：缩放，应用姿态和变换，处理特定骨骼，删除lod1模型，处理face模型顶点组，清理零权重骨骼(保留眼睛骨骼)" # 修改 bl_description
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 允许在物体模式或姿态模式下启动，只要活动对象是骨架
        return (context.active_object and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选择一个骨架对象")
            return {'CANCELLED'}

        armature = obj.data
        original_mode = context.mode # 记录原始模式

        try:
            # --- 最终调整后的顺序 --- #

            # --- 1. 删除LOD1模型 (物体模式) --- <--- 使用 bpy.data.objects.remove() 重构
            print("步骤 1: 删除 LOD1 模型 (直接移除)...")
            if context.mode != 'OBJECT': # 确保在物体模式
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT') # 清理选择以防万一

            deleted_lod_count = 0
            # 收集需要删除的对象名称，因为在迭代时直接删除可能导致问题
            objects_to_delete_names = [o.name for o in bpy.data.objects if o.type == 'MESH' and 'lod1' in o.name.lower()]
            
            if objects_to_delete_names:
                print(f"  - 找到 {len(objects_to_delete_names)} 个 LOD1 模型准备删除...")
                for obj_name in objects_to_delete_names:
                    obj_to_delete = bpy.data.objects.get(obj_name)
                    if obj_to_delete: # 确保对象仍然存在
                        try:
                            bpy.data.objects.remove(obj_to_delete, do_unlink=True)
                            print(f"    - 已移除对象: {obj_name}")
                            deleted_lod_count += 1
                        except Exception as e_remove_lod1:
                            print(f"    - 移除对象 '{obj_name}' 时出错 (可能已被删除或有特殊链接): {e_remove_lod1}")
                print(f"  - 完成 LOD1 模型移除尝试，移除了 {deleted_lod_count} 个。")
            else:
                print("  - 未找到 LOD1 模型。")

            # --- 2. 缩放 (物体模式) ---
            print("步骤 2: 缩放骨架...")
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            # 确保只选择骨架
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.transform.resize(value=(1000, 1000, 1000))
            print("  - 骨架缩放完成。")

            # --- 3. 应用姿态为静止姿态 (姿态模式) ---
            print("步骤 3: 应用当前姿态为静止姿态...")
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.select_all(action='SELECT')
            bpy.ops.pose.armature_apply(selected=False)
            bpy.ops.pose.select_all(action='DESELECT')
            print("  - 应用姿态完成。")

            # --- 3.5. 修复没有骨架修改器的模型父级关系 (物体模式) ---
            print("步骤 3.5: 修复没有骨架修改器的模型父级关系...")
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            
            # 查找所有子对象中没有骨架修改器的网格对象
            models_without_armature_modifier = []
            for child in obj.children:
                if child.type == 'MESH':
                    has_armature_modifier = False
                    for modifier in child.modifiers:
                        if modifier.type == 'ARMATURE':
                            has_armature_modifier = True
                            break
                    if not has_armature_modifier:
                        models_without_armature_modifier.append(child)
            
            print(f"  - 找到 {len(models_without_armature_modifier)} 个没有骨架修改器的模型需要处理...")
            
            # 处理每个没有骨架修改器的模型
            processed_models = 0
            for model in models_without_armature_modifier:
                try:
                    print(f"    - 处理模型: {model.name}")
                    
                    # 选择并激活该模型
                    bpy.ops.object.select_all(action='DESELECT')
                    model.select_set(True)
                    context.view_layer.objects.active = model
                    
                    # 清除父级并保持变换结果
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    print(f"      - 已清除父级并保持变换")
                    
                    # 重新设置父级为骨架（使用对象父级，不使用骨骼父级）
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
                    print(f"      - 已重新设置父级为骨架")
                    
                    # 为该模型添加骨架修改器
                    try:
                        # 确保模型被选中并激活
                        bpy.ops.object.select_all(action='DESELECT')
                        model.select_set(True)
                        context.view_layer.objects.active = model
                        
                        # 添加骨架修改器
                        armature_modifier = model.modifiers.new(name="Armature", type='ARMATURE')
                        armature_modifier.object = obj  # 设置骨架对象为用户选择的骨架
                        print(f"      - 已添加骨架修改器并设置目标为: {obj.name}")
                        
                    except Exception as e_modifier:
                        print(f"      - 添加骨架修改器时出错: {e_modifier}")
                    
                    processed_models += 1
                    
                except Exception as e_model_fix:
                    print(f"      - 处理模型 {model.name} 时出错: {e_model_fix}")
                    continue
            
            if processed_models > 0:
                print(f"  - 成功处理了 {processed_models} 个没有骨架修改器的模型")
            else:
                print("  - 没有需要处理的模型或处理失败")
            
            # 清理选择状态
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            # --- 4. 处理特定骨骼 & Root 合并 (姿态模式) ---
            print("步骤 4: 处理特定骨骼和 Root 合并...")
            if context.mode != 'POSE':
                 bpy.ops.object.mode_set(mode='POSE')
            # ... (骨骼合并逻辑保持不变) ...
            # 合并 "part" 或 "finger4" (排除 CHest_M)
            print("  - 检查 'part'/'finger4' 骨骼 (排除 CHest_M)...")
            bpy.ops.pose.select_all(action='DESELECT')
            found_bones_part1 = False
            bones_to_select_p1 = []
            for pose_bone in obj.pose.bones:
                bone_name_lower = pose_bone.name.lower()
                # 排除 Chest_M 骨骼（不区分大小写）
                if pose_bone.name.lower() == "chest_m":
                    print(f"    - 跳过保护骨骼: {pose_bone.name}")
                    continue
                if ("part" in bone_name_lower or "finger4" in bone_name_lower) and pose_bone.parent:
                    bones_to_select_p1.append(pose_bone.name)
                    found_bones_part1 = True
            if found_bones_part1:
                print(f"    - 找到 {len(bones_to_select_p1)} 个，准备合并到父级...")
                for bone_name in bones_to_select_p1:
                    if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                if context.selected_pose_bones:
                    bpy.ops.bone.merge_to_parent()
                    print("    - 'part'/'finger4' 骨骼合并完成。")
                else:
                    print("    - 警告：选择 'part'/'finger4' 骨骼失败或没有选中项，跳过合并。")
            else:
                print("  - 未找到 'part'/'finger4' 骨骼。")
            # 合并 "skin" (排除特定前缀和CHest_M)
            print("  - 检查 'skin' 骨骼 (排除 'lf', 'rf', 'rt_', 'lt_', CHest_M)...")
            bpy.ops.pose.select_all(action='DESELECT')
            found_bones_part2 = False
            bones_to_select_p2 = []
            exclude_prefixes = ("lf", "rf", "rt_", "lt_")
            for pose_bone in obj.pose.bones:
                bone_name = pose_bone.name.lower()
                # 排除 Chest_M 骨骼（不区分大小写）
                if bone_name == "chest_m":
                    print(f"    - 跳过保护骨骼: {pose_bone.name}")
                    continue
                if ("skin" in bone_name and
                    not any(bone_name.startswith(prefix) for prefix in exclude_prefixes) and
                    not any(f"_{prefix}" in bone_name for prefix in exclude_prefixes) and
                    pose_bone.parent):
                    bones_to_select_p2.append(pose_bone.name)
                    found_bones_part2 = True
            if found_bones_part2:
                print(f"    - 找到 {len(bones_to_select_p2)} 个，准备合并到父级...")
                for bone_name in bones_to_select_p2:
                    if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                if context.selected_pose_bones:
                    bpy.ops.bone.merge_to_parent()
                    print("    - 'skin' 骨骼合并完成。")
                else:
                    print("    - 警告：选择 'skin' 骨骼失败或没有选中项，跳过合并。")
            else:
                print("  - 未找到符合条件的 'skin' 骨骼。")
            # 合并 "cup" (排除CHest_M)
            print("  - 检查 'cup' 骨骼 (排除CHest_M)...")
            bpy.ops.pose.select_all(action='DESELECT')
            found_bones_cup = False
            bones_to_select_cup = []
            for pose_bone in obj.pose.bones:
                bone_name_lower = pose_bone.name.lower()
                # 排除 Chest_M 骨骼（不区分大小写）
                if bone_name_lower == "chest_m":
                    print(f"    - 跳过保护骨骼: {pose_bone.name}")
                    continue
                if "cup" in bone_name_lower and pose_bone.parent:
                    bones_to_select_cup.append(pose_bone.name)
                    found_bones_cup = True
            if found_bones_cup:
                print(f"    - 找到 {len(bones_to_select_cup)} 个，准备合并到父级...")
                for bone_name in bones_to_select_cup:
                    if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                if context.selected_pose_bones:
                    bpy.ops.bone.merge_to_parent()
                    print("    - 'cup' 骨骼合并完成。")
                else:
                    print("    - 警告：选择 'cup' 骨骼失败或没有选中项，跳过合并。")
            else:
                print("  - 未找到 'cup' 骨骼。")
            # 处理 root 骨骼
            print("  - 处理 Root 骨骼合并...")
            bpy.ops.pose.select_all(action='DESELECT')
            root_bone = None
            for pose_bone in obj.pose.bones:
                if pose_bone.name.lower() == "root":
                    root_bone = pose_bone
                    break
            if root_bone:
                print(f"    - 找到 Root 骨骼: {root_bone.name}")
                try:
                    bpy.ops.pose.select_all(action='DESELECT')
                    obj.data.bones.active = root_bone.bone
                    root_bone.bone.select = True
                except Exception as e_select_root:
                    print(f"    - 警告：选择或设置Root为活动骨骼时出错: {e_select_root}")
                    root_bone = None
                if root_bone:
                    root_parent = root_bone.parent
                    siblings_selected = False
                    bones_to_select_siblings = []
                    if root_parent:
                        print(f"    - 查找 Root 的同层级骨骼 (父级: {root_parent.name})...")
                        for pose_bone in obj.pose.bones:
                            if pose_bone != root_bone and pose_bone.parent == root_parent:
                                bones_to_select_siblings.append(pose_bone.name)
                                siblings_selected = True
                                print(f"      - 待选同层级: {pose_bone.name}")
                    if siblings_selected:
                        print("    - 合并同层级骨骼到 Root...")
                        for bone_name in bones_to_select_siblings:
                            if bone_name in obj.pose.bones: obj.pose.bones[bone_name].bone.select = True
                        obj.data.bones.active = root_bone.bone
                        root_bone.bone.select = True 
                        if len(context.selected_pose_bones) > 1:
                            bpy.ops.bone.merge_to_active()
                        else:
                             print("    - 警告：选择同层级骨骼后，选中数量不足以合并。")
                        bpy.ops.pose.select_all(action='DESELECT')
                    if root_parent:
                        print(f"    - 选择 Root 的父级 {root_parent.name} 并合并到 Root...")
                        bpy.ops.pose.select_all(action='DESELECT')
                        root_bone.bone.select = True
                        obj.data.bones.active = root_bone.bone
                        if root_parent.name in obj.pose.bones:
                            obj.pose.bones[root_parent.name].bone.select = True
                            if len(context.selected_pose_bones) == 2:
                                bpy.ops.bone.merge_to_active()
                                print("    - Root 父级合并完成。")
                            else:
                                print("    - 警告：选择父级骨骼后，选中数量不为2，无法合并。")
                        else:
                            print(f"    - 警告: 无法在 Pose 模式下找到父级骨骼 {root_parent.name}。")
                        bpy.ops.pose.select_all(action='DESELECT')
            else:
                print("  - 未找到名为 'root' 的骨骼。")

            # --- 5. 清理零权重骨骼 (物体/编辑模式) ---
            print("步骤 5: 清理零权重骨骼...")
            # ... (清理逻辑保持不变，确保先切到 OBJECT 模式检查权重) ...
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == obj]
            print(f"  - 检查 {len(mesh_objects)} 个当前关联模型的权重...")
            bones_with_weights = set()
            for mesh_obj in mesh_objects:
                 if not mesh_obj.vertex_groups: continue
                 for vgroup in mesh_obj.vertex_groups:
                      if vgroup.name not in armature.bones: continue
                      has_weight = False
                      if vgroup.index in [g.group for v in mesh_obj.data.vertices for g in v.groups]:
                           for vert in mesh_obj.data.vertices:
                                try:
                                     weight = vgroup.weight(vert.index)
                                     if weight > 1e-6:
                                          has_weight = True
                                          break
                                except RuntimeError:
                                     continue
                      if has_weight:
                           bones_with_weights.add(vgroup.name)
            print(f"  - {len(bones_with_weights)} 个骨骼具有有效权重。")
            excluded_bone_names = {"face_eye_l", "face_eye_r", "face_base_eye_l", "face_base_eye_r"}
            bones_to_remove = []
            for bone in armature.bones:
                if (bone.name not in bones_with_weights and
                    bone.name.lower() not in excluded_bone_names and
                    bone.name.lower() != "chest_m"):  # 排除 Chest_M 骨骼（不区分大小写）
                    bones_to_remove.append(bone.name)
            print(f"  - 找到 {len(bones_to_remove)} 个零权重骨骼准备删除 (已排除眼睛骨骼)。")
            if bones_to_remove:
                print("  - 切换到编辑模式删除骨骼...")
                bpy.ops.object.mode_set(mode='EDIT')
                removed_count = 0
                for bone_name in bones_to_remove:
                    if bone_name in armature.edit_bones:
                        edit_bone = armature.edit_bones[bone_name]
                        parent = edit_bone.parent
                        children_to_reparent = list(edit_bone.children)
                        if children_to_reparent and parent and parent.name in armature.edit_bones:
                             valid_parent_edit_bone = armature.edit_bones[parent.name]
                             for child in children_to_reparent:
                                  if child.name in armature.edit_bones:
                                       armature.edit_bones[child.name].parent = valid_parent_edit_bone
                        try:
                            armature.edit_bones.remove(edit_bone)
                            removed_count += 1
                        except Exception as e_bone_remove:
                             print(f"      - 删除骨骼 {bone_name} 时出错: {e_bone_remove}")
                print(f"  - 实际删除了 {removed_count} 个零权重骨骼。")
            else:
                print("  - 没有需要删除的零权重骨骼。")

            # --- 6. 应用变换 (物体模式) ---
            print("步骤 6: 应用骨架和剩余子模型变换...")
            # ... (应用变换逻辑保持不变) ...
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            mesh_children_final = []
            for child in obj.children:
                if child.type == 'MESH':
                    child.select_set(True)
                    mesh_children_final.append(child)
            if context.selected_objects:
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                print(f"  - 已对骨架和 {len(mesh_children_final)} 个剩余子模型应用变换。")
            else:
                print("  - 没有选中对象可以应用变换。")
            bpy.ops.object.select_all(action='DESELECT')

            # --- 7. 处理面部模型顶点组 (物体模式) ---
            print("步骤 7: 处理剩余面部模型顶点组...")
            # ... (面部顶点组处理逻辑保持不变) ...
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            face_models_final = [o for o in bpy.data.objects if o.type == 'MESH' and 'face' in o.name.lower()]
            print(f"  - 找到 {len(face_models_final)} 个剩余的面部模型进行顶点组处理...")
            face_models_processed = 0
            for face_model in face_models_final:
                print(f"    - 处理模型: {face_model.name}")
                bpy.ops.object.select_all(action='DESELECT')
                context.view_layer.objects.active = face_model
                face_model.select_set(True)
                print("      - 清除现有顶点组...")
                while face_model.vertex_groups:
                    try:
                         face_model.vertex_groups.remove(face_model.vertex_groups[0])
                    except Exception as e_vg_remove:
                         print(f"        - 删除顶点组时出错 (可能已删除): {e_vg_remove}")
                         break
                print("      - 创建 Head_M, Face_Eye_L, Face_Eye_R 顶点组...")
                head_group = face_model.vertex_groups.new(name="Head_M")
                eye_l_group = face_model.vertex_groups.new(name="Face_Eye_L")
                eye_r_group = face_model.vertex_groups.new(name="Face_Eye_R")
                eye_material_indices = []
                if face_model.data.materials:
                    for i, mat in enumerate(face_model.data.materials):
                        if mat:
                            mat_name_lower = mat.name.lower()
                            if ((("eyenew" in mat_name_lower and "eyenewmu" not in mat_name_lower) or
                                 "eyenewadd" in mat_name_lower) and
                                not any(exclude in mat_name_lower for exclude in ["eyenewmul", "eyenewmult"])):
                                eye_material_indices.append(i)
                print("      - 分配顶点到组...")
                verts_head = []
                verts_eye_l = []
                verts_eye_r = []
                processed_verts = set()
                if not face_model.data.polygons:
                     print("      - 警告: 模型没有面，无法分配顶点组。")
                     continue
                for poly in face_model.data.polygons:
                    is_eye_material = poly.material_index in eye_material_indices
                    for vert_idx in poly.vertices:
                        if vert_idx in processed_verts: continue
                        vert = face_model.data.vertices[vert_idx]
                        processed_verts.add(vert_idx)
                        if is_eye_material:
                            if vert.co.x > 0: verts_eye_l.append(vert_idx)
                            else: verts_eye_r.append(vert_idx)
                        else: verts_head.append(vert_idx)
                if verts_head: head_group.add(verts_head, 1.0, 'REPLACE');
                if verts_eye_l: eye_l_group.add(verts_eye_l, 1.0, 'REPLACE');
                if verts_eye_r: eye_r_group.add(verts_eye_r, 1.0, 'REPLACE');
                face_models_processed += 1
                bpy.ops.object.select_all(action='DESELECT')
            if face_models_processed == 0 and len(face_models_final) > 0:
                print("  - 未成功处理任何面部模型顶点组。")
            elif face_models_processed > 0:
                print(f"  - 已处理 {face_models_processed} 个面部模型顶点组。")

            # --- 8. 完成与报告 --- (旧的步骤7)
            # 切换回原始模式
            bpy.ops.object.mode_set(mode=original_mode if original_mode in {'OBJECT', 'POSE', 'EDIT'} else 'OBJECT') # 确保是有效模式

            # 最终报告
            final_message = "少前2模型预处理完成。"
            self.report({'INFO'}, final_message)
            print(f"\n{final_message}")

        except Exception as e:
            # 发生错误时，尝试恢复原始模式
            try:
                if bpy.context.mode != original_mode:
                   bpy.ops.object.mode_set(mode=original_mode if original_mode in {'OBJECT', 'POSE', 'EDIT'} else 'OBJECT')
            except Exception as mode_restore_error:
                 print(f"尝试恢复原始模式时也发生错误: {mode_restore_error}")
            # 报告错误
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"处理过程中发生错误: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

class BONE_OT_merge_siblings_half(Operator):
    bl_idname = "bone.merge_siblings_half"
    bl_label = "左右对称合并"
    bl_description = "将同层级的骨骼按左右各合并一半（保持圆周分布）"
    bl_options = {'REGISTER', 'UNDO'}
    
    use_global_center: bpy.props.BoolProperty(
        name="使用全局中心",
        description="使用所有选定骨骼的中心作为参考点，保持垂直对齐",
        default=True
    )
    
    include_root_bones: bpy.props.BoolProperty(
        name="包含根骨骼",
        description="同时处理没有父级的根骨骼",
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE' and
                context.selected_pose_bones)
    
    def execute(self, context):
        obj = context.active_object
        armature = obj.data
        
        # 计算全局中心
        global_center = None
        if self.use_global_center:
            all_selected_bones = context.selected_pose_bones
            global_center = sum((b.head for b in all_selected_bones), Vector()) / len(all_selected_bones)
        
        # 收集选中骨骼的层级
        parent_level = {}
        for bone in context.selected_pose_bones:
            # 判断是否处理根骨骼
            if bone.parent or self.include_root_bones:
                # 计算骨骼所在层级深度
                depth = 0
                parent = bone.parent
                while parent:
                    depth += 1
                    parent = parent.parent
                parent_level[depth] = parent_level.get(depth, set())
                parent_level[depth].add(bone)
        
        # 按层级处理骨骼
        for depth, bones in parent_level.items():
            if len(bones) < 2:
                continue
            
            # 将骨骼按圆周顺序排序
            bones_list = list(bones)
            
            # 决定使用哪个中心点
            if self.use_global_center and global_center:
                center = global_center
            else:
                center = sum((b.head for b in bones_list), Vector()) / len(bones_list)
            
            # 计算每个骨骼相对于中心的角度
            def get_angle(bone):
                vec = bone.head - center
                return math.atan2(vec.y, vec.x)
            
            bones_list.sort(key=get_angle)
            
            # 计算需要保留的骨骼数量（总数的一半，向上取整）
            target_count = (len(bones_list) + 1) // 2
            
            # 按圆周均匀选择要保留的骨骼
            bones_to_keep = []
            step = len(bones_list) / target_count
            for i in range(target_count):
                index = int(i * step)
                bones_to_keep.append(bones_list[index])
            
            # 将其他骨骼的权重转移到最近的保留骨骼
            bones_to_remove = [b for b in bones_list if b not in bones_to_keep]
            
            # 切换到对象模式进行权重转移
            bpy.ops.object.mode_set(mode='OBJECT')
            
            for bone in bones_to_remove:
                # 找到最近的保留骨骼
                closest_bone = min(bones_to_keep, 
                                 key=lambda b: (bone.head - b.head).length)
                
                # 转移权重
                for mesh in [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == context.active_object]:
                    self.transfer_weights(bone.name, closest_bone.name, mesh)
                log_bone_operation(context, "MergeSiblingsHalf", f"{bone.name} -> {closest_bone.name} on {obj.name}")
            
            # 切换到编辑模式删除骨骼
            bpy.ops.object.mode_set(mode='EDIT')
            
            # 删除已合并的骨骼
            for bone in bones_to_remove:
                if bone.name in armature.edit_bones:
                    edit_bone = armature.edit_bones[bone.name]
                    # 如果骨骼有子级，先将子级的父级设置为当前骨骼的父级
                    if edit_bone.children:
                        parent = edit_bone.parent
                        for child in edit_bone.children:
                            child.parent = parent
                    armature.edit_bones.remove(edit_bone)
        
        # 返回姿态模式
        bpy.ops.object.mode_set(mode='POSE')
        
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_global_center")
        layout.prop(self, "include_root_bones")
        
    @staticmethod
    def transfer_weights(from_bone_name, to_bone_name, mesh):
        """
        改进的权重转移函数
        """
        # 确保目标权重组存在
        if to_bone_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=to_bone_name)
        
        # 获取源和目标权重组
        from_group = mesh.vertex_groups.get(from_bone_name)
        to_group = mesh.vertex_groups.get(to_bone_name)
        
        if not from_group:
            return
        
        # 存储每个顶点的权重
        weights = {}
        for vertex in mesh.data.vertices:
            try:
                weight = from_group.weight(vertex.index)
                if weight > 0:
                    weights[vertex.index] = weight
            except RuntimeError:
                continue
        
        # 转移权重
        if weights:
            # 添加新权重
            for vertex_index, weight in weights.items():
                try:
                    current_weight = 0
                    try:
                        current_weight = to_group.weight(vertex_index)
                    except RuntimeError:
                        pass
                    # 使用 'REPLACE' 模式确保权重正确设置
                    to_group.add([vertex_index], current_weight + weight, 'REPLACE')
                except RuntimeError:
                    continue
        
        # 删除原始权重组
        mesh.vertex_groups.remove(from_group)

class BONE_OT_mmd_quick_merge(Operator):
    bl_idname = "bone.mmd_quick_merge"
    bl_label = "MMD快速合并"
    bl_description = "按预设规则将MMD冗余骨并入主体骨"
    bl_options = {'REGISTER', 'UNDO'}

    merge_spine: BoolProperty(name="脊椎", default=True)
    merge_arms: BoolProperty(name="手臂", default=True)
    merge_legs: BoolProperty(name="腿部", default=True)
    merge_leg_ik: BoolProperty(name="合并腿部IK冗余", default=True)
    preserve_upperbody: BoolProperty(name="保留上躯干(Ubody/UpperBody)", default=True)
    shoulder_c_target: EnumProperty(
        name="肩C目标",
        items=[('ARM', '并入臂', ''), ('SHOULDER', '并入肩', '')],
        default='ARM'
    )
    delete_bones: BoolProperty(name="删除源骨骼", default=True)
    report_only: BoolProperty(name="仅预览", default=False)
    log_actions: BoolProperty(name="记录日志", default=True)

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj and obj.type == 'ARMATURE':
            return True
        for o in context.selected_objects:
            if o.type == 'ARMATURE':
                return True
        return False

    def _get_armature(self, context):
        obj = context.object
        if obj and obj.type == 'ARMATURE':
            return obj
        for o in context.selected_objects:
            if o.type == 'ARMATURE':
                return o
        for o in bpy.data.objects:
            if o.type == 'ARMATURE':
                return o
        return None

    def _get_meshes_for_armature(self, arm):
        meshes = []
        for o in bpy.data.objects:
            if o.type == 'MESH':
                for mod in o.modifiers:
                    if mod.type == 'ARMATURE' and getattr(mod, 'object', None) == arm:
                        meshes.append(o)
                        break
        return meshes

    def _bone_exists(self, arm, name):
        try:
            return name in {b.name for b in arm.data.bones}
        except Exception:
            return False

    def _merge_one(self, context, arm, meshes, src, dst):
        for m in meshes:
            try:
                BONE_OT_merge_to_parent.transfer_weights(src, dst, m)
            except Exception:
                pass
        if self.log_actions:
            try:
                log_bone_operation(context, "QuickMerge", f"{src} -> {dst} on {arm.name}")
            except Exception:
                pass
        if self.delete_bones and self._bone_exists(arm, src):
            bpy.context.view_layer.objects.active = arm
            try:
                prev_mode = arm.mode
            except Exception:
                prev_mode = 'OBJECT'
            bpy.ops.object.mode_set(mode='EDIT')
            eb = arm.data.edit_bones
            src_eb = eb.get(src)
            dst_eb = eb.get(dst)
            if src_eb:
                for b in eb:
                    if b.parent == src_eb:
                        b.parent = dst_eb
                eb.remove(src_eb)
            bpy.ops.object.mode_set(mode='POSE')

    def execute(self, context):
        arm = self._get_armature(context)
        if not arm:
            self.report({'ERROR'}, "未找到骨架")
            return {'CANCELLED'}
        meshes = self._get_meshes_for_armature(arm)

        merges = []

        if self.merge_spine:
            spine_pairs = [
                ("ParentNode", "LowerBody"),
                ("Center", "LowerBody"),
                ("ControlNode", "LowerBody"),
                ("Groove", "LowerBody"),
                ("acc_bo2_end", "UpperBody"),
                ("acc_bo2", "UpperBody"),
                ("2000_SMiddle心", "UpperBody"),
            ]
            for src, dst in spine_pairs:
                if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                    merges.append((src, dst))
            if not self.preserve_upperbody:
                if self._bone_exists(arm, "UpperBody") and self._bone_exists(arm, "LowerBody"):
                    merges.append(("UpperBody", "LowerBody"))
                if self._bone_exists(arm, "Ubody") and self._bone_exists(arm, "LowerBody"):
                    merges.append(("Ubody", "LowerBody"))
            if self._bone_exists(arm, "LowerBody") and self._bone_exists(arm, "Waist"):
                merges.append(("LowerBody", "Waist"))
            for side in ("L", "R"):
                s = f"_shadow_LegD_{side}"
                if self._bone_exists(arm, s) and self._bone_exists(arm, "Waist"):
                    merges.append((s, "Waist"))
            for side in ("L", "R"):
                s = f"_shadow_ShoulderC_{side}"
                if self._bone_exists(arm, s) and self._bone_exists(arm, "UpperBody3"):
                    merges.append((s, "UpperBody3"))

        if self.merge_arms:
            for side in ("L", "R"):
                shoulder_target = ("Arm_" + side) if self.shoulder_c_target == 'ARM' else ("Shoulder_" + side)
                base_pairs = [
                    (f"ShoulderP_{side}", f"Shoulder_{side}"),
                    (f"ArmWIK_{side}", f"Arm_{side}"),
                    (f"ArmW_{side}", f"Arm_{side}"),
                    (f"ArmWTip_{side}", f"Arm_{side}"),
                ]
                for src, dst in base_pairs:
                    if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                        merges.append((src, dst))
                sc = f"ShoulderC_{side}"
                if self._bone_exists(arm, sc) and self._bone_exists(arm, shoulder_target):
                    merges.append((sc, shoulder_target))
                dummy_sc = f"_dummy_ShoulderC_{side}"
                if self._bone_exists(arm, dummy_sc) and self._bone_exists(arm, shoulder_target):
                    merges.append((dummy_sc, shoulder_target))
                for src in (f"ArmTwistWTip_{side}", f"ArmTwistWIK_{side}", f"ArmTwistW_{side}", f"ArmTwist自動IK_{side}", f"ArmTwist自動Tip_{side}", f"ArmTwist自動_{side}"):
                    dst = f"ArmTwist_{side}"
                    if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                        merges.append((src, dst))
                for src in (f"ElbowW_{side}", f"ElbowWIK_{side}", f"ElbowWTip_{side}", f"ArmTwist_{side}", f"HandTwist_{side}"):
                    dst = f"Elbow_{side}"
                    if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                        merges.append((src, dst))
                for src in (f"WristW_{side}", f"HandTwist自動Tip_{side}", f"HandTwistWIK_{side}", f"HandTwist自動IK_{side}", f"HandTwist自動_{side}", f"HandTwistW_{side}", f"HandTwistWTip_{side}", f"Dummy_{side}"):
                    dst = f"Wrist_{side}"
                    if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                        merges.append((src, dst))

        if self.merge_legs:
            for side in ("L", "R"):
                for src, dst in (
                    (f"LegD_{side}", f"Leg_{side}"),
                    (f"_dummy_LegD_{side}", f"Leg_{side}"),
                    (f"_shadow_KneeD_{side}", f"Leg_{side}"),
                    (f"KneeD_{side}", f"Knee_{side}"),
                    (f"_dummy_KneeD_{side}", f"Knee_{side}"),
                    (f"_shadow_AnkleD_{side}", f"Knee_{side}"),
                    (f"AnkleD_{side}", f"Ankle_{side}"),
                    (f"_dummy_AnkleD_{side}", f"Ankle_{side}"),
                    (f"LegTipEX_{side}", f"ToeTip_{side}"),
                    (f"_dummy_LegTipEX_{side}", f"ToeTip_{side}"),
                    (f"_shadow_LegTipEX_{side}", f"ToeTip_{side}"),
                    (f"ToeTipXRotation_{side}", f"ToeTip_{side}"),
                ):
                    if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                        merges.append((src, dst))
            if self._bone_exists(arm, "LeftLeg_ex") and self._bone_exists(arm, "Knee_L"):
                merges.append(("LeftLeg_ex", "Knee_L"))
            if self._bone_exists(arm, "RightLeg_ex") and self._bone_exists(arm, "Knee_R"):
                merges.append(("RightLeg_ex", "Knee_R"))

        if self.merge_leg_ik:
            for side in ("L", "R"):
                for src, dst in (
                    (f"LegIKParent_{side}", f"Leg_{side}"),
                    (f"LegIK_{side}", f"Leg_{side}"),
                    (f"KneeIK_{side}", f"Knee_{side}"),
                    (f"AnkleIK_{side}", f"Ankle_{side}"),
                    (f"FootIK_{side}", f"Ankle_{side}"),
                    (f"ToeTipIK_{side}", f"ToeTip_{side}"),
                    (f"ToeIK_{side}", f"ToeTip_{side}"),
                ):
                    if self._bone_exists(arm, src) and self._bone_exists(arm, dst):
                        merges.append((src, dst))

        total = 0
        for src, dst in merges:
            if self.report_only:
                if self.log_actions:
                    log_bone_operation(context, "QuickMerge-Preview", f"{src} -> {dst} on {arm.name}")
                continue
            self._merge_one(context, arm, meshes, src, dst)
            total += 1

        self.report({'INFO'}, f"快速合并完成：{total} 项")
        return {'FINISHED'}

class BONE_OT_unlock_all_transforms(Operator):
    bl_idname = "bone.unlock_all_transforms"
    bl_label = "解锁骨骼变换锁定"
    bl_description = "快速解锁所有骨骼的移动/旋转/缩放锁定"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 面板处已根据是否选中骨架限制启用，这里保持宽松
        return True

    def execute(self, context):
        arm = context.object if context.object and context.object.type == 'ARMATURE' else None
        if arm is None:
            for o in bpy.data.objects:
                if o.type == 'ARMATURE':
                    arm = o
                    break
        if arm is None:
            self.report({'ERROR'}, "未找到骨架")
            return {'CANCELLED'}
        bpy.context.view_layer.objects.active = arm
        try:
            prev_mode = arm.mode
        except Exception:
            prev_mode = 'OBJECT'
        bpy.ops.object.mode_set(mode='POSE')
        count = 0
        for pb in arm.pose.bones:
            try:
                pb.lock_location = (False, False, False)
                pb.lock_rotation = (False, False, False)
                pb.lock_scale = (False, False, False)
                if hasattr(pb, "lock_rotations_4d"):
                    pb.lock_rotations_4d = False
                if hasattr(pb, "lock_rotation_w"):
                    pb.lock_rotation_w = False
                count += 1
            except Exception:
                pass
        bpy.ops.object.mode_set(mode=prev_mode)
        self.report({'INFO'}, f"已解锁 {count} 个骨骼的移动/旋转/缩放")
        return {'FINISHED'}

# 主体骨骼重命名设置
class RenamePrimarySettings(PropertyGroup):
    preset: EnumProperty(
        name="预设",
        description="选择重命名预设",
        items=[
            ('StandardRename', 'Standard', ''),
            ('WutheringWaves', 'WutheringWaves', ''),
            ('Snowbreak', 'Snowbreak', ''),
            ('GF2', 'GF2', ''),
            ('UMA', 'UMA', ''),
            ('Sio', 'Sio', ''),
            ('idol', 'idol', ''),
            ('Chunli', 'Chunli', ''),
        ],
        default='StandardRename'
    )
    file_path: StringProperty(
        name="映射文件",
        description="重命名映射的INI文件路径",
        default="d:\\功能移植\\RenamePresets.ini",
        subtype='FILE_PATH'
    )
    case_sensitive: BoolProperty(
        name="区分大小写",
        description="匹配骨骼与顶点组时区分大小写",
        default=False
    )
    merge_vertex_groups: BoolProperty(
        name="同步顶点组",
        description="将网格顶点组同步到新的骨骼名称（合并或重命名）",
        default=True
    )

class BONE_OT_rename_primary_bones(Operator):
    bl_idname = "bone.rename_primary_bones"
    bl_label = "主体骨骼一键重命名"
    bl_description = "根据预设映射重命名主体骨骼，并同步网格顶点组"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def _get_armature(self, context):
        arm = context.object if context.object and context.object.type == 'ARMATURE' else None
        if arm is None:
            for o in bpy.data.objects:
                if o.type == 'ARMATURE':
                    return o
        return arm

    def _get_meshes_for_armature(self, arm):
        meshes = []
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for m in obj.modifiers:
                if m.type == 'ARMATURE' and m.object == arm:
                    meshes.append(obj)
                    break
        return meshes

    def _find_name_case_insensitive(self, candidates, name):
        name_lower = name.lower()
        for c in candidates:
            if c.name.lower() == name_lower:
                return c
        return None

    def execute(self, context):
        import re
        # 一键硬编码重命名（不读取任何外部文件）
        case_sensitive = False
        merge_vertex_groups = True

        arm = self._get_armature(context)
        if arm is None:
            self.report({'ERROR'}, "未找到骨架")
            return {'CANCELLED'}
        meshes = self._get_meshes_for_armature(arm)

        # 统一骨架对象与数据名称
        try:
            old_obj_name = arm.name
            old_data_name = arm.data.name if arm.data else ""
            arm.name = "Armature"
            if arm.data:
                arm.data.name = "Armature"
            try:
                log_bone_operation(context, "RenameArmature", f"{old_obj_name}/{old_data_name} -> Armature on {arm.name}")
            except Exception:
                pass
        except Exception as e:
            self.report({'WARNING'}, f"重命名骨架到 Armature 失败: {str(e)}")

        # 硬编码主体骨映射（覆盖从脚趾到手指所有部分）
        pairs = [
            # 参考自 StandardRename 的标准目标名称
            ("Shoulder_R","Right shoulder"),("RightShoulder","Right shoulder"),("UpperArm_R","Right arm"),("RightUpperArm","Right arm"),("LowerArm_R","Right_elbow"),("RightLowerArm","Right_elbow"),("RightHand","Right wrist"),("Hand_R","Right wrist"),("RightUpperLeg","Right leg"),("UpperLeg_R","Right leg"),("RightLowerLeg","Right knee"),("LowerLeg_R","Right knee"),("RightFoot","Right_ankle"),("Foot_R","Right_ankle"),("RightToeBase","Right toe"),("Toe_R","Right toe"),
            ("IndexProximal_R","IndexFinger1_R"),("RightIndexProximal","IndexFinger1_R"),("IndexIntermediate_R","IndexFinger2_R"),("RightIndexIntermediate","IndexFinger2_R"),("IndexDistal_R","IndexFinger3_R"),("RightIndexDistal","IndexFinger3_R"),
            ("LittleProximal_R","LittleFinger1_R"),("RightLittleProximal","LittleFinger1_R"),("LittleIntermediate_R","LittleFinger2_R"),("RightLittleIntermediate","LittleFinger2_R"),("LittleDistal_R","LittleFinger3_R"),("RightLittleDistal","LittleFinger3_R"),
            ("MiddleProximal_R","MiddleFinger1_R"),("RightMiddleProximal","MiddleFinger1_R"),("MiddleIntermediate_R","MiddleFinger2_R"),("RightMiddleIntermediate","MiddleFinger2_R"),("MiddleDistal_R","MiddleFinger3_R"),("RightMiddleDistal","MiddleFinger3_R"),
            ("RingProximal_R","RingFinger1_R"),("RightRingProximal","RingFinger1_R"),("RingIntermediate_R","RingFinger2_R"),("RightRingIntermediate","RingFinger2_R"),("RingDistal_R","RingFinger3_R"),("RightRingDistal","RingFinger3_R"),
            ("ThumbProximal_R","Thumb0_R"),("RightThumbProximal","Thumb0_R"),("ThumbIntermediate_R","Thumb1_R"),("RightThumbIntermediate","Thumb1_R"),("ThumbDistal_R","Thumb2_R"),("RightThumbDistal","Thumb2_R"),
            ("Shoulder_L","Left shoulder"),("LeftShoulder","Left shoulder"),("UpperArm_L","Left arm"),("LeftUpperArm","Left arm"),("LowerArm_L","Left_elbow"),("LeftLowerArm","Left_elbow"),("LeftHand","Left wrist"),("Hand_L","Left wrist"),("LeftUpperLeg","Left leg"),("UpperLeg_L","Left leg"),("LeftLowerLeg","Left knee"),("LowerLeg_L","Left knee"),("LeftFoot","Left_ankle"),("Foot_L","Left_ankle"),("LeftToeBase","Left toe"),("Toe_L","Left toe"),
            ("IndexProximal_L","IndexFinger1_L"),("LeftIndexProximal","IndexFinger1_L"),("IndexIntermediate_L","IndexFinger2_L"),("LeftIndexIntermediate","IndexFinger2_L"),("IndexDistal_L","IndexFinger3_L"),("LeftIndexDistal","IndexFinger3_L"),
            ("LittleProximal_L","LittleFinger1_L"),("LeftLittleProximal","LittleFinger1_L"),("LittleIntermediate_L","LittleFinger2_L"),("LeftLittleIntermediate","LittleFinger2_L"),("LittleDistal_L","LittleFinger3_L"),("LeftLittleDistal","LittleFinger3_L"),
            ("MiddleProximal_L","MiddleFinger1_L"),("LeftMiddleProximal","MiddleFinger1_L"),("MiddleIntermediate_L","MiddleFinger2_L"),("LeftMiddleIntermediate","MiddleFinger2_L"),("MiddleDistal_L","MiddleFinger3_L"),("LeftMiddleDistal","MiddleFinger3_L"),
            ("RingProximal_L","RingFinger1_L"),("LeftRingProximal","RingFinger1_L"),("RingIntermediate_L","RingFinger2_L"),("LeftRingIntermediate","RingFinger2_L"),("RingDistal_L","RingFinger3_L"),("LeftRingDistal","RingFinger3_L"),
            ("ThumbProximal_L","Thumb0_L"),("LeftThumbProximal","Thumb0_L"),("ThumbIntermediate_L","Thumb1_L"),("LeftThumbIntermediate","Thumb1_L"),("ThumbDistal_L","Thumb2_L"),("LeftThumbDistal","Thumb2_L"),
            ("Hips","Hips"),("Spine","Spine"),("Chest","Chest"),("Neck","Neck"),("Head","Head"),

            # 结合骨骼日志中的 MMD 命名（主体肢体）
            ("Shoulder_L","Left shoulder"),("Shoulder_R","Right shoulder"),
            ("Arm_L","Left arm"),("Arm_R","Right arm"),
            ("Elbow_L","Left_elbow"),("Elbow_R","Right_elbow"),
            ("Wrist_L","Left wrist"),("Wrist_R","Right wrist"),
            ("Leg_L","Left leg"),("Leg_R","Right leg"),
            ("Knee_L","Left knee"),("Knee_R","Right knee"),
            ("Ankle_L","Left_ankle"),("Ankle_R","Right_ankle"),
            ("ToeTip_L","Left toe"),("ToeTip_R","Right toe"),

            # 常见主体节点：按你的要求调整
            ("Waist","Hips"),
            ("UpperBody","Spine"),("Upperbody","Spine"),
            ("UpperBody2","Spine2"),("Upperbody2","Spine2"),("Upperboody2","Spine2"),
            ("UpperBody3","Chest"),("Upperbody3","Chest"),
        ]

        # 统一大小写匹配
        current_names = {pb.name for pb in arm.pose.bones}
        rename_count = 0
        miss_bones = 0
        mapped_old_names = set()

        for old_name, new_name in pairs:
            pb = arm.pose.bones.get(old_name)
            if pb is None and not case_sensitive:
                pb = self._find_name_case_insensitive(arm.pose.bones, old_name)
            if pb is None:
                miss_bones += 1
                continue

            source_name_for_vg = pb.name
            mapped_old_names.add(old_name)

            if pb.name != new_name:
                try:
                    pb.name = new_name
                except Exception as e:
                    self.report({'WARNING'}, f"重命名骨骼 {old_name} -> {new_name} 失败: {str(e)}")
                    continue

            if merge_vertex_groups:
                for obj in meshes:
                    vg_old = obj.vertex_groups.get(source_name_for_vg)
                    if vg_old is None and not case_sensitive:
                        for vg in obj.vertex_groups:
                            if vg.name.lower() == source_name_for_vg.lower():
                                vg_old = vg
                                break
                    if vg_old is None:
                        continue

                    # 如果目标名与源名一致，跳过同步，避免误删顶点组
                    if new_name == source_name_for_vg:
                        continue

                    vg_new = obj.vertex_groups.get(new_name)
                    if vg_new is None:
                        try:
                            vg_old.name = new_name
                            # 重命名成功，无需新建或移除
                            continue
                        except Exception:
                            vg_new = obj.vertex_groups.new(name=new_name)
                            for v in obj.data.vertices:
                                try:
                                    w = vg_old.weight(v.index)
                                except RuntimeError:
                                    w = 0.0
                                if w > 0.0:
                                    vg_new.add([v.index], w, 'REPLACE')
                            obj.vertex_groups.remove(vg_old)
                    else:
                        # 已存在不同名称的目标组，合并权重后移除旧组
                        if vg_new is vg_old:
                            # 同一个组（保护性判断），无需处理
                            continue
                        for v in obj.data.vertices:
                            try:
                                w_old = vg_old.weight(v.index)
                            except RuntimeError:
                                w_old = 0.0
                            if w_old > 0.0:
                                try:
                                    w_new = vg_new.weight(v.index)
                                except RuntimeError:
                                    w_new = 0.0
                                w_final = min(1.0, w_new + w_old)
                                vg_new.add([v.index], w_final, 'REPLACE')
                        obj.vertex_groups.remove(vg_old)

            rename_count += 1
            try:
                log_bone_operation(context, "Rename", f"{old_name} -> {new_name} on {arm.name} [Hardcoded]")
            except Exception:
                pass

        # 检测主体骨中可能缺失的映射（关键词），排除应在合并阶段处理的节点
        major_keywords = re.compile(r"(shoulder|upperarm|lowerarm|arm|elbow|hand|wrist|thigh|calf|leg|knee|foot|ankle|toe|hips|pelvis|waist|upperbody|spine|chest|neck|head)", re.I)
        ignore_primary_names = {"center","groove","lowerbody"}
        unknown_primary_bones = [n for n in current_names if major_keywords.search(n) and n.lower() not in ignore_primary_names and n not in mapped_old_names]
        if unknown_primary_bones:
            try:
                log_bone_operation(context, "MissingMapping", f"未覆盖主体骨: {', '.join(sorted(unknown_primary_bones))}")
            except Exception:
                pass
            preview_list = ", ".join(sorted(unknown_primary_bones[:8]))
            self.report({'WARNING'}, f"存在未在硬编码映射覆盖的主体骨：{preview_list} …")

        self.report({'INFO'}, f"重命名完成：{rename_count} 成功, {miss_bones} 未找到；使用硬编码 MMD 映射")
        return {'FINISHED'}

class MQT_PT_BoneToolsPanel(Panel):
    bl_label = "骨骼工具"
    bl_idname = "MQT_PT_BoneToolsPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 基本合并功能
        box = layout.box()
        box.label(text="基本合并")
        
        row = box.row()
        row.operator("bone.merge_to_parent", text="合并到父级")
        
        row = box.row()
        row.operator("bone.merge_to_active", text="合并到活动骨骼")
        
        # 高级合并功能
        box = layout.box()
        box.label(text="高级合并")
        
        row = box.row()
        row.operator("bone.merge_siblings_half", text="左右对称合并")
        
        # MMD 快速合并
        box2 = layout.box()
        box2.label(text="MMD 快速合并")
        row = box2.row()
        row.operator("bone.mmd_quick_merge", text="执行快速合并")
        
        # 预处理工具
        box = layout.box()
        box.label(text="预处理工具")
        
        row = box.row()
        # 使用修改后的 bl_idname
        row.operator("object.gfl2_preprocess", text="少前2模型一键预处理") # 按钮文本可以保持不变或同步修改
        
        # 清理工具
        box = layout.box()
        box.label(text="清理工具")
        
        row = box.row()
        row.operator("bone.remove_zero_weight", text="清除零权重骨骼")
        
        row = box.row()
        row.operator("object.remove_rigidbodies_joints", text="移除刚体与关节")
        
        row = box.row()
        row.operator("bone.remove_constraints", text="移除骨骼约束")
        
        # 变换工具
        box = layout.box()
        box.label(text="变换工具")
        
        row = box.row()
        row.operator("bone.apply_pose_transform", text="应用姿态变换")
        row = box.row()
        row.operator("bone.unlock_all_transforms", text="解锁所有骨骼移动/旋转/缩放")

        # 命名工具
        box = layout.box()
        box.label(text="命名工具")
        row = box.row()
        row.operator("bone.rename_primary_bones", text="主体骨骼一键重命名")
        
        # 检查是否选择了骨架来启用按钮（而不是检查模式）
        armature_selected = bool(context.active_object and context.active_object.type == 'ARMATURE')
        layout.enabled = armature_selected

# --------------------------------------------------------------------------
# 工具 6: 顶点组合并工具
# --------------------------------------------------------------------------

class VertexGroupSelectItem(PropertyGroup):
    """顶点组选择项属性组"""
    name: StringProperty(name="组名")
    selected: BoolProperty(name="选择", default=False)

class VERTEX_OT_MergeVertexGroups(Operator):
    """合并选中的顶点组"""
    bl_idname = "vertex.merge_vertex_groups"
    bl_label = "合并顶点组"
    bl_description = "将选中的顶点组合并为一个新的顶点组"
    bl_options = {'REGISTER', 'UNDO'}
    
    target_group_name: StringProperty(
        name="目标组名称",
        description="合并后的顶点组名称",
        default="MergedGroup"
    )
    
    merge_mode: EnumProperty(
        name="合并模式",
        description="选择权重合并的方式",
        items=[
            ('ADD', '权重相加', '将所有选中组的权重相加'),
            ('AVERAGE', '权重平均', '计算所有选中组的权重平均值'),
            ('MAX', '最大权重', '取所有选中组中的最大权重值'),
        ],
        default='ADD'
    )
    
    remove_source_groups: BoolProperty(
        name="删除源顶点组",
        description="合并后删除原始的顶点组",
        default=True
    )
    
    normalize_weights: BoolProperty(
        name="规格化权重",
        description="合并后自动规格化所有权重",
        default=True
    )
    
    # 顶点组选择列表
    selected_groups: CollectionProperty(
        type=VertexGroupSelectItem,
        name="选中的顶点组"
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                len(context.active_object.vertex_groups) >= 2)
    
    def invoke(self, context, event):
        # 清空之前的选择
        self.selected_groups.clear()
        
        # 为每个顶点组创建选择项
        obj = context.active_object
        for vg in obj.vertex_groups:
            item = self.selected_groups.add()
            item.name = vg.name
            item.selected = False
        
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        vertex_groups = obj.vertex_groups
        
        # 获取选中的顶点组
        selected_group_names = []
        for item in self.selected_groups:
            if item.selected:
                selected_group_names.append(item.name)
        
        if len(selected_group_names) < 2:
            self.report({'ERROR'}, "请至少选择2个顶点组进行合并")
            return {'CANCELLED'}
        
        # 获取实际的顶点组对象
        selected_groups = []
        for name in selected_group_names:
            group = obj.vertex_groups.get(name)
            if group:
                selected_groups.append(group)
        
        # 确保目标组名称不为空
        if not self.target_group_name.strip():
            self.target_group_name = "MergedGroup"
        
        # 创建目标顶点组
        target_group = vertex_groups.new(name=self.target_group_name)
        
        # 收集所有顶点的权重数据
        vertex_weights = {}
        
        for vertex in mesh.vertices:
            vertex_index = vertex.index
            weights_for_vertex = []
            
            # 收集该顶点在所有选中组中的权重
            for group in selected_groups:
                try:
                    weight = group.weight(vertex_index)
                    weights_for_vertex.append(weight)
                except RuntimeError:
                    weights_for_vertex.append(0.0)
            
            # 根据合并模式计算最终权重
            if weights_for_vertex:
                if self.merge_mode == 'ADD':
                    final_weight = sum(weights_for_vertex)
                elif self.merge_mode == 'AVERAGE':
                    final_weight = sum(weights_for_vertex) / len(weights_for_vertex)
                elif self.merge_mode == 'MAX':
                    final_weight = max(weights_for_vertex)
                else:
                    final_weight = sum(weights_for_vertex)
                
                # 限制权重在0-1范围内
                final_weight = max(0.0, min(1.0, final_weight))
                
                if final_weight > 0.0:
                    vertex_weights[vertex_index] = final_weight
        
        # 将计算出的权重分配给目标组
        for vertex_index, weight in vertex_weights.items():
            target_group.add([vertex_index], weight, 'REPLACE')
        
        # 删除源顶点组（如果选择了删除）
        if self.remove_source_groups:
            for group in selected_groups:
                vertex_groups.remove(group)
        
        # 规格化权重（如果选择了规格化）
        if self.normalize_weights:
            try:
                # 进入编辑模式进行规格化
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.object.vertex_group_normalize_all(lock_active=False)
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception as e:
                self.report({'WARNING'}, f"权重规格化失败: {str(e)}")
                # 确保返回物体模式
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass
        
        merged_count = len(selected_groups)
        self.report({'INFO'}, f"成功合并了 {merged_count} 个顶点组到 '{self.target_group_name}'")
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        
        layout.prop(self, "target_group_name")
        layout.prop(self, "merge_mode")
        layout.prop(self, "remove_source_groups")
        layout.prop(self, "normalize_weights")
        
        # 顶点组选择界面
        box = layout.box()
        box.label(text="选择要合并的顶点组:", icon='GROUP_VERTEX')
        
        # 显示顶点组选择列表
        for item in self.selected_groups:
            row = box.row()
            row.prop(item, "selected", text="")
            row.label(text=item.name)
        
        # 提示信息
        if len([item for item in self.selected_groups if item.selected]) < 2:
            box.label(text="请至少选择2个顶点组", icon='ERROR')

class MQT_PT_VertexGroupPanel(Panel):
    bl_label = "顶点组工具"
    bl_idname = "MQT_PT_VertexGroupPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 顶点组合并工具
        box = layout.box()
        box.label(text="顶点组合并工具:", icon='GROUP_VERTEX')
        
        # 功能说明
        tips_box = box.box()
        tips_box.label(text="使用说明:", icon='INFO')
        tips_box.label(text="• 选择网格对象后点击合并顶点组")
        tips_box.label(text="• 支持多种合并模式（相加/平均/最大值）")
        tips_box.label(text="• 可选择是否删除源顶点组")
        tips_box.label(text="• 自动规格化权重选项")
        
        # 合并按钮
        row = box.row()
        row.operator(VERTEX_OT_MergeVertexGroups.bl_idname, 
                    text="合并顶点组", 
                    icon='GROUP_VERTEX')
        
        # 检查是否选择了网格对象来启用按钮
        mesh_selected = bool(context.active_object and 
                           context.active_object.type == 'MESH' and
                           len(context.active_object.vertex_groups) >= 2)
        
        if not mesh_selected:
            if not context.active_object:
                box.label(text="请选择一个对象", icon='ERROR')
            elif context.active_object.type != 'MESH':
                box.label(text="请选择网格对象", icon='ERROR')
            elif len(context.active_object.vertex_groups) < 2:
                box.label(text="需要至少2个顶点组", icon='ERROR')

# --------------------------------------------------------------------------
# 工具 7: 一键PBR材质着色工具
# --------------------------------------------------------------------------

# --- Helper Functions for PBR Tool ---

def _find_texture_path(base_dir, output_dir, texture_filename):
    """查找纹理文件的绝对路径"""
    potential_paths = []
    # 优先在输出目录查找（如果指定）
    if output_dir:
        potential_paths.append(os.path.join(output_dir, os.path.basename(texture_filename)))
        potential_paths.append(os.path.join(output_dir, texture_filename)) # In case filename includes relative path parts
    # 在源目录查找
    potential_paths.append(os.path.join(base_dir, os.path.basename(texture_filename)))
    potential_paths.append(os.path.join(base_dir, texture_filename))
    # 直接使用文件名（可能是绝对路径）
    potential_paths.append(texture_filename)

    for p in potential_paths:
        if p and os.path.isfile(p):
            return os.path.normpath(p)
    print(f"警告: 无法找到贴图文件 '{texture_filename}' 在 {base_dir} 或 {output_dir}")
    return None # Corrected indentation

def _cleanup_material_nodes(nodes, links, remove_normal_nodes=False):
    """清理材质节点树，保留Output节点和现有的Normal Map设置
    
    Args:
        nodes: 材质节点树的节点集合
        links: 材质节点树的连接集合
        remove_normal_nodes: 是否删除法向相关节点（Normal Map和_n贴图）
    """
    print(f"  - 开始清理节点 (当前 {len(nodes)} 个)...")
    if remove_normal_nodes:
        print(f"  - BASE_ALPHA模式: 将删除法向相关节点")
    output_node = None
    principled_bsdf_node = None # Find the BSDF connected to output
    normal_map_node = None
    normal_texture_node = None
    nodes_to_remove = []

    # Find the Material Output node first
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
            break # Assume only one output node

    # Find the BSDF connected to the output and check its Normal input
    if output_node and output_node.inputs["Surface"].links:
        link = output_node.inputs["Surface"].links[0]
        if link.from_node.type == 'BSDF_PRINCIPLED':
            principled_bsdf_node = link.from_node
            print(f"    - 找到连接到输出的 Principled BSDF: {principled_bsdf_node.name}")
            # Check Normal input of this existing BSDF
            normal_input = principled_bsdf_node.inputs.get("Normal")
            if normal_input and normal_input.links:
                normal_link = normal_input.links[0]
                if normal_link.from_node.type == 'NORMAL_MAP':
                    normal_map_node = normal_link.from_node
                    print(f"    - 找到连接到法线的 Normal Map 节点: {normal_map_node.name}")
                    # Check the Color input of the Normal Map node
                    color_input = normal_map_node.inputs.get("Color")
                    if color_input and color_input.links:
                        texture_link = color_input.links[0]
                        if texture_link.from_node.type == 'TEX_IMAGE':
                            normal_texture_node = texture_link.from_node
                            print(f"    - 找到连接到 Normal Map 的 Image Texture: {normal_texture_node.name}")

    # 在BASE_ALPHA模式下，强制删除法向相关节点
    if remove_normal_nodes:
        if normal_map_node:
            print(f"    - BASE_ALPHA模式: 强制删除Normal Map节点: {normal_map_node.name}")
            normal_map_node = None
        if normal_texture_node:
            print(f"    - BASE_ALPHA模式: 强制删除法向贴图节点: {normal_texture_node.name}")
            normal_texture_node = None
        
        # 删除所有_n后缀的图像纹理节点
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                image_name = node.image.name.lower()
                if '_n.' in image_name or image_name.endswith('_n'):
                    print(f"    - BASE_ALPHA模式: 删除_n后缀贴图节点: {node.name} (图像: {node.image.name})")
                    nodes_to_remove.append(node)

    # Identify nodes to remove
    preserved_nodes = {output_node, principled_bsdf_node, normal_map_node, normal_texture_node}
    for node in nodes:
        if node not in preserved_nodes and node is not None: # Check for None just in case
            nodes_to_remove.append(node)
        elif node == output_node and output_node:
             # Clean input links of the output node EXCEPT the BSDF link if preserved
            for input_socket in node.inputs:
                 if input_socket.name == "Surface" and principled_bsdf_node: continue # Keep BSDF link
                 if input_socket.links:
                     for link in list(input_socket.links):
                         print(f"    - 清理输出连接: {link.from_node.name}.{link.from_socket.name} -> {node.name}.{input_socket.name}")
                         links.remove(link)
        elif node == principled_bsdf_node and principled_bsdf_node:
            # Clean inputs of preserved BSDF EXCEPT the normal link if preserved
            for input_socket in node.inputs:
                 if input_socket.name == "Normal" and normal_map_node: continue # Keep normal link
                 if input_socket.links:
                     for link in list(input_socket.links):
                          print(f"    - 清理保留的BSDF输入连接: {link.from_node.name}.{link.from_socket.name} -> {node.name}.{input_socket.name}")
                          links.remove(link)
        elif node == normal_map_node and normal_map_node:
             # Clean inputs of preserved Normal Map EXCEPT the texture link if preserved
             for input_socket in node.inputs:
                  if input_socket.name == "Color" and normal_texture_node: continue # Keep texture link
                  if input_socket.links:
                      for link in list(input_socket.links):
                           print(f"    - 清理保留的NormalMap输入连接: {link.from_node.name}.{link.from_socket.name} -> {node.name}.{input_socket.name}")
                           links.remove(link)


    removed_count = 0
    if nodes_to_remove:
        print(f"    - 准备删除 {len(nodes_to_remove)} 个旧节点...")
        for node in nodes_to_remove:
            # Ensure node still exists before removing (might have been removed as part of another node's tree)
            if node.name in nodes:
                print(f"      - 删除: {node.name} ({node.type})")
                try:
                    nodes.remove(node)
                    removed_count += 1
                except Exception as remove_err:
                    print(f"      - 删除节点 {node.name} 时出错: {remove_err}")
            else:
                print(f"      - 跳过删除: {node.name} (已不存在)")

    print(f"  - 节点清理完成，删除了 {removed_count} 个。")
    # Return the nodes that were preserved (or None if not found)
    return output_node, principled_bsdf_node, normal_map_node, normal_texture_node

def _create_base_nodes(nodes, links, existing_output, existing_bsdf, existing_normal_map, existing_normal_texture):
    """创建或复用Principled BSDF和Output，并重新连接法线贴图（如果存在）"""
    output_node = existing_output
    if not output_node:
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        # Adjusted location
        output_node.location = (500, 300)
        print(f"  - 创建了新输出节点: {output_node.name}")

    principled_node = existing_bsdf
    if not principled_node:
        principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        # Adjusted location
        principled_node.location = (100, 300)
        print(f"  - 创建了新 Principled BSDF: {principled_node.name}")
        # Connect new BSDF to output if BSDF was newly created
        if output_node.inputs["Surface"].links:
             for link in list(output_node.inputs["Surface"].links): links.remove(link) # Clean first
        links.new(principled_node.outputs["BSDF"], output_node.inputs["Surface"])
        print(f"  - 连接了新 {principled_node.name}.BSDF -> {output_node.name}.Surface")
    else:
         # Ensure the preserved BSDF is still connected to output
         is_connected = False
         if output_node.inputs["Surface"].links:
              if output_node.inputs["Surface"].links[0].from_node == principled_node:
                   is_connected = True
         if not is_connected:
              print(f"  - 重新连接保留的BSDF {principled_node.name} 到输出 {output_node.name}")
              if output_node.inputs["Surface"].links: # Clean if wrongly connected
                  for link in list(output_node.inputs["Surface"].links): links.remove(link)
              links.new(principled_node.outputs["BSDF"], output_node.inputs["Surface"])

    # Reconnect preserved normal map setup if it exists
    if principled_node and existing_normal_map and existing_normal_texture:
        normal_input = principled_node.inputs.get("Normal")
        if normal_input:
            is_normal_connected = False
            if normal_input.links:
                if normal_input.links[0].from_node == existing_normal_map:
                    is_normal_connected = True

            if not is_normal_connected:
                print(f"  - 重新连接保留的法线贴图设置: {existing_normal_texture.name} -> {existing_normal_map.name} -> {principled_node.name}.Normal")
                # Ensure Normal Map color input is linked correctly
                color_input = existing_normal_map.inputs.get("Color")
                if color_input:
                    is_tex_connected = False
                    if color_input.links:
                        if color_input.links[0].from_node == existing_normal_texture:
                             is_tex_connected = True
                    if not is_tex_connected:
                        if color_input.links: # Clean wrong links
                             for link in list(color_input.links): links.remove(link)
                        links.new(existing_normal_texture.outputs["Color"], color_input)
                else: print(f"    - 警告: 保留的 Normal Map 节点 {existing_normal_map.name} 没有 Color 输入?")

                # Link Normal Map output to BSDF Normal input
                if normal_input.links: # Clean wrong links
                    for link in list(normal_input.links): links.remove(link)
                links.new(existing_normal_map.outputs["Normal"], normal_input)
            else:
                 print(f"  - 保留的法线贴图设置已连接。")
        else:
            print(f"  - 警告: 保留的 Principled BSDF {principled_node.name} 没有 Normal 输入?")
    elif existing_normal_map or existing_normal_texture:
         print(f"  - 警告: 法线贴图设置不完整，无法重新连接 (NormalMap: {existing_normal_map}, Texture: {existing_normal_texture})")


    return principled_node, output_node


def _load_texture_node(nodes, texture_path, node_name_prefix, material_name, is_rmo=False):
    """加载纹理到图像节点，使用材质名称重命名数据块，返回图像节点。"""
    # REMOVED: force_unique_datablock parameter and its logic
    logger = logging.getLogger('pbr_materials')

    if not texture_path or not os.path.exists(texture_path):
        # Now log error instead of print
        logger.error(f"错误: 贴图路径无效或文件不存在: {texture_path}")
        return None

    tex_node = nodes.new(type='ShaderNodeTexImage')
    # Use a more robust unique name for the node itself
    unique_node_suffix = str(uuid.uuid4())[:8]
    node_name = f"{node_name_prefix}_{('RMO' if is_rmo else 'Diffuse')}_{unique_node_suffix}"
    tex_node.name = node_name
    tex_node.label = os.path.basename(texture_path) # Set label for readability
    # Adjusted locations for more spacing
    tex_node.location = (-800, 100) if is_rmo else (-800, 500)
    logger.info(f"  - 创建图像节点: {node_name}")

    loaded_image = None
    try:
        # Always use check_existing=True now, let Blender handle sharing based on filepath
        logger.info(f"  - 尝试加载/复用图像: '{os.path.basename(texture_path)}' (check_existing=True)")
        loaded_image = bpy.data.images.load(texture_path, check_existing=True)
        if loaded_image:
            logger.info(f"    - 加载/复用图像成功: Name='{loaded_image.name}', ID={id(loaded_image)}, Path='{loaded_image.filepath}'")
            # --- Rename Data Block Here --- 
            # Check if the loaded image name is already the desired material name
            if loaded_image.name != material_name:
                # Check if the target name already exists
                if material_name in bpy.data.images:
                    logger.warning(f"    - 目标图像数据块名称 '{material_name}' 已存在。将尝试复用现有块。")
                    # If the existing block with the target name points to the SAME file, reuse it
                    existing_image = bpy.data.images[material_name]
                    if existing_image.filepath == loaded_image.filepath:
                        logger.info(f"      - 复用名称为 '{material_name}' 且路径相同的现有数据块。")
                        # If the initially loaded image has no other users, remove it
                        if loaded_image.users <= 1 and loaded_image.name != material_name: # Check users of initially loaded block
                           try:
                                bpy.data.images.remove(loaded_image)
                                logger.info(f"        - 移除了初始加载的、未使用的块 '{loaded_image.name}'")
                           except Exception as remove_err:
                                logger.warning(f"        - 移除初始加载块 '{loaded_image.name}' 时出错: {remove_err}")
                        loaded_image = existing_image # Point to the correctly named existing block
                    else:
                        # Name collision with different file path - append UUID to avoid issues
                        logger.warning(f"      - 名称 '{material_name}' 已被用于不同文件 ('{existing_image.filepath}')。将添加UUID后缀。")
                        unique_mat_name = f"{material_name}_{str(uuid.uuid4())[:4]}"
                        loaded_image.name = unique_mat_name
                        logger.info(f"    - 重命名图像数据块为: '{unique_mat_name}'")
                else:
                    # Target name doesn't exist, safe to rename
                    loaded_image.name = material_name
                    logger.info(f"    - 重命名图像数据块为: '{material_name}'")
            else:
                 logger.info(f"    - 图像数据块名称 '{loaded_image.name}' 已是目标名称 '{material_name}'")

            # Ensure filepath is correct (important if reusing existing block)
            if loaded_image.filepath != texture_path:
                logger.warning(f"    - 修正图像数据块 '{loaded_image.name}' 的文件路径: '{loaded_image.filepath}' -> '{texture_path}'")
                loaded_image.filepath = texture_path
                loaded_image.reload() # Reload to ensure consistency
        else:
            logger.error(f"    - 错误: 加载图像 '{os.path.basename(texture_path)}' 失败")

    except Exception as load_err:
        logger.error(f"错误: 加载或处理图像 '{os.path.basename(texture_path)}' 失败: {load_err}", exc_info=True)
        if tex_node in nodes: nodes.remove(tex_node) # Clean up failed node
        return None

    if loaded_image:
        tex_node.image = loaded_image
        # Set color space AFTER assigning image
        tex_node.image.colorspace_settings.name = 'Non-Color' if is_rmo else 'sRGB'
        logger.info(f"    - 设置色彩空间 for '{loaded_image.name}': {'Non-Color' if is_rmo else 'sRGB'}")
        return tex_node
    else:
        logger.error(f"错误: 最终图像对象为空: {texture_path}")
        if tex_node in nodes: nodes.remove(tex_node)
        return None


def _link_textures_to_principled(nodes, links, principled_node, diffuse_tex, rmo_tex):
    """将纹理节点连接到Principled BSDF"""
    # Check if principled_node is valid
    if not principled_node:
        logger = logging.getLogger('pbr_materials')
        logger.error("_link_textures_to_principled: 无效的 Principled BSDF 节点提供")
        return

    logger = logging.getLogger('pbr_materials') # Get logger instance

    if diffuse_tex and rmo_tex:
        logger.info(f"  - 连接 Diffuse ({diffuse_tex.name}) 和 RMO ({rmo_tex.name})")
        # --- RMO Path ---
        print(f"    - RMO 节点: {rmo_tex.name}, 图像: {rmo_tex.image.name if rmo_tex.image else '无'}, 颜色空间: {rmo_tex.image.colorspace_settings.name if rmo_tex.image else 'N/A'}")
        if rmo_tex.image and rmo_tex.image.colorspace_settings.name != 'Non-Color':
            print(f"    - 警告: RMO 贴图 '{rmo_tex.image.name}' 的颜色空间不是 Non-Color, 应修正。")
        
        separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
        # Adjusted location for more spacing
        separate_rgb.location = (-300, 100)
        print(f"    - 创建 Separate RGB 节点: {separate_rgb.name}")
        
        # Ensure RMO output is connected to Separate RGB input
        if separate_rgb.inputs["Image"].links: # Clean first
             for link in list(separate_rgb.inputs["Image"].links): links.remove(link)
        links.new(rmo_tex.outputs["Color"], separate_rgb.inputs["Image"])
        print(f"    - 连接: {rmo_tex.name}.Color -> {separate_rgb.name}.Image")

        # Connect R, G to Roughness, Metallic
        if principled_node.inputs["Roughness"].links:
             for link in list(principled_node.inputs["Roughness"].links): links.remove(link)
        links.new(separate_rgb.outputs["R"], principled_node.inputs["Roughness"])
        print(f"    - 连接: {separate_rgb.name}.R -> {principled_node.name}.Roughness")
        
        if principled_node.inputs["Metallic"].links:
             for link in list(principled_node.inputs["Metallic"].links): links.remove(link)
        links.new(separate_rgb.outputs["G"], principled_node.inputs["Metallic"])
        print(f"    - 连接: {separate_rgb.name}.G -> {principled_node.name}.Metallic")

        # --- Diffuse + AO Path ---
        print(f"    - Diffuse 节点: {diffuse_tex.name}, 图像: {diffuse_tex.image.name if diffuse_tex.image else '无'}, 颜色空间: {diffuse_tex.image.colorspace_settings.name if diffuse_tex.image else 'N/A'}")

        multiply_node = nodes.new(type='ShaderNodeMixRGB') # Changed to MixRGB for clarity in UI, still use Multiply
        multiply_node.label = "AO Multiply"
        # Adjusted location for more spacing
        multiply_node.location = (-300, 500)
        multiply_node.blend_type = 'MULTIPLY'
        # Set AO Mix Factor to 0.5
        multiply_node.inputs["Fac"].default_value = 0.5
        print(f"    - 创建 MixRGB (Multiply) 节点: {multiply_node.name}")

        # Connect Diffuse to Color1
        if multiply_node.inputs["Color1"].links:
             for link in list(multiply_node.inputs["Color1"].links): links.remove(link)
        links.new(diffuse_tex.outputs["Color"], multiply_node.inputs["Color1"])
        print(f"    - 连接: {diffuse_tex.name}.Color -> {multiply_node.name}.Color1")

        # Connect AO (Blue channel) to Color2
        if multiply_node.inputs["Color2"].links:
             for link in list(multiply_node.inputs["Color2"].links): links.remove(link)
        links.new(separate_rgb.outputs["B"], multiply_node.inputs["Color2"]) # Assuming B channel is AO
        print(f"    - 连接: {separate_rgb.name}.B (AO) -> {multiply_node.name}.Color2")

        # Connect Mix result to Base Color
        if principled_node.inputs["Base Color"].links:
             for link in list(principled_node.inputs["Base Color"].links): links.remove(link)
        links.new(multiply_node.outputs["Color"], principled_node.inputs["Base Color"])
        print(f"    - 连接: {multiply_node.name}.Color -> {principled_node.name}.Base Color")

    elif diffuse_tex:
        # --- Only Diffuse Path ---
        print(f"  - 仅连接 Diffuse ({diffuse_tex.name})")
        print(f"    - Diffuse 节点: {diffuse_tex.name}, 图像: {diffuse_tex.image.name if diffuse_tex.image else '无'}, 颜色空间: {diffuse_tex.image.colorspace_settings.name if diffuse_tex.image else 'N/A'}")
        if principled_node.inputs["Base Color"].links:
             for link in list(principled_node.inputs["Base Color"].links): links.remove(link)
        links.new(diffuse_tex.outputs["Color"], principled_node.inputs["Base Color"])
        print(f"    - 连接: {diffuse_tex.name}.Color -> {principled_node.name}.Base Color")
        # Ensure Roughness/Metallic are default if no RMO
        principled_node.inputs["Roughness"].default_value = 0.5 # Default roughness
        principled_node.inputs["Metallic"].default_value = 0.0 # Default non-metallic

    elif rmo_tex: # If only RMO, connect Roughness/Metallic but leave Base Color default
         # --- Only RMO Path ---
         print(f"  - 仅连接 RMO ({rmo_tex.name})")
         print(f"    - RMO 节点: {rmo_tex.name}, 图像: {rmo_tex.image.name if rmo_tex.image else '无'}, 颜色空间: {rmo_tex.image.colorspace_settings.name if rmo_tex.image else 'N/A'}")
         if rmo_tex.image and rmo_tex.image.colorspace_settings.name != 'Non-Color':
             print(f"    - 警告: RMO 贴图 '{rmo_tex.image.name}' 的颜色空间不是 Non-Color, 应修正。")
         
         separate_rgb = nodes.new(type='ShaderNodeSeparateRGB')
         separate_rgb.location = (0, 0)
         print(f"    - 创建 Separate RGB 节点: {separate_rgb.name}")

         if separate_rgb.inputs["Image"].links:
              for link in list(separate_rgb.inputs["Image"].links): links.remove(link)
         links.new(rmo_tex.outputs["Color"], separate_rgb.inputs["Image"])
         print(f"    - 连接: {rmo_tex.name}.Color -> {separate_rgb.name}.Image")

         if principled_node.inputs["Roughness"].links:
              for link in list(principled_node.inputs["Roughness"].links): links.remove(link)
         links.new(separate_rgb.outputs["R"], principled_node.inputs["Roughness"])
         print(f"    - 连接: {separate_rgb.name}.R -> {principled_node.name}.Roughness")

         if principled_node.inputs["Metallic"].links:
              for link in list(principled_node.inputs["Metallic"].links): links.remove(link)
         links.new(separate_rgb.outputs["G"], principled_node.inputs["Metallic"])
         print(f"    - 连接: {separate_rgb.name}.G -> {principled_node.name}.Metallic")
         
         # Leave Base Color at default
         # principled_node.inputs["Base Color"].default_value = default color

    else:
        # No textures connected, set defaults
        print("  - 没有纹理节点连接，设置 BSDF 默认值。")
        principled_node.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0) # Default grey
        principled_node.inputs["Roughness"].default_value = 0.5
        principled_node.inputs["Metallic"].default_value = 0.0


def _handle_alpha_channel(mat, links, principled_node, diffuse_tex):
    """处理Alpha通道连接和材质设置 (使用像素检查)"""
    logger = logging.getLogger('pbr_materials') # Get logger instance
    if not principled_node:
        logger.error("_handle_alpha_channel: 无效的 Principled BSDF 节点提供")
        return
    if not mat:
        logger.error("_handle_alpha_channel: 无效的材质提供")
        return

    if not diffuse_tex or not diffuse_tex.image:
        logger.info("  - 无漫反射贴图，跳过Alpha处理")
        # Ensure OPAQUE if no texture
        mat.blend_method = 'OPAQUE'
        mat.shadow_method = 'OPAQUE'
        return

    image = diffuse_tex.image
    logger.info(f"  - 检查 Alpha for Node: {diffuse_tex.name}, Image: {image.name}")
    has_meaningful_alpha = False # Renamed variable for clarity

    # 首先，检查基本条件：必须有4个通道才可能包含Alpha
    if image.channels == 4:
        logger.info(f"    - 图像有 {image.channels} 个通道，开始像素检查...")
        try:
            # 确保像素数据已加载 (如果图像很大或未完全加载，这步可能会耗时)
            start_load_time = time.time()
            # Accessing pixels implicitly loads them if needed
            pixels = image.pixels[:] # Use slicing to ensure we get a copy, might help with large images
            load_time = time.time() - start_load_time
            if load_time > 0.1: # Log if loading took noticeable time
                 logger.info(f"    - 加载/访问像素耗时: {load_time:.4f} 秒")

            pixel_count = len(pixels) // image.channels # 计算像素总数

            # 检查 Alpha 值 (索引 3, 7, 11, ...)
            # Limit check for performance? For now, check all.
            check_limit = pixel_count # 检查所有像素
            # check_limit = min(pixel_count, 100000) # Example: Limit check

            logger.info(f"    - 准备检查 {check_limit} / {pixel_count} 个像素的 Alpha 值...")
            start_check_time = time.time()
            alpha_step = image.channels # Step should be number of channels

            for i in range(0, check_limit * alpha_step, alpha_step):
                alpha_index = i + 3 # Alpha is the 4th channel (index 3)
                if pixels[alpha_index] < 0.999: # Use a threshold for float comparison
                    has_meaningful_alpha = True
                    logger.info(f"    - 在像素 {i // alpha_step} 发现非不透明 Alpha 值: {pixels[alpha_index]:.4f}")
                    break # 找到一个就足够了

            end_check_time = time.time()
            logger.info(f"    - 像素检查耗时: {end_check_time - start_check_time:.4f} 秒")

            if not has_meaningful_alpha:
                logger.info("    - 所有检查过的像素 Alpha 值均接近 1.0")

        except IndexError as idx_err:
             logger.error(f"    - 检查像素时发生索引错误 (可能图像数据不完整?): {idx_err}")
             has_meaningful_alpha = False # Assume no alpha on error
        except MemoryError as mem_err:
             logger.error(f"    - 检查像素时发生内存错误 (图像可能过大): {mem_err}")
             logger.info(f"    - 跳过 Alpha 像素检查 for {image.name}")
             has_meaningful_alpha = False # Assume no alpha on error
        except Exception as pixel_check_err:
            logger.error(f"    - 检查像素时发生未知错误: {pixel_check_err}")
            import traceback
            traceback.print_exc()
            # 出错时，默认不连接 Alpha
            logger.info("    - 像素检查失败，回退到默认：无有效 Alpha。")
            has_meaningful_alpha = False
    else:
         logger.info(f"    - 图像只有 {image.channels} 个通道，不包含 Alpha。")

    # --- 后续连接逻辑，使用 has_meaningful_alpha ---
    alpha_input = principled_node.inputs.get("Alpha")
    bsdf_alpha_connected = False
    if alpha_input and alpha_input.links:
        bsdf_alpha_connected = True
        logger.info(f"  - 清理旧的 Principled BSDF Alpha 输入连接...")
        for link in list(alpha_input.links):
            logger.info(f"    - 断开 Alpha: {link.from_node.name}.{link.from_socket.name} -> {principled_node.name}.Alpha")
            links.remove(link)

    if has_meaningful_alpha and alpha_input:
        logger.info(f"  - 连接 Alpha: {diffuse_tex.name}.Alpha -> {principled_node.name}.Alpha (基于像素检查)")
        try:
            links.new(diffuse_tex.outputs["Alpha"], alpha_input)
            mat.blend_method = 'HASHED' # Using HASHED for potentially better performance than CLIP
            mat.shadow_method = 'HASHED' # Consistent shadow method
            logger.info(f"  - 设置材质 '{mat.name}' blend/shadow = HASHED")
        except Exception as link_alpha_err:
             logger.error(f"错误: 连接 Alpha 通道失败: {link_alpha_err}")
             # If linking fails, revert blend mode maybe?
             mat.blend_method = 'OPAQUE'
             mat.shadow_method = 'OPAQUE'
    else:
         # If no meaningful alpha, or linking failed, or no alpha input exists
         if bsdf_alpha_connected: # Only log if we previously disconnected something
              logger.info(f"  - 无有效 Alpha 或连接失败，确保材质 '{mat.name}' 为 OPAQUE")
         mat.blend_method = 'OPAQUE'
         mat.shadow_method = 'OPAQUE'


# --- 重构后的 PBR Operator ---

class AUTO_OT_create_pbr_materials(Operator):
    bl_idname = "auto.create_pbr_materials"
    bl_label = "一键PBR材质着色 (重构版)"
    bl_description = "选择贴图文件夹，自动应用PBR材质节点 (已重构)"
    bl_options = {'REGISTER', 'UNDO'}

    # 只保留文件选择器必需的属性
    directory: StringProperty(
        name="贴图文件夹",
        description="选择包含贴图的文件夹",
        subtype='DIR_PATH'
    )

    @classmethod
    def poll(cls, context):
        """检查是否可以执行操作"""
        # 检查是否有eyenewadd或eyenewmul材质
        has_eye_materials = False
        for mat in bpy.data.materials:
            mat_name_lower = mat.name.lower()
            if 'eyenewadd' in mat_name_lower or 'eyenewmul' in mat_name_lower:
                has_eye_materials = True
                break
        
        # 如果有eye材质，检查是否指定了eyeblend贴图
        if has_eye_materials:
            pbr_settings = getattr(context.scene, 'pbr_material_settings', None)
            if not pbr_settings or not pbr_settings.eyeblend_texture_path:
                return False
            # 检查文件是否存在
            eyeblend_path = bpy.path.abspath(pbr_settings.eyeblend_texture_path)
            if not os.path.exists(eyeblend_path):
                return False
        
        return True

    def invoke(self, context, event):
        """在执行前调用，打开文件选择对话框"""
        # 直接打开文件选择对话框，所有设置都从场景属性获取
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def setup_single_material(self, mat, diffuse_path, rmo_path, processed_set, processing_mode, copy_textures_externally, external_texture_directory):
        """设置单个材质的 PBR 节点树 (完整版)"""
        logger = logging.getLogger('pbr_materials')
        logger.info(f"开始设置材质: {mat.name}")
        logger.info(f"  - Diffuse Path: {diffuse_path}")
        logger.info(f"  - RMO Path: {rmo_path}")

        if mat.name in processed_set:
            logger.info(f"材质 '{mat.name}' 已处理，跳过")
            return False # Already processed

        try:
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            # 1. 清理旧节点，保留必要的节点
            logger.info("  - 清理旧节点...")
            remove_normals = (processing_mode == 'BASE_ALPHA')
            existing_output, existing_bsdf, existing_normal_map, existing_normal_texture = _cleanup_material_nodes(nodes, links, remove_normal_nodes=remove_normals)
            logger.info(f"    - 保留节点: Output={existing_output}, BSDF={existing_bsdf}, NormalMap={existing_normal_map}, NormalTexture={existing_normal_texture}")
            if remove_normals:
                logger.info("    - BASE_ALPHA模式: 已删除法向相关节点")

            # 2. 创建或复用基础 BSDF 和 Output 节点
            logger.info("  - 创建/复用基础节点...")
            principled_node, output_node = _create_base_nodes(nodes, links, existing_output, existing_bsdf, existing_normal_map, existing_normal_texture)
            if not principled_node or not output_node:
                 logger.error(f"错误: 无法创建或找到 Principled BSDF 或 Output 节点 for '{mat.name}'")
                 return False

            # 3. 加载纹理节点
            logger.info("  - 加载纹理节点...")
            diffuse_tex_node = None
            rmo_tex_node = None
            mat_base_name = mat.name.split('.')[0] # Get base name for node prefix only

            # --- Diffuse Texture Handling ---
            if diffuse_path:
                final_diffuse_path_for_load = diffuse_path
                # 如果启用了外部复制，则复制并获取新路径
                if copy_textures_externally and external_texture_directory:
                    copied_path = self._copy_texture_file(diffuse_path, external_texture_directory, mat.name, "_d")
                    if copied_path:
                        final_diffuse_path_for_load = copied_path
                    else:
                        logger.warning(f"警告: 复制 Diffuse 贴图失败 for '{mat.name}', 将使用原始路径")

                logger.info(f"    - 准备加载 Diffuse: '{os.path.basename(final_diffuse_path_for_load)}'")
                diffuse_tex_node = _load_texture_node(nodes, final_diffuse_path_for_load, mat_base_name, mat.name, is_rmo=False)
                if diffuse_tex_node:
                    logger.info(f"    - Diffuse 节点加载成功: {diffuse_tex_node.name}")
                else:
                    logger.error(f"    - Diffuse 节点加载失败 for: {final_diffuse_path_for_load}")
            else:
                logger.info("    - 无 Diffuse 路径提供")

            # --- RMO Texture Handling ---
            if processing_mode == 'FULL' and rmo_path:
                final_rmo_path_for_load = rmo_path
                # 如果启用了外部复制，则复制并获取新路径
                if copy_textures_externally and external_texture_directory:
                    copied_path = self._copy_texture_file(rmo_path, external_texture_directory, mat.name, "_rmo")
                    if copied_path:
                        final_rmo_path_for_load = copied_path
                    else:
                        logger.warning(f"警告: 复制 RMO 贴图失败 for '{mat.name}', 将使用原始路径")

                logger.info(f"    - 准备加载 RMO: '{os.path.basename(final_rmo_path_for_load)}'")
                # Pass mat.name as material_name argument, REMOVED force_unique_datablock
                rmo_tex_node = _load_texture_node(nodes, final_rmo_path_for_load, mat_base_name, mat.name, is_rmo=True)
                if rmo_tex_node:
                    # actual_rmo_path = final_rmo_path_for_load # Not strictly needed anymore
                    logger.info(f"    - RMO 节点加载成功: {rmo_tex_node.name}")
                else:
                     logger.error(f"    - RMO 节点加载失败 for: {final_rmo_path_for_load}")
            elif processing_mode != 'FULL':
                 logger.info("    - 处理模式非 FULL，跳过 RMO 加载")
            else:
                 logger.info("    - 无 RMO 路径提供")

            # 4. 连接纹理到 Principled BSDF
            logger.info("  - 连接纹理到 Principled BSDF...")
            _link_textures_to_principled(nodes, links, principled_node, diffuse_tex_node, rmo_tex_node)

            # 5. 处理 Alpha 通道
            logger.info("  - 处理 Alpha 通道...")
            _handle_alpha_channel(mat, links, principled_node, diffuse_tex_node)

            # --- 特殊处理: eyenewmul 强制透明 ---
            if "eyenewmul" in mat.name.lower():
                logger.info(f"    - 特殊规则: 强制材质 '{mat.name}' (eyenewmul) 为完全透明")
                if principled_node.inputs.get("Alpha"):
                    # 断开可能存在的 Alpha 连接
                    if principled_node.inputs["Alpha"].links:
                        for link in list(principled_node.inputs["Alpha"].links):
                            links.remove(link)
                    # 设置 Alpha 值为 0
                    principled_node.inputs["Alpha"].default_value = 0.0 # 改为 0.0
                mat.blend_method = 'BLEND' # 改为 BLEND
                mat.shadow_method = 'NONE' # 改为 NONE

            # 6. BASE_ALPHA模式下的特殊设置
            if processing_mode == 'BASE_ALPHA':
                logger.info(f"  - BASE_ALPHA模式: 设置材质属性...")
                # 设置金属度为0
                if principled_node.inputs.get("Metallic"):
                    principled_node.inputs["Metallic"].default_value = 0.0
                    logger.info(f"    - 金属度设为: 0.0")
                # 设置粗糙度为0
                if principled_node.inputs.get("Roughness"):
                    principled_node.inputs["Roughness"].default_value = 0.0
                    logger.info(f"    - 粗糙度设为: 0.0")
                # 设置折射率为1
                if principled_node.inputs.get("IOR"):
                    principled_node.inputs["IOR"].default_value = 1.0
                    logger.info(f"    - 折射率设为: 1.0")

            # 7. 标记为已处理
            processed_set.add(mat.name)
            logger.info(f"材质 '{mat.name}' 设置成功")
            return True

        except Exception as e:
            logger.error(f"设置材质 '{mat.name}' 时发生严重错误: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return False

    def setup_logger(self, log_to_file, log_file_path):
        """设置日志记录器"""
        # 清除可能存在的handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 创建logger
        logger = logging.getLogger('pbr_materials')
        logger.setLevel(logging.DEBUG) # Set level for the logger itself

        # 创建console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO) # Control console output level

        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        # 添加console handler
        logger.addHandler(console_handler)

        # 如果启用了文件日志
        if log_to_file and log_file_path:
            try:
                # 解析路径，处理Blender相对路径
                log_path = log_file_path
                if log_path.startswith('//'):
                    # 转换到绝对路径
                    log_path = bpy.path.abspath(log_path)

                # 确保目录存在
                log_dir = os.path.dirname(log_path)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)

                # 创建文件handler
                file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
                file_handler.setLevel(logging.DEBUG) # Control file output level
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

                logger.info(f"日志文件已设置: {log_path}")
            except Exception as e:
                logger.error(f"无法设置日志文件: {e}")
                # Use self.report for operator feedback
                self.report({'WARNING'}, f"无法设置日志文件: {e}")
        # Ensure logger propagation is off if desired to avoid duplicate root logger messages
        logger.propagate = False
        return logger
    
    def _check_extended_rules(self, mat_name_lower):
        """检查材质名称是否匹配扩展特殊规则"""
        extended_patterns = [
            'hairuber',
            'cloth2double',
            'silkstock',
            'faceuber'
        ]
        return any(pattern in mat_name_lower for pattern in extended_patterns)
    
    def _apply_extended_rules(self, mat_name, mat_name_lower, special_textures, texture_dict, logger, cloth2double_cloth_type, silkstock_cloth_type):
        """应用扩展特殊规则"""
        diffuse_to_use = None
        rmo_to_use = None
        
        if 'hairuber' in mat_name_lower:
            # hairuber 材质使用 hair 贴图
            if special_textures['hair']:
                diffuse_to_use = special_textures['hair'][0][1]
                hair_base_name = special_textures['hair'][0][0]
                rmo_path = texture_dict.get(hair_base_name, {}).get('rmo')
                if rmo_path:
                    rmo_to_use = rmo_path
                logger.info(f"规则应用: '{mat_name}' (hairuber) -> 使用 'hair' 贴图 {'和 RMO' if rmo_to_use else ''}")
            else:
                logger.warning(f"警告: 未找到 'hair' 贴图用于 '{mat_name}'")
        
        elif 'cloth2double' in mat_name_lower:
            # cloth2Double_uber 材质根据设置选择贴图类型
            cloth_type = cloth2double_cloth_type
            if cloth_type == 'NONE':
                logger.info(f"跳过处理: '{mat_name}' (cloth2Double) - 用户选择不处理")
                return None, None
            
            cloth_key = 'cloth1' if cloth_type == 'CLOTH1' else 'cloth2'
            if special_textures[cloth_key]:
                diffuse_to_use = special_textures[cloth_key][0][1]
                cloth_base_name = special_textures[cloth_key][0][0]
                rmo_path = texture_dict.get(cloth_base_name, {}).get('rmo')
                if rmo_path:
                    rmo_to_use = rmo_path
                logger.info(f"规则应用: '{mat_name}' (cloth2Double) -> 使用 '{cloth_key}' 贴图 {'和 RMO' if rmo_to_use else ''}")
            else:
                logger.warning(f"警告: 未找到 '{cloth_key}' 贴图用于 '{mat_name}'")
        
        elif 'silkstock' in mat_name_lower:
            # silkstock_uber 材质根据设置选择贴图类型
            cloth_type = silkstock_cloth_type
            if cloth_type == 'NONE':
                logger.info(f"跳过处理: '{mat_name}' (silkstock) - 用户选择不处理")
                return None, None
            
            cloth_key = 'cloth1' if cloth_type == 'CLOTH1' else 'cloth2'
            if special_textures[cloth_key]:
                diffuse_to_use = special_textures[cloth_key][0][1]
                cloth_base_name = special_textures[cloth_key][0][0]
                rmo_path = texture_dict.get(cloth_base_name, {}).get('rmo')
                if rmo_path:
                    rmo_to_use = rmo_path
                logger.info(f"规则应用: '{mat_name}' (silkstock) -> 使用 '{cloth_key}' 贴图 {'和 RMO' if rmo_to_use else ''}")
            else:
                logger.warning(f"警告: 未找到 '{cloth_key}' 贴图用于 '{mat_name}'")
        
        elif 'faceuber' in mat_name_lower:
            # faceuber 材质使用 face 贴图
            if special_textures['face']:
                diffuse_to_use = special_textures['face'][0][1]
                logger.info(f"规则应用: '{mat_name}' (faceuber) -> 使用 'face' 贴图")
            else:
                logger.warning(f"警告: 未找到 'face' 贴图用于 '{mat_name}'")
        
        return diffuse_to_use, rmo_to_use

    def _copy_texture_file(self, source_path, target_dir, material_name, suffix):
        """将纹理文件复制到目标目录，并使用材质名和后缀重命名。返回新路径或None。"""
        logger = logging.getLogger('pbr_materials')
        if not source_path or not os.path.exists(source_path):
            logger.error(f"_copy_texture_file: 源文件无效: {source_path}")
            return None
        if not target_dir:
            logger.error(f"_copy_texture_file: 未指定目标目录")
            return None

        try:
            # 确保目标目录存在
            target_dir_abs = bpy.path.abspath(target_dir)
            if not os.path.exists(target_dir_abs):
                os.makedirs(target_dir_abs, exist_ok=True)
                logger.info(f"创建目标目录: {target_dir_abs}")

            # 获取原始文件扩展名
            _, ext = os.path.splitext(source_path)
            if not ext:
                ext = ".png" # 如果没有扩展名，默认使用.png
                logger.warning(f"源文件 '{os.path.basename(source_path)}' 无扩展名，默认使用 '.png'")

            # 构建新文件名 (使用材质名 + 后缀 + 扩展名)
            # 清理材质名中的非法字符，以用于文件名
            safe_material_name = re.sub(r'[^\w\-. ]', '_', material_name) # 允许字母数字、下划线、连字符、点、空格
            new_filename = f"{safe_material_name}{suffix}{ext}"
            target_path = os.path.join(target_dir_abs, new_filename)

            # 执行复制 (shutil.copy2 会保留元数据)
            shutil.copy2(source_path, target_path)
            logger.info(f"复制外部纹理: '{os.path.basename(source_path)}' -> '{new_filename}'")
            return target_path

        except Exception as e:
            logger.error(f"复制外部纹理 '{os.path.basename(source_path)}' 到 '{target_dir}' 失败: {e}", exc_info=True)
            return None

    def execute(self, context):
        # 从PBR设置获取日志和扩展规则设置
        pbr_settings = context.scene.pbr_material_settings
        log_to_file = pbr_settings.log_to_file if pbr_settings else False
        log_file_path = pbr_settings.log_file_path if pbr_settings else "//pbr_material_log.txt"
        enable_extended_rules = True  # 默认启用扩展规则
        
        # 设置日志记录器
        logger = self.setup_logger(log_to_file, log_file_path)
        logger.info("=" * 50)
        logger.info("开始执行一键PBR材质着色 (重构版)")

        start_time = time.time()
        if not self.directory or not os.path.exists(self.directory):
            logger.error(f"无效的贴图文件夹: {self.directory}")
            self.report({'ERROR'}, "请选择有效的贴图文件夹")
            return {'CANCELLED'}

        # 从场景属性获取所有设置
        clean_data = context.scene.pbr_clean_data
        skinuber_cloth_type = context.scene.pbr_skinuber_cloth_type
        cloth2double_cloth_type = context.scene.pbr_cloth2double_cloth_type
        silkstock_cloth_type = context.scene.pbr_silkstock_cloth_type
        processing_mode = context.scene.pbr_processing_mode
        copy_textures_externally = context.scene.pbr_copy_textures_externally
        external_texture_directory = context.scene.pbr_external_texture_directory

        # 检查外部复制设置是否有效
        if copy_textures_externally and not external_texture_directory:
            logger.error("启用了外部复制，但未指定目标文件夹")
            self.report({'ERROR'}, "请指定外部纹理文件夹")
            return {'CANCELLED'}

        # 规范化路径
        self.directory = os.path.normpath(self.directory)
        if external_texture_directory:
            external_texture_directory = os.path.normpath(bpy.path.abspath(external_texture_directory))
            logger.info(f"外部纹理目标目录: {external_texture_directory}")
        else:
             logger.info("未启用外部纹理复制")

        logger.info(f"源贴图目录: {self.directory}")
        logger.info(f"创建独立数据块: {clean_data}")
        logger.info(f"复制纹理到外部: {copy_textures_externally}")
        logger.info(f"清理未使用数据: {clean_data}")
        logger.info(f"Skinuber贴图类型: {skinuber_cloth_type}")
        logger.info(f"Cloth2Double贴图类型: {cloth2double_cloth_type}")
        logger.info(f"Silkstock贴图类型: {silkstock_cloth_type}")
        logger.info(f"PBR 处理模式: {processing_mode}")
        logger.info("=" * 50)

        # 1. 清理未使用数据 (可选)
        if clean_data:
            logger.info("开始清理未使用数据")
            try:
                bpy.ops.outliner.orphans_purge(do_recursive=True)
                bpy.ops.outliner.orphans_purge(do_recursive=True) # Run twice for good measure
                logger.info("已执行孤立数据清理")
            except Exception as clean_err:
                 logger.error(f"清理数据时出错: {clean_err}")
            logger.info("清理数据结束")

        # 2. 收集场景材质和贴图文件
        logger.info("开始收集材质和贴图")
        all_materials = {mat.name: mat for mat in bpy.data.materials}
        logger.info(f"找到 {len(all_materials)} 个场景材质")
        for mat_name in all_materials:
            logger.debug(f"材质: {mat_name}")

        texture_files = [f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))]
        logger.info(f"找到 {len(texture_files)} 个文件在源目录")
        for f in texture_files:
            logger.debug(f"文件: {f}")

        # 按基础名称整理贴图 (Diffuse 和 RMO)
        texture_dict = defaultdict(dict)
        special_textures = defaultdict(list) # face, eyeblend, hair, cloth1, cloth2
        # 修改后缀映射，去掉点
        texture_suffix_map = {"_d": "diffuse", "_rmo": "rmo"}

        logger.info("开始识别贴图类型和基础名称")
        for file in texture_files:
            file_path = os.path.join(self.directory, file)
            base_name = file
            texture_type = None

            logger.debug(f"处理文件: {file}")

            # 识别贴图类型和基础名称
            root, ext = os.path.splitext(file)
            for suffix, type_name in texture_suffix_map.items():
                # 修改：检查文件名是否以后缀结尾
                if root.endswith(suffix):
                    # 获取基础名称（去掉后缀）
                    base_name = root[:-len(suffix)] # 使用切片移除后缀
                    texture_type = type_name
                    logger.debug(f"识别到贴图类型: {file} -> 类型={type_name}, 基础名={base_name}")
                    break # 找到主要类型后跳出循环

            if texture_type:
                texture_dict[base_name][texture_type] = file_path
                logger.info(f"识别到贴图: Base='{base_name}', Type='{texture_type}', File='{file}'")

                # 收集特殊用途贴图 (仅Diffuse)
                if texture_type == 'diffuse':
                    name_lower = base_name.lower()
                    special_texture_types = {
                        'face': 'face' in name_lower and 'eyeface' not in name_lower,
                        'eye': 'eye' in name_lower and 'eyenew' not in name_lower and 'eyeblend' not in name_lower,
                        # 'eyeblend' 由下面的特殊捕获处理
                        'hair': 'hair' in name_lower and 'eyehair' not in name_lower,
                        'cloth1': 'cloth1' in name_lower,
                        'cloth2': 'cloth2' in name_lower
                    }

                    for sp_type, condition in special_texture_types.items():
                        if condition:
                            special_textures[sp_type].append((base_name, file_path))
                            logger.info(f"识别到特殊贴图: {sp_type} -> {file}")

            # 捕获 eyeblend 贴图，无论后缀如何
            if 'eyeblend' in root.lower(): # 在不含扩展名的部分检查
                already_added = any(item[1] == file_path for item in special_textures['eyeblend'])
                if not already_added:
                    # 使用不含扩展名的部分作为基础名
                    eyeblend_base_name = root
                    special_textures['eyeblend'].append((eyeblend_base_name, file_path))
                    logger.info(f"特殊捕获: Eyeblend 贴图 '{file}' (基础名: {eyeblend_base_name})")

        # 打印识别结果总览
        logger.info(f"整理后得到 {len(texture_dict)} 个贴图基础名称")
        logger.info(f"特殊贴图: Face={len(special_textures['face'])}, Eyeblend={len(special_textures['eyeblend'])}, Hair={len(special_textures['hair'])}, Cloth1={len(special_textures['cloth1'])}, Cloth2={len(special_textures['cloth2'])}")

        # 打印详细的texture_dict内容
        logger.info("--- 贴图字典内容 ---")
        for base, types in texture_dict.items():
            logger.info(f"  基础名: {base}")
            for type_name, path in types.items():
                logger.info(f"    - {type_name}: {os.path.basename(path)}")
        logger.info("--- 贴图字典内容结束 ---")

        # 打印特殊贴图字典内容
        logger.info("--- 特殊贴图内容 ---")
        for special_type, items in special_textures.items():
            logger.info(f"  类型: {special_type}")
            for base_name, path in items:
                logger.info(f"    - {base_name}: {os.path.basename(path)}")
        logger.info("--- 特殊贴图内容结束 ---")

        # 3. 处理材质
        logger.info("开始处理材质")
        processed_materials_set = set()
        materials_processed_count = 0
        materials_failed_count = 0
        external_copy_count = 0 # 跟踪外部复制次数

        # --- 特殊规则处理 ---
        logger.info("开始应用特殊材质规则")

        pbr_settings = context.scene.pbr_material_settings

        # 检查手动指定的eyeblend贴图
        eyeblend_path = None
        if pbr_settings.eyeblend_texture_path and os.path.exists(bpy.path.abspath(pbr_settings.eyeblend_texture_path)):
            # 优先使用手动指定的路径
            eyeblend_path = bpy.path.abspath(pbr_settings.eyeblend_texture_path)
            logger.info(f"使用手动指定的eyeblend贴图路径: {eyeblend_path}")
        else:
            # 尝试自动检测
            eyeblend_path = special_textures['eyeblend'][0][1] if special_textures['eyeblend'] else None
            if eyeblend_path:
                logger.info(f"自动检测到eyeblend贴图: {eyeblend_path}")

        # 缓存其他特殊贴图路径
        face_path = special_textures['face'][0][1] if special_textures['face'] else None
        hair_path = special_textures['hair'][0][1] if special_textures['hair'] else None
        eye_path = special_textures['eye'][0][1] if special_textures['eye'] else None

        if eyeblend_path: logger.info(f"使用eyeblend贴图: {os.path.basename(eyeblend_path)}")
        if face_path: logger.info(f"使用face贴图: {os.path.basename(face_path)}")
        if hair_path: logger.info(f"使用hair贴图: {os.path.basename(hair_path)}")
        if eye_path: logger.info(f"使用eye贴图: {os.path.basename(eye_path)}")

        # 缓存 RMO 贴图路径查找函数
        def find_rmo_for_base(base_name):
            rmo = texture_dict.get(base_name, {}).get('rmo')
            logger.debug(f"查找RMO for {base_name}: {'找到' if rmo else '未找到'}")
            return rmo

        # 遍历所有材质，应用特殊规则
        for mat_name, mat in all_materials.items():
            mat_name_lower = mat_name.lower()
            diffuse_to_use = None
            rmo_to_use = None
            # REMOVED: force_unique = False # 不再需要在这里初始化和重置
            rule_applied = True

            logger.info(f"处理材质: {mat_name} (lower: {mat_name_lower})")
            logger.debug(f"规则检查: eyelashuber: {'eyelashuber' in mat_name_lower}")
            logger.debug(f"规则检查: fringeuber: {'fringeuber' in mat_name_lower}")
            logger.debug(f"规则检查: skinuber: {'skinuber' in mat_name_lower}")
            logger.debug(f"规则检查: eyenewadd: {'eyenewadd' in mat_name_lower}")
            logger.debug(f"规则检查: eyenewmul: {'eyenewmul' in mat_name_lower}")

            # 特殊规则应用逻辑 - 保持现有代码逻辑不变，只添加日志记录
            if 'eyelashuber' in mat_name_lower:
                if special_textures['face']:
                    diffuse_to_use = special_textures['face'][0][1]
                    logger.info(f"规则应用: '{mat_name}' (eyelashuber) -> 使用 'face' 贴图")
                else:
                    logger.warning(f"警告: 未找到 'face' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'eyenewadd' in mat_name_lower or 'eyenewmul' in mat_name_lower:
                if eyeblend_path:
                    diffuse_to_use = eyeblend_path
                    logger.info(f"规则应用: '{mat_name}' ({'eyenewadd' if 'add' in mat_name_lower else 'eyenewmul'}) -> 使用 'eyeblend' 贴图")
                else:
                    logger.warning(f"警告: 未找到 'eyeblend' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'eyenew' in mat_name_lower and 'eyenewmu' not in mat_name_lower:
                if eye_path:
                    diffuse_to_use = eye_path
                    logger.info(f"规则应用: '{mat_name}' (eyenew) -> 使用 'eye' 贴图")
                else:
                    logger.warning(f"警告: 未找到 'eye' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'fringeuber' in mat_name_lower:
                 if hair_path:
                    diffuse_to_use = hair_path
                    # 查找对应的 RMO
                    hair_base_name = special_textures['hair'][0][0]
                    rmo_to_use = find_rmo_for_base(hair_base_name)
                    logger.info(f"规则应用: '{mat_name}' (fringeuber) -> 使用 'hair' 贴图 {'和 RMO' if rmo_to_use else ''}")
                 else:
                    logger.warning(f"警告: 未找到 'hair' 贴图用于 '{mat_name}'")
                    rule_applied = False
            elif 'skinuber' in mat_name_lower:
                if skinuber_cloth_type != 'NONE':
                    cloth_key = 'cloth1' if skinuber_cloth_type == 'CLOTH1' else 'cloth2'
                    logger.info(f"skinuber材质使用{cloth_key}贴图")
                    if special_textures[cloth_key]:
                        diffuse_to_use = special_textures[cloth_key][0][1]
                        # 查找对应的 RMO
                        cloth_base_name = special_textures[cloth_key][0][0]
                        rmo_path = texture_dict.get(cloth_base_name, {}).get('rmo')
                        if rmo_path:
                            rmo_to_use = rmo_path
                        logger.info(f"规则应用: '{mat_name}' (skinuber) -> 使用 '{cloth_key}' 贴图 {'和 RMO' if rmo_to_use else ''}")
                    else:
                        logger.warning(f"警告: 未找到 '{cloth_key}' 贴图用于 '{mat_name}'")
                        rule_applied = False
                else:
                    logger.info(f"跳过skinuber材质处理 (设置为NONE)")
                    rule_applied = False
            # 新增：扩展特殊规则处理
            elif enable_extended_rules and self._check_extended_rules(mat_name_lower):
                diffuse_to_use, rmo_to_use = self._apply_extended_rules(mat_name, mat_name_lower, special_textures, texture_dict, logger, cloth2double_cloth_type, silkstock_cloth_type)
                if diffuse_to_use:
                    rule_applied = True
                else:
                    rule_applied = False
            else:
                logger.info(f"材质 '{mat_name}' 不适用特殊规则")
                rule_applied = False

            # 如果应用了特殊规则，并且找到了贴图
            if rule_applied and diffuse_to_use:
                # *** 修改: 外部复制逻辑 ***
                final_diffuse_path = diffuse_to_use
                final_rmo_path = rmo_to_use
                # mat_base_name = mat_name.split('.')[0] # Use full material name for copying

                logger.info(f"应用特殊规则 '{mat_name}':")
                logger.info(f"  - 初始Diffuse: '{os.path.basename(diffuse_to_use) if diffuse_to_use else 'None'}'")
                logger.info(f"  - 初始RMO: '{os.path.basename(rmo_to_use) if rmo_to_use else 'None'}'")
                logger.info(f"  - 复制外部选项: {copy_textures_externally}")
                logger.info(f"  - 独立数据块选项: {clean_data}")

                # --- 外部复制处理 --- 
                if copy_textures_externally and external_texture_directory:
                    if diffuse_to_use:
                        copied_d_path = self._copy_texture_file(diffuse_to_use, external_texture_directory, mat_name, "_d")
                        if copied_d_path:
                            final_diffuse_path = copied_d_path
                            external_copy_count += 1
                        else:
                            logger.error(f"无法复制漫反射贴图 '{os.path.basename(diffuse_to_use)}' 到外部目录，将使用原始路径")
                    
                    if rmo_to_use and processing_mode == 'FULL': # Only copy RMO if processing it
                        copied_rmo_path = self._copy_texture_file(rmo_to_use, external_texture_directory, mat_name, "_rmo")
                        if copied_rmo_path:
                            final_rmo_path = copied_rmo_path
                            external_copy_count += 1 # Count RMO copies too if needed
                        else:
                            logger.error(f"无法复制RMO贴图 '{os.path.basename(rmo_to_use)}' 到外部目录，将使用原始路径")
                # --- 外部复制处理结束 --- 

                # 调用材质设置函数 - force_unique 由 self.copy_textures 控制 (独立数据块)
                try:
                    logger.info(f"  - 设置材质: {mat_name}")
                    logger.info(f"  - 使用Diffuse路径: '{final_diffuse_path if final_diffuse_path else 'None'}'")
                    logger.info(f"  - 使用RMO路径: '{final_rmo_path if final_rmo_path else 'None'}'")

                    # 传递最终的文件路径和独立数据块设置
                    if self.setup_single_material(mat, final_diffuse_path, final_rmo_path, processed_materials_set, processing_mode, copy_textures_externally, external_texture_directory):
                        materials_processed_count += 1
                        logger.info(f"材质 '{mat_name}' 处理成功")
                    else:
                        materials_failed_count += 1
                        logger.warning(f"材质 '{mat_name}' 处理失败")
                except Exception as e:
                    materials_failed_count += 1
                    logger.error(f"设置材质 '{mat_name}' 时发生错误: {e}")
                # else: # Original logic had an else block here, seems it was meant for when rules didn't apply or diffuse wasn't found
                    # This part seems less relevant now, as materials not handled by special rules fall through to regular matching.
                    # If you need to log something specific here, you can add it. Example:
                    # elif not rule_applied:
                    #     logger.info(f"材质 '{mat_name}' 未应用特殊规则，将尝试常规匹配")
                    # elif not diffuse_to_use:
                    #     logger.warning(f"材质 '{mat_name}' 应用规则但未找到漫反射贴图")


        # --- 常规智能匹配处理 ---
        logger.info("\n--- 开始常规智能匹配 ---")
        # (收集所有未被特殊规则处理的材质)
        remaining_materials = {name: mat for name, mat in all_materials.items() if name not in processed_materials_set}
        logger.info(f"剩余 {len(remaining_materials)} 个材质待智能匹配")

        for base_name, textures in texture_dict.items():
            # 跳过没有漫反射的组
            diffuse_path = textures.get('diffuse')
            if not diffuse_path:
                logger.debug(f"跳过贴图组 '{base_name}' (无漫反射贴图)")
                continue

            rmo_path = textures.get('rmo')
            logger.info(f"尝试为贴图组 '{base_name}' 匹配材质...")

            best_match_name = None
            best_score = 0

            # Iterate over a copy of the keys to allow deletion within the loop
            for mat_name in list(remaining_materials):
                score = 0
                mat_name_lower = mat_name.lower()
                base_name_lower = base_name.lower()

                mat_base_lower = mat_name_lower
                if mat_base_lower.endswith('_uber'):
                    mat_base_lower = mat_base_lower[:-5]

                if mat_base_lower == base_name_lower:
                    score = 100
                elif mat_base_lower.startswith(base_name_lower):
                    score = len(base_name_lower) + 10
                elif base_name_lower.startswith(mat_base_lower):
                    score = len(mat_base_lower)
                # Consider adding fuzzy matching score here if needed

                logger.debug(f"匹配比较: 贴图基础名='{base_name_lower}', 材质基础名='{mat_base_lower}', 得分={score}")

                if score > best_score:
                    best_score = score
                    best_match_name = mat_name

                # 修改匹配阈值：从 >= 100 改为 >= 30
                if best_match_name and best_score >= 30:
                    # *** ADD CHECK HERE: Ensure the best match wasn't processed in a previous outer loop iteration ***
                    if best_match_name in remaining_materials:
                        mat = remaining_materials[best_match_name]
                        logger.info(f"智能匹配成功: 贴图 '{base_name}' -> 材质 '{best_match_name}' (Score: {best_score})")

                        # *** 修改: 外部复制逻辑 ***
                        final_diffuse_path = diffuse_path
                        final_rmo_path = rmo_path

                        logger.info(f"智能匹配 '{best_match_name}':")
                        logger.info(f"  - 初始Diffuse: '{os.path.basename(diffuse_path) if diffuse_path else 'None'}'")
                        logger.info(f"  - 初始RMO: '{os.path.basename(rmo_path) if rmo_path else 'None'}'")
                        logger.info(f"  - 复制外部选项: {copy_textures_externally}")
                        logger.info(f"  - 独立数据块选项: {clean_data}")
                        
                        # --- 外部复制处理 ---
                        if copy_textures_externally and external_texture_directory:
                            if diffuse_path:
                                copied_d_path = self._copy_texture_file(diffuse_path, external_texture_directory, best_match_name, "_d")
                                if copied_d_path:
                                    final_diffuse_path = copied_d_path
                                    external_copy_count += 1
                                else:
                                    logger.error(f"无法复制漫反射贴图 '{os.path.basename(diffuse_path)}' 到外部目录，将使用原始路径")
                            
                            if rmo_path and processing_mode == 'FULL': # Only copy RMO if processing it
                                copied_rmo_path = self._copy_texture_file(rmo_path, external_texture_directory, best_match_name, "_rmo")
                                if copied_rmo_path:
                                    final_rmo_path = copied_rmo_path
                                    external_copy_count += 1
                                else:
                                    logger.error(f"无法复制RMO贴图 '{os.path.basename(rmo_path)}' 到外部目录，将使用原始路径")
                        # --- 外部复制处理结束 ---

                        # 处理材质 - force_unique 由 self.copy_textures 控制
                        try:
                            logger.info(f"  - 设置材质: {best_match_name} (常规匹配)")
                            logger.info(f"  - 使用Diffuse路径: '{final_diffuse_path if final_diffuse_path else 'None'}'")
                            logger.info(f"  - 使用RMO路径: '{final_rmo_path if final_rmo_path else 'None'}'")
                            
                            # 传递最终的文件路径和独立数据块设置
                            if self.setup_single_material(mat, final_diffuse_path, final_rmo_path, processed_materials_set, processing_mode, copy_textures_externally, external_texture_directory):
                                materials_processed_count += 1
                                logger.info(f"材质 '{best_match_name}' 处理成功")
                                del remaining_materials[best_match_name]
                            else:
                                materials_failed_count += 1
                                # Log failure here if setup_single_material returned False
                                logger.warning(f"材质 '{best_match_name}' (常规匹配) setup_single_material 返回 False")
                        except Exception as e:
                            materials_failed_count += 1
                            logger.error(f"设置材质 '{best_match_name}' (常规匹配) 时发生错误: {e}", exc_info=True)
                    else:
                        # Log that the best match was found but already processed earlier
                        logger.warning(f"贴图组 '{base_name}' 的最佳匹配 '{best_match_name}' 已在之前的迭代中处理，跳过")
                else:
                     # 仅在 best_match_name 存在但分数不够时记录更详细的信息
                     if best_match_name:
                         logger.info(f"贴图组 '{base_name}' 找到潜在匹配 '{best_match_name}' 但分数 ({best_score}) 不足 30")
                     else:
                         logger.info(f"贴图组 '{base_name}' 未找到任何常规材质匹配")


        # 打印最终未处理的材质
        if remaining_materials:
            logger.warning("--- 以下材质未找到匹配的贴图或未被处理 ---")
            for mat_name in remaining_materials:
                logger.warning(f"- {mat_name}")
            logger.warning("--- 未处理材质列表结束 ---")

        # 完成处理，记录统计信息
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info("=" * 50)
        logger.info(f"PBR材质处理完成，耗时 {elapsed_time:.2f} 秒")
        logger.info(f"处理成功: {materials_processed_count} 个材质")
        logger.info(f"处理失败/跳过: {materials_failed_count} 个材质")
        if copy_textures_externally:
            logger.info(f"外部复制: {external_copy_count} 个纹理文件") # Log external copy count
        logger.info("=" * 50)

        # --- 新的清理位置：在所有处理完成后执行 ---
        if clean_data:
            logger.info("开始清理未使用数据 (最终)")
            try:
                # 确保在 Object 模式下执行清理
                if bpy.context.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.outliner.orphans_purge(do_recursive=True)
                bpy.ops.outliner.orphans_purge(do_recursive=True) # 多执行一次确保清理干净
                logger.info("已执行最终孤立数据清理")
            except Exception as clean_err:
                 logger.error(f"最终清理数据时出错: {clean_err}")
            logger.info("最终清理数据结束")

        return {'FINISHED'}

    # ...【保留类中的其他方法】...

# 修改面板类，添加日志选项
class MQT_PT_PBRMaterialPanel(Panel):
    bl_label = "一键PBR材质着色"
    bl_idname = "MQT_PT_PBRMaterialPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 添加操作按钮
        box = layout.box()
        row = box.row()
        # 注意：这里的 bl_idname 要与重构后的 Operator 类名一致
        row.operator(AUTO_OT_create_pbr_materials.bl_idname, icon='NODE_MATERIAL')

        # 获取PBR设置
        pbr_settings = context.scene.pbr_material_settings

        # 添加手动指定eyeblend贴图的UI
        eyeblend_box = layout.box()
        eyeblend_box.label(text="Eyeblend贴图设置:")
        eyeblend_box.prop(pbr_settings, "eyeblend_texture_path")

        
        # 添加属性设置
        props = box.column()
        props.label(text="内部设置:")
        # Removed output directory setting
        props.prop(context.scene, "pbr_clean_data")
        props.prop(context.scene, "pbr_skinuber_cloth_type", text="Skinuber贴图类型")
        props.prop(context.scene, "pbr_cloth2double_cloth_type", text="Cloth2Double贴图类型")
        props.prop(context.scene, "pbr_silkstock_cloth_type", text="Silkstock贴图类型")
        # Add the processing mode selector
        props.prop(context.scene, "pbr_processing_mode", text="处理模式")
        
        # 添加扩展特殊规则开关
        props.separator()
        props.label(text="扩展规则设置:")
        # 注意：这里需要通过operator的属性来控制，暂时用文本说明
        props.label(text="扩展特殊规则: 默认启用", icon='INFO')
        props.label(text="支持: hairuber, cloth2Double, silkstock")

        # 添加复制外部纹理设置
        props.separator()
        props.label(text="外部复制设置 (防合并):")
        row = props.row()
        row.prop(context.scene, "pbr_copy_textures_externally")
        row = props.row()
        row.enabled = context.scene.pbr_copy_textures_externally # 仅在启用时可选路径
        row.prop(context.scene, "pbr_external_texture_directory")

        # 添加日志设置UI
        box = layout.box()
        box.label(text="日志设置:")
        row = box.row()
        row.prop(context.scene.pbr_material_settings, "log_to_file")
        if context.scene.pbr_material_settings.log_to_file:
            row = box.row()
            row.prop(context.scene.pbr_material_settings, "log_file_path")
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明:", icon='INFO')
        box.label(text="1. 确保材质已存在于场景中")
        box.label(text="2. 将贴图命名为类似于材质名称的格式")
        box.label(text="3. 漫反射贴图添加_d后缀")
        box.label(text="4. RMO贴图添加_rmo后缀")
        box.label(text="5. 设置输出文件夹(可选)")
        box.label(text="6. 智能匹配贴图到材质")
        
        # 特殊规则说明
        special_box = layout.box()
        special_box.label(text="特殊规则:", icon='INFO')
        special_box.label(text="* eyelashuber → face贴图")
        special_box.label(text="* eyenewadd → eyeblend贴图(复制+独立)")
        special_box.label(text="* eyenewmul → eyeblend贴图(复制+独立)")
        special_box.label(text="* fringeuber → hair贴图(复制)")
        special_box.label(text="* skinuber → 根据选择使用cloth1/cloth2贴图")
        
        # 扩展特殊规则说明
        extended_box = layout.box()
        extended_box.label(text="扩展特殊规则 (新增):", icon='PLUS')
        extended_box.label(text="* hairuber → hair贴图")
        extended_box.label(text="* cloth2Double_uber → cloth2贴图")
        extended_box.label(text="* silkstock_uber → cloth1贴图")
        extended_box.label(text="注: 基于名称匹配，支持开关控制")

# --------------------------------------------------------------------------
# 工具 7: 网格权重显示工具 (新功能)
# --------------------------------------------------------------------------

class MeshWeightToolsSettings(PropertyGroup):
    zero_weight_threshold: FloatProperty(
        name="权重阈值",
        description="顶点权重低于此值被视为空权重",
        default=0.001,
        min=0.0,
        max=0.1, # Adjusted max for practical use
        soft_min=0.0,
        soft_max=0.1,
        step=0.001,
        precision=3 # For better display of small numbers
    )

class MESH_OT_isolate_zero_weight_meshes(Operator):
    bl_idname = "mesh.isolate_zero_weight"
    bl_label = "隔离零权重网格"
    bl_description = "在编辑模式下隐藏非零权重网格，显示零权重网格。基于可调阈值。"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        # print("--- MESH_OT_isolate_zero_weight_meshes EXECUTE (Vertex-Level Hide) ---")
        settings = context.scene.mq_mesh_weight_settings
        threshold = settings.zero_weight_threshold
        # print(f"Threshold: {threshold:.4f}")

        if not (context.active_object and context.active_object.type == 'MESH' and context.mode == 'EDIT_MESH'):
            self.report({'WARNING'}, "请先在编辑模式下选择一个网格对象")
            # print("No active mesh object in edit mode.")
            return {'CANCELLED'}

        obj = context.active_object
        # print(f"Processing object: {obj.name}")

        bpy.ops.object.mode_set(mode='OBJECT')
        # print(f"  Switched to OBJECT mode for object '{obj.name}'.")

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # print(f"  Created bmesh with {len(bm.verts)} verts, {len(bm.edges)} edges, {len(bm.faces)} faces.")

        verts_hidden_count = 0
        verts_shown_count = 0

        if not obj.vertex_groups:
            # print(f"  Object '{obj.name}' has NO vertex groups. All vertices will be SHOWN.")
            for v_bm in bm.verts:
                v_bm.hide = False
                verts_shown_count +=1
        else:
            # print(f"  Object '{obj.name}' HAS {len(obj.vertex_groups)} vertex group(s). Checking weights...")
            for v_bm in bm.verts:
                v_idx = v_bm.index
                vertex_has_significant_weight = False
                
                for vg in obj.vertex_groups:
                    try:
                        weight = vg.weight(v_idx)
                        if weight > threshold:
                            vertex_has_significant_weight = True
                            break
                    except RuntimeError:
                        continue
                    except IndexError:
                        # print(f"    IndexError for v_idx {v_idx} in group '{vg.name}'. Skipping group for this vertex.")
                        continue
                
                if vertex_has_significant_weight:
                    v_bm.hide = True
                    verts_hidden_count += 1
                else:
                    v_bm.hide = False
                    verts_shown_count += 1
        
        # print(f"  Vertex processing complete: Hidden={verts_hidden_count}, Shown={verts_shown_count}")

        edges_hidden_count = 0
        for e_bm in bm.edges:
            if all(v_edge.hide for v_edge in e_bm.verts):
                e_bm.hide = True
                edges_hidden_count +=1
            else:
                e_bm.hide = False
        # print(f"  Edges updated: Hidden={edges_hidden_count}")

        faces_hidden_count = 0
        for f_bm in bm.faces:
            if all(v_face.hide for v_face in f_bm.verts):
                f_bm.hide = True
                faces_hidden_count +=1
            else:
                f_bm.hide = False
        # print(f"  Faces updated: Hidden={faces_hidden_count}")

        bm.to_mesh(obj.data)
        bm.free()
        # print(f"  Bmesh data written back to '{obj.name}.data' and freed.")

        obj.data.update()
        # print(f"  '{obj.name}.data.update()' called.")

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        # print(f"  Switched back to EDIT mode for object '{obj.name}'.")
        
        self.report({'INFO'}, f"网格 '{obj.name}': {verts_hidden_count} 个顶点被隐藏, {verts_shown_count} 个顶点保持可见.")
        # print("--- MESH_OT_isolate_zero_weight_meshes EXECUTE (Vertex-Level Hide) END ---")
        return {'FINISHED'}

class MQT_PT_MeshWeightDisplayPanel(Panel):
    bl_label = "网格权重显示"
    bl_idname = "MQT_PT_MeshWeightDisplayPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        # Ensure settings exist, might not if script is reloaded without full re-register
        if hasattr(context.scene, 'mq_mesh_weight_settings'):
            settings = context.scene.mq_mesh_weight_settings
            box = layout.box()
            col = box.column(align=True)
            col.prop(settings, "zero_weight_threshold")
            col.operator(MESH_OT_isolate_zero_weight_meshes.bl_idname, text="隔离零权重网格", icon='FILTER')
        else:
            layout.label(text="设置未加载，请尝试重新加载插件。")


# --------------------------------------------------------------------------
# MMD材质转换工具
# --------------------------------------------------------------------------

def create_mmd_basic_shader():
    """创建MMDBasicShader节点组"""
    if "MMDBasicShader" in bpy.data.node_groups:
        return bpy.data.node_groups["MMDBasicShader"]
    
    # 创建节点组
    node_group = bpy.data.node_groups.new(name="MMDBasicShader", type='ShaderNodeTree')
    
    # 创建输入和输出节点
    group_inputs = node_group.nodes.new('NodeGroupInput')
    group_outputs = node_group.nodes.new('NodeGroupOutput')
    
    # 添加输入接口
    node_group.interface.new_socket(name="Diffuse Color", in_out='INPUT', socket_type='NodeSocketColor')
    node_group.interface.new_socket(name="Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    node_group.interface.new_socket(name="Ambient Color", in_out='INPUT', socket_type='NodeSocketColor')
    node_group.interface.new_socket(name="Specular Color", in_out='INPUT', socket_type='NodeSocketColor')
    node_group.interface.new_socket(name="Shininess", in_out='INPUT', socket_type='NodeSocketFloat')
    node_group.interface.new_socket(name="Texture", in_out='INPUT', socket_type='NodeSocketColor')
    node_group.interface.new_socket(name="Texture Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    
    # 添加输出接口
    node_group.interface.new_socket(name="Shader", in_out='OUTPUT', socket_type='NodeSocketShader')
    
    # 创建Principled BSDF节点
    principled = node_group.nodes.new('ShaderNodeBsdfPrincipled')
    
    # 创建混合节点用于纹理和漫反射颜色
    mix_rgb = node_group.nodes.new('ShaderNodeMix')
    mix_rgb.data_type = 'RGBA'
    mix_rgb.blend_type = 'MULTIPLY'
    mix_rgb.inputs['Fac'].default_value = 1.0
    
    # 创建数学节点用于alpha计算
    math_multiply = node_group.nodes.new('ShaderNodeMath')
    math_multiply.operation = 'MULTIPLY'
    
    # 连接节点
    node_group.links.new(group_inputs.outputs['Diffuse Color'], mix_rgb.inputs['Color1'])
    node_group.links.new(group_inputs.outputs['Texture'], mix_rgb.inputs['Color2'])
    node_group.links.new(mix_rgb.outputs['Color'], principled.inputs['Base Color'])
    
    node_group.links.new(group_inputs.outputs['Alpha'], math_multiply.inputs[0])
    node_group.links.new(group_inputs.outputs['Texture Alpha'], math_multiply.inputs[1])
    node_group.links.new(math_multiply.outputs['Value'], principled.inputs['Alpha'])
    
    node_group.links.new(group_inputs.outputs['Specular Color'], principled.inputs['Specular Tint'])
    node_group.links.new(principled.outputs['BSDF'], group_outputs.inputs['Shader'])
    
    # 设置节点位置
    group_inputs.location = (-400, 0)
    mix_rgb.location = (-200, 100)
    math_multiply.location = (-200, -100)
    principled.location = (0, 0)
    group_outputs.location = (200, 0)
    
    return node_group

def create_mmd_alpha_shader():
    """创建MMDAlphaShader节点组"""
    if "MMDAlphaShader" in bpy.data.node_groups:
        return bpy.data.node_groups["MMDAlphaShader"]
    
    # 创建节点组
    node_group = bpy.data.node_groups.new(name="MMDAlphaShader", type='ShaderNodeTree')
    
    # 创建输入和输出节点
    group_inputs = node_group.nodes.new('NodeGroupInput')
    group_outputs = node_group.nodes.new('NodeGroupOutput')
    
    # 添加输入接口
    node_group.interface.new_socket(name="Shader", in_out='INPUT', socket_type='NodeSocketShader')
    node_group.interface.new_socket(name="Alpha", in_out='INPUT', socket_type='NodeSocketFloat')
    
    # 添加输出接口
    node_group.interface.new_socket(name="Shader", in_out='OUTPUT', socket_type='NodeSocketShader')
    
    # 创建透明BSDF节点
    transparent = node_group.nodes.new('ShaderNodeBsdfTransparent')
    
    # 创建混合着色器节点
    mix_shader = node_group.nodes.new('ShaderNodeMixShader')
    
    # 连接节点
    node_group.links.new(group_inputs.outputs['Alpha'], mix_shader.inputs['Fac'])
    node_group.links.new(transparent.outputs['BSDF'], mix_shader.inputs[1])
    node_group.links.new(group_inputs.outputs['Shader'], mix_shader.inputs[2])
    node_group.links.new(mix_shader.outputs['Shader'], group_outputs.inputs['Shader'])
    
    # 设置节点位置
    group_inputs.location = (-300, 0)
    transparent.location = (-100, 100)
    mix_shader.location = (100, 0)
    group_outputs.location = (300, 0)
    
    return node_group

class MMD_OT_convert_materials_to_blender(bpy.types.Operator):
    """将MMD材质转换为Blender材质"""
    bl_idname = "mmd.convert_materials_to_blender"
    bl_label = "转换为Blender材质"
    bl_description = "将选中对象的MMD材质转换为Blender Principled BSDF材质"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        converted_count = 0
        error_count = 0
        skipped_count = 0
        
        for obj in context.selected_objects:
            if obj.type != 'MESH' or not obj.data.materials:
                continue
                
            for material in obj.data.materials:
                if not material:
                    continue
                    
                if not material.use_nodes:
                    skipped_count += 1
                    continue
                    
                # 检查是否已经是MMD材质
                has_mmd_nodes = any(node.name.startswith('mmd_') or 
                                  node.bl_idname in ['ShaderNodeGroup'] and 
                                  node.node_tree and node.node_tree.name in ['MMDBasicShader', 'MMDShaderDev']
                                  for node in material.node_tree.nodes)
                
                if not has_mmd_nodes:
                    skipped_count += 1
                    continue
                
                try:
                    # 转换为Principled BSDF
                    self.convert_to_principled_bsdf(material)
                    converted_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"转换材质 '{material.name}' 时出错: {str(e)}")
        
        # 生成详细的报告信息
        if converted_count > 0:
            self.report({'INFO'}, f"成功转换 {converted_count} 个MMD材质")
        if skipped_count > 0:
            self.report({'WARNING'}, f"跳过 {skipped_count} 个非MMD材质或未启用节点的材质")
        if error_count > 0:
            self.report({'ERROR'}, f"转换失败 {error_count} 个材质，请检查控制台错误信息")
        
        if converted_count == 0 and skipped_count == 0 and error_count == 0:
            self.report({'WARNING'}, "未找到可转换的材质")
        
        return {'FINISHED'}
    
    def convert_to_principled_bsdf(self, material):
        """将MMD材质转换为Principled BSDF"""
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # 查找MMD节点组
        mmd_shader_node = None
        mmd_alpha_node = None
        mmd_tex_uv_node = None
        
        for node in nodes:
            if (node.bl_idname == 'ShaderNodeGroup' and node.node_tree):
                if node.node_tree.name in ['MMDBasicShader', 'MMDShaderDev']:
                    mmd_shader_node = node
                elif node.node_tree.name == 'MMDAlphaShader':
                    mmd_alpha_node = node
                elif node.node_tree.name == 'MMDTexUV':
                    mmd_tex_uv_node = node
        
        if not mmd_shader_node:
            return
        
        # 创建新的Principled BSDF节点
        principled = nodes.new('ShaderNodeBsdfPrincipled')
        principled.location = mmd_shader_node.location
        
        # 查找连接到Base Tex的图像纹理节点
        base_texture_node = None
        if 'Base Tex' in mmd_shader_node.inputs and mmd_shader_node.inputs['Base Tex'].is_linked:
            # 获取连接到Base Tex的节点
            connected_node = mmd_shader_node.inputs['Base Tex'].links[0].from_node
            if connected_node.type == 'TEX_IMAGE':
                base_texture_node = connected_node
        
        # 连接纹理到Principled BSDF
        if base_texture_node:
            # 直接连接图像纹理的Color输出到Principled BSDF的Base Color
            links.new(base_texture_node.outputs['Color'], principled.inputs['Base Color'])
            # 如果有Alpha输出，也连接到Alpha输入
            if 'Alpha' in base_texture_node.outputs and 'Alpha' in principled.inputs:
                links.new(base_texture_node.outputs['Alpha'], principled.inputs['Alpha'])
        else:
            # 如果没有纹理，使用漫反射颜色
            if 'Diffuse Color' in mmd_shader_node.inputs:
                principled.inputs['Base Color'].default_value[:3] = mmd_shader_node.inputs['Diffuse Color'].default_value[:3]
        
        # 处理Alpha值
        if 'Alpha' in mmd_shader_node.inputs:
            if 'Alpha' in principled.inputs:
                principled.inputs['Alpha'].default_value = mmd_shader_node.inputs['Alpha'].default_value
        
        # 设置其他属性
        principled.inputs['IOR'].default_value = 1.0
        if 'Subsurface Weight' in principled.inputs:
            principled.inputs['Subsurface Weight'].default_value = 0.001
        
        # 处理Alpha节点的输出连接
        output_links = list(mmd_shader_node.outputs[0].links)
        if mmd_alpha_node:
            principled.location = mmd_alpha_node.location
            output_links = list(mmd_alpha_node.outputs[0].links)
        
        # 重新连接输出到材质输出节点
        for link in output_links:
            links.new(principled.outputs['BSDF'], link.to_socket)
        
        # 清理旧的MMD节点组，但保留图像纹理节点
        nodes_to_remove = []
        for node in nodes:
            # 删除MMD相关的节点组
            if (node.bl_idname == 'ShaderNodeGroup' and 
                node.node_tree and 
                node.node_tree.name in ['MMDBasicShader', 'MMDShaderDev', 'MMDAlphaShader', 'MMDTexUV']):
                nodes_to_remove.append(node)
            # 删除以mmd_开头的节点，但保留图像纹理节点
            elif (node.name.startswith('mmd_') and 
                  node.type != 'TEX_IMAGE'):
                nodes_to_remove.append(node)
        
        for node in nodes_to_remove:
            nodes.remove(node)

class MMD_OT_convert_materials_to_cycles(bpy.types.Operator):
    """将MMD材质转换为Cycles材质"""
    bl_idname = "mmd.convert_materials_to_cycles"
    bl_label = "转换为Cycles材质"
    bl_description = "将选中对象的MMD材质转换为Cycles兼容的材质"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        try:
            # 切换到Cycles渲染引擎
            original_engine = context.scene.render.engine
            if context.scene.render.engine != 'CYCLES':
                context.scene.render.engine = 'CYCLES'
            
            # 调用Blender材质转换
            result = bpy.ops.mmd.convert_materials_to_blender()
            
            if result == {'FINISHED'}:
                if original_engine != 'CYCLES':
                    self.report({'INFO'}, f"已从 {original_engine} 切换到 Cycles 并转换材质")
                else:
                    self.report({'INFO'}, "已转换为Cycles材质")
            else:
                self.report({'WARNING'}, "材质转换可能未完全成功")
                
        except Exception as e:
            self.report({'ERROR'}, f"转换过程中出错: {str(e)}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

class MMD_OT_convert_materials_to_mmd(bpy.types.Operator):
    """将Blender材质转换为MMD材质"""
    bl_idname = "mmd.convert_materials_to_mmd"
    bl_label = "转换为MMD材质"
    bl_description = "将选中对象的Blender材质转换为MMD材质"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.selected_objects
    
    def execute(self, context):
        converted_count = 0
        error_count = 0
        skipped_count = 0
        
        try:
            # 确保MMD节点组存在
            create_mmd_basic_shader()
            create_mmd_alpha_shader()
        except Exception as e:
            self.report({'ERROR'}, f"创建MMD节点组失败: {str(e)}")
            return {'CANCELLED'}
        
        for obj in context.selected_objects:
            if obj.type != 'MESH' or not obj.data.materials:
                continue
                
            for material in obj.data.materials:
                if not material:
                    continue
                    
                # 启用节点
                if not material.use_nodes:
                    material.use_nodes = True
                
                # 检查是否已经是MMD材质
                has_mmd_nodes = any(node.name.startswith('mmd_') or 
                                  (node.bl_idname == 'ShaderNodeGroup' and 
                                   node.node_tree and 
                                   node.node_tree.name in ['MMDBasicShader', 'MMDShaderDev'])
                                  for node in material.node_tree.nodes)
                
                if has_mmd_nodes:
                    skipped_count += 1
                    continue
                
                try:
                    # 转换为MMD材质
                    self.convert_to_mmd_material(material)
                    converted_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"转换材质 '{material.name}' 时出错: {str(e)}")
        
        # 生成详细的报告信息
        if converted_count > 0:
            self.report({'INFO'}, f"成功转换 {converted_count} 个材质为MMD格式")
        if skipped_count > 0:
            self.report({'WARNING'}, f"跳过 {skipped_count} 个已经是MMD格式的材质")
        if error_count > 0:
            self.report({'ERROR'}, f"转换失败 {error_count} 个材质，请检查控制台错误信息")
        
        if converted_count == 0 and skipped_count == 0 and error_count == 0:
            self.report({'WARNING'}, "未找到可转换的材质")
        
        return {'FINISHED'}
    
    def convert_to_mmd_material(self, material):
        """将Blender材质转换为MMD材质"""
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # 查找输出节点
        output_node = None
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                break
        
        if not output_node:
            output_node = nodes.new('ShaderNodeOutputMaterial')
        
        # 查找Principled BSDF节点
        principled_node = None
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                principled_node = node
                break
        
        # 查找图像纹理节点
        image_texture_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']
        
        # 创建MMD Basic Shader节点
        mmd_basic = nodes.new('ShaderNodeGroup')
        mmd_basic.node_tree = bpy.data.node_groups['MMDBasicShader']
        mmd_basic.name = 'mmd_shader'
        mmd_basic.location = (0, 0)
        
        # 设置默认值
        mmd_basic.inputs['Diffuse Color'].default_value = (0.8, 0.8, 0.8, 1.0)
        mmd_basic.inputs['Alpha'].default_value = 1.0
        mmd_basic.inputs['Ambient Color'].default_value = (0.1, 0.1, 0.1, 1.0)
        mmd_basic.inputs['Specular Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        mmd_basic.inputs['Shininess'].default_value = 50.0
        mmd_basic.inputs['Texture'].default_value = (1.0, 1.0, 1.0, 1.0)
        mmd_basic.inputs['Texture Alpha'].default_value = 1.0
        
        # 处理纹理连接
        if image_texture_nodes:
            # 使用第一个图像纹理节点
            main_texture = image_texture_nodes[0]
            if main_texture.image:
                # 连接纹理到MMD shader
                links.new(main_texture.outputs['Color'], mmd_basic.inputs['Texture'])
                if main_texture.image.channels == 4:  # RGBA
                    links.new(main_texture.outputs['Alpha'], mmd_basic.inputs['Texture Alpha'])
        
        # 从Principled BSDF获取值
        if principled_node:
            base_color = principled_node.inputs['Base Color']
            alpha = principled_node.inputs['Alpha']
            
            # 如果Base Color有连接且不是纹理节点，连接到Diffuse Color
            if base_color.is_linked:
                source_node = base_color.links[0].from_node
                if source_node.type != 'TEX_IMAGE':  # 不是纹理节点
                    source_socket = base_color.links[0].from_socket
                    links.new(source_socket, mmd_basic.inputs['Diffuse Color'])
            else:
                # 使用默认值
                mmd_basic.inputs['Diffuse Color'].default_value = base_color.default_value
            
            # 处理Alpha
            if alpha.is_linked:
                source_node = alpha.links[0].from_node
                if source_node.type != 'TEX_IMAGE':  # 不是纹理节点
                    source_socket = alpha.links[0].from_socket
                    links.new(source_socket, mmd_basic.inputs['Alpha'])
            else:
                mmd_basic.inputs['Alpha'].default_value = alpha.default_value
        
        # 检查是否需要alpha处理
        alpha_value = mmd_basic.inputs['Alpha'].default_value if not mmd_basic.inputs['Alpha'].is_linked else 1.0
        
        if alpha_value < 1.0 or (mmd_basic.inputs['Texture Alpha'].is_linked):
            # 创建MMD Alpha Shader节点
            mmd_alpha = nodes.new('ShaderNodeGroup')
            mmd_alpha.node_tree = bpy.data.node_groups['MMDAlphaShader']
            mmd_alpha.location = (200, 0)
            
            # 连接节点
            links.new(mmd_basic.outputs['Shader'], mmd_alpha.inputs['Shader'])
            
            # 连接alpha值
            if mmd_basic.inputs['Alpha'].is_linked:
                alpha_socket = mmd_basic.inputs['Alpha'].links[0].from_socket
                links.new(alpha_socket, mmd_alpha.inputs['Alpha'])
            else:
                mmd_alpha.inputs['Alpha'].default_value = alpha_value
            
            links.new(mmd_alpha.outputs['Shader'], output_node.inputs['Surface'])
        else:
            # 直接连接到输出
            links.new(mmd_basic.outputs['Shader'], output_node.inputs['Surface'])
        
        # 清理旧的Principled BSDF节点
        if principled_node:
            nodes.remove(principled_node)

class MQT_PT_MMDMaterialPanel(bpy.types.Panel):
    """MMD材质转换面板"""
    bl_label = "MMD材质转换"
    bl_idname = "MQT_PT_MMDMaterialPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 添加说明
        info_box = layout.box()
        info_box.label(text="MMD材质转换工具", icon='MATERIAL')
        info_box.label(text="选择对象后点击转换按钮")
        
        # 检查选中对象
        if not context.selected_objects:
            warning_box = layout.box()
            warning_box.label(text="请先选择要转换的对象", icon='ERROR')
        else:
            # 统计材质信息
            total_materials = 0
            mmd_materials = 0
            blender_materials = 0
            
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.data.materials:
                    for material in obj.data.materials:
                        if material and material.use_nodes:
                            total_materials += 1
                            has_mmd_nodes = any(node.name.startswith('mmd_') or 
                                              (node.bl_idname == 'ShaderNodeGroup' and 
                                               node.node_tree and 
                                               node.node_tree.name in ['MMDBasicShader', 'MMDShaderDev'])
                                              for node in material.node_tree.nodes)
                            if has_mmd_nodes:
                                mmd_materials += 1
                            else:
                                blender_materials += 1
            
            # 显示材质统计
            stats_box = layout.box()
            stats_box.label(text=f"材质统计: 总计 {total_materials}")
            stats_box.label(text=f"MMD材质: {mmd_materials}")
            stats_box.label(text=f"Blender材质: {blender_materials}")
        
        # 转换按钮
        col = layout.column(align=True)
        col.operator(MMD_OT_convert_materials_to_blender.bl_idname, 
                    text="转换为Blender材质", icon='MATERIAL')
        col.operator(MMD_OT_convert_materials_to_cycles.bl_idname, 
                    text="转换为Cycles材质", icon='SHADING_RENDERED')
        col.operator(MMD_OT_convert_materials_to_mmd.bl_idname, 
                    text="转换为MMD材质", icon='MESH_DATA')
        
        # 当前渲染引擎信息
        layout.separator()
        box = layout.box()
        box.label(text=f"当前渲染引擎: {context.scene.render.engine}")
        
        # 使用提示
        layout.separator()
        tips_box = layout.box()
        tips_box.label(text="使用提示:", icon='INFO')
        tips_box.label(text="• 转换前请备份文件")
        tips_box.label(text="• 确保材质已启用节点")
        tips_box.label(text="• 纹理将自动保留连接")


# --------------------------------------------------------------------------
# 工具 9: 静态对象GLB2.0导出
# --------------------------------------------------------------------------

class StaticGLBExportSettings(PropertyGroup):
    """静态对象GLB导出设置"""
    export_path: StringProperty(
        name="导出路径",
        description="选择GLB文件的导出路径",
        subtype='FILE_PATH',
        default="//static_export.glb"
    )
    
    target_collection: PointerProperty(
        type=bpy.types.Collection,
        name="目标集合",
        description="选择要导出的总集合"
    )
    
    apply_pose: BoolProperty(
        name="应用姿态",
        description="导出时应用当前骨架姿态",
        default=True
    )
    
    apply_shapekeys: BoolProperty(
        name="应用形态键",
        description="导出时应用当前形态键设置",
        default=True
    )
    
    export_materials: BoolProperty(
        name="导出材质",
        description="导出材质信息（不包含贴图）",
        default=True
    )
    
    export_textures: BoolProperty(
        name="导出贴图",
        description="导出贴图文件",
        default=False
    )

class STATIC_OT_export_glb(Operator):
    """静态对象GLB2.0导出操作"""
    bl_idname = "static.export_glb"
    bl_label = "导出静态GLB"
    bl_description = "根据集合导出静态GLB文件，应用姿态和形态键"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        settings = context.scene.static_glb_settings
        return settings.target_collection is not None
    
    def execute(self, context):
        settings = context.scene.static_glb_settings
        
        if not settings.target_collection:
            self.report({'ERROR'}, "请选择要导出的目标集合")
            return {'CANCELLED'}
        
        if not settings.export_path:
            self.report({'ERROR'}, "请设置导出路径")
            return {'CANCELLED'}
        
        try:
            # 保存当前选择状态
            original_selection = list(context.selected_objects)
            original_active = context.active_object
            
            # 收集目标集合中的所有对象
            target_objects = self.collect_objects_from_collection(settings.target_collection)
            
            if not target_objects:
                self.report({'WARNING'}, "目标集合中没有找到可导出的对象")
                return {'CANCELLED'}
            
            # 清除选择并选择目标对象
            bpy.ops.object.select_all(action='DESELECT')
            for obj in target_objects:
                obj.select_set(True)
            
            if target_objects:
                context.view_layer.objects.active = target_objects[0]
            
            # 创建临时副本用于处理
            temp_objects = []
            if settings.apply_pose or settings.apply_shapekeys:
                temp_objects = self.create_temp_copies(context, target_objects, settings)
            else:
                temp_objects = target_objects
            
            # 选择处理后的对象
            bpy.ops.object.select_all(action='DESELECT')
            for obj in temp_objects:
                obj.select_set(True)
            
            if temp_objects:
                context.view_layer.objects.active = temp_objects[0]
            

            
            # 设置导出参数
            export_path = bpy.path.abspath(settings.export_path)
            
            # 设置活动集合为目标集合
            def find_layer_collection(layer_collection, collection_name):
                if layer_collection.collection.name == collection_name:
                    return layer_collection
                for child in layer_collection.children:
                    result = find_layer_collection(child, collection_name)
                    if result:
                        return result
                return None
            
            target_layer_collection = find_layer_collection(context.view_layer.layer_collection, settings.target_collection.name)
            if target_layer_collection:
                context.view_layer.active_layer_collection = target_layer_collection
            
            # 执行GLB导出
            bpy.ops.export_scene.gltf(
                filepath=export_path,
                use_selection=True,  # 只导出选中的对象
                export_format='GLB',
                export_materials='EXPORT' if settings.export_materials else 'NONE',  # 导出材质但不包含贴图
                export_unused_textures=False,  # 不导出未使用的贴图文件
                export_image_format='NONE',  # 不导出图像
                export_hierarchy_full_collections=True,  # 完整的集合层次结构
                export_morph_normal=False,  # 关闭形态键法向导出
                export_animations=False,
                export_skins=False,  # 不导出骨架
                export_apply=True  # 应用修改器
            )
            

            
            # 清理临时对象并清空未使用数据
            if settings.apply_pose or settings.apply_shapekeys:
                self.cleanup_temp_objects(temp_objects)
                # 清空未使用的数据块
                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
            
            # 恢复原始选择
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selection:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)
            
            if original_active and original_active.name in bpy.data.objects:
                context.view_layer.objects.active = original_active
            
            self.report({'INFO'}, f"成功导出静态GLB文件: {export_path}")
            return {'FINISHED'}
            
        except Exception as e:
            # 清理临时对象（如果创建了的话）
            if 'temp_objects' in locals() and settings.apply_pose or settings.apply_shapekeys:
                self.cleanup_temp_objects(temp_objects)
            
            # 恢复原始选择
            if 'original_selection' in locals():
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selection:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            
            if 'original_active' in locals() and original_active and original_active.name in bpy.data.objects:
                context.view_layer.objects.active = original_active
            
            self.report({'ERROR'}, f"导出失败: {str(e)}")
            return {'CANCELLED'}
    
    def collect_objects_from_collection(self, collection):
        """递归收集集合中的所有网格对象"""
        objects = []
        
        # 收集当前集合中的网格对象
        for obj in collection.objects:
            if obj.type == 'MESH':
                objects.append(obj)
        
        # 递归收集子集合中的对象
        for child_collection in collection.children:
            objects.extend(self.collect_objects_from_collection(child_collection))
        
        return objects
    
    def create_temp_copies(self, context, objects, settings):
        """创建对象的临时副本并应用修改器和形态键"""
        temp_objects = []
        self.original_objects = []  # 记录原始对象信息
        
        for obj in objects:
            if obj.type != 'MESH':
                continue
            
            # 记录原始对象的名称
            original_name = obj.name
            
            # 复制对象
            temp_obj = obj.copy()
            temp_obj.data = obj.data.copy()
            
            # 将原始名称给临时对象
            temp_obj.name = original_name
            
            # 修改原始对象的名称以释放名称占用
            obj.name = f"{original_name}_original_hidden"
            
            # 记录原始对象所在的集合
            original_collections = list(obj.users_collection)
            
            # 将临时对象链接到原始对象所在的集合
            for collection in original_collections:
                collection.objects.link(temp_obj)
            
            # 确保临时对象至少在一个集合中
            if not temp_obj.users_collection:
                bpy.context.collection.objects.link(temp_obj)
            
            # 隐藏原始对象但不从集合中移除
            try:
                obj.hide_set(True)
            except:
                pass  # 忽略隐藏失败的情况
            
            # 记录原始对象信息用于后续恢复
            self.original_objects.append({
                'obj': obj,
                'collections': original_collections,
                'original_name': original_name,  # 保存真正的原始名称
                'temp_obj': temp_obj
            })
            
            # 对于有形态键的对象，需要特殊处理以保留姿态
            has_shape_keys = settings.apply_shapekeys and temp_obj.data.shape_keys
            has_armature = settings.apply_pose and any(mod.type == 'ARMATURE' for mod in temp_obj.modifiers)
            
            if has_shape_keys and has_armature:
                # 有形态键和骨架的对象：必须先应用形态键，再应用骨架修改器
                context.view_layer.objects.active = temp_obj
                bpy.ops.object.select_all(action='DESELECT')
                temp_obj.select_set(True)
                
                # 先应用形态键
                try:
                    bpy.ops.object.shape_key_add(from_mix=True)
                    # 删除原始形态键
                    while temp_obj.data.shape_keys and len(temp_obj.data.shape_keys.key_blocks) > 1:
                        temp_obj.active_shape_key_index = 0
                        bpy.ops.object.shape_key_remove()
                except:
                    pass  # 忽略形态键处理失败
                    
                # 然后应用骨架修改器
                for modifier in temp_obj.modifiers:
                    if modifier.type == 'ARMATURE':
                        try:
                            bpy.ops.object.modifier_apply(modifier=modifier.name)
                        except:
                            pass  # 忽略应用失败的修改器
                            
            elif has_armature:
                # 只有骨架修改器的对象
                context.view_layer.objects.active = temp_obj
                bpy.ops.object.select_all(action='DESELECT')
                temp_obj.select_set(True)
                
                for modifier in temp_obj.modifiers:
                    if modifier.type == 'ARMATURE':
                        try:
                            bpy.ops.object.modifier_apply(modifier=modifier.name)
                        except:
                            pass  # 忽略应用失败的修改器
                            
            elif has_shape_keys:
                # 只有形态键的对象
                context.view_layer.objects.active = temp_obj
                bpy.ops.object.select_all(action='DESELECT')
                temp_obj.select_set(True)
                
                try:
                    bpy.ops.object.shape_key_add(from_mix=True)
                    # 删除原始形态键
                    while temp_obj.data.shape_keys and len(temp_obj.data.shape_keys.key_blocks) > 1:
                        temp_obj.active_shape_key_index = 0
                        bpy.ops.object.shape_key_remove()
                except:
                    pass  # 忽略形态键处理失败
            
            temp_objects.append(temp_obj)
        
        return temp_objects
    
    def cleanup_temp_objects(self, temp_objects):
        """清理临时对象"""
        # 删除临时对象
        for obj in temp_objects:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        
        # 恢复原始对象的可见性和名称
        if hasattr(self, 'original_objects'):
            for obj_info in self.original_objects:
                original_obj = obj_info['obj']
                original_name = obj_info['original_name']
                
                # 恢复原始名称
                try:
                    original_obj.name = original_name
                except:
                    pass  # 忽略名称恢复失败的情况
                
                # 恢复可见性
                try:
                    original_obj.hide_set(False)
                except:
                    pass  # 忽略恢复可见性失败的情况
            
            # 清理记录
            self.original_objects = []

class MQT_PT_StaticGLBExportPanel(Panel):
    """静态对象GLB导出面板"""
    bl_label = "静态对象GLB导出"
    bl_idname = "MQT_PT_StaticGLBExportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.static_glb_settings
        
        # 功能说明
        info_box = layout.box()
        info_box.label(text="静态对象GLB导出", icon='EXPORT')
        info_box.label(text="应用姿态和形态键后导出")
        
        # 基本设置
        main_box = layout.box()
        main_box.label(text="导出设置:", icon='SETTINGS')
        
        # 目标集合选择
        main_box.prop_search(settings, "target_collection", bpy.data, "collections", text="目标集合")
        
        # 导出路径
        main_box.prop(settings, "export_path", text="导出路径")
        
        # 处理选项
        process_box = layout.box()
        process_box.label(text="处理选项:", icon='MODIFIER')
        process_box.prop(settings, "apply_pose", text="应用骨架姿态")
        process_box.prop(settings, "apply_shapekeys", text="应用形态键")
        
        # 导出选项
        export_box = layout.box()
        export_box.label(text="导出选项:", icon='MATERIAL')
        export_box.prop(settings, "export_materials", text="导出材质")
        export_box.prop(settings, "export_textures", text="导出贴图")
        
        # 集合信息显示
        if settings.target_collection:
            info_box = layout.box()
            info_box.label(text="集合信息:", icon='INFO')
            
            # 统计对象数量
            mesh_count = 0
            total_count = 0
            
            def count_objects(collection):
                nonlocal mesh_count, total_count
                for obj in collection.objects:
                    total_count += 1
                    if obj.type == 'MESH':
                        mesh_count += 1
                for child in collection.children:
                    count_objects(child)
            
            count_objects(settings.target_collection)
            
            info_box.label(text=f"网格对象: {mesh_count}")
            info_box.label(text=f"总对象数: {total_count}")
        
        # 导出按钮
        layout.separator()
        export_row = layout.row()
        export_row.scale_y = 1.5
        export_row.operator(STATIC_OT_export_glb.bl_idname, text="导出静态GLB", icon='EXPORT')
        
        # 使用说明
        layout.separator()
        tips_box = layout.box()
        tips_box.label(text="使用说明:", icon='INFO')
        tips_box.label(text="• 选择包含所有内容的总集合")
        tips_box.label(text="• 自动应用骨架修改器和形态键")
        tips_box.label(text="• 保持完整的集合层次结构")
        tips_box.label(text="• 默认关闭形态键法向导出")

# --------------------------------------------------------------------------
# 工具 10: 绝地潜兵2MOD制作工具
# --------------------------------------------------------------------------

class HELLDIVERS2_OT_ProcessModel(Operator):
    """绝地潜兵2MOD制作：删除模型只剩一个面并缩小到1%"""
    bl_idname = "helldivers2.process_model"
    bl_label = "处理选中模型"
    bl_description = "将选中的模型删除只剩一个面，然后缩小到1%"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # 获取当前选中的对象
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'WARNING'}, "请先选择至少一个网格对象")
            return {'CANCELLED'}
        
        processed_count = 0
        
        for obj in selected_objects:
            try:
                # 确保对象是网格类型
                if obj.type != 'MESH':
                    continue
                
                # 进入编辑模式
                context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')
                
                # 选择所有面
                bpy.ops.mesh.select_all(action='SELECT')
                
                # 获取bmesh表示
                bm = bmesh.from_mesh(obj.data)
                
                # 确保面索引有效
                bm.faces.ensure_lookup_table()
                
                # 如果有面，保留第一个面，删除其他所有面
                if len(bm.faces) > 1:
                    # 取消选择所有面
                    for face in bm.faces:
                        face.select = False
                    
                    # 选择除第一个面之外的所有面
                    for i in range(1, len(bm.faces)):
                        if i < len(bm.faces):
                            bm.faces[i].select = True
                    
                    # 更新网格
                    bmesh.update_edit_mesh(obj.data)
                    
                    # 删除选中的面
                    bpy.ops.mesh.delete(type='FACE')
                
                # 退出编辑模式
                bpy.ops.object.mode_set(mode='OBJECT')
                
                # 缩放到1%
                obj.scale = (0.01, 0.01, 0.01)
                
                processed_count += 1
                
            except Exception as e:
                self.report({'ERROR'}, f"处理对象 {obj.name} 时出错: {str(e)}")
                # 确保退出编辑模式
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass
                continue
        
        if processed_count > 0:
            self.report({'INFO'}, f"成功处理了 {processed_count} 个对象")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "没有成功处理任何对象")
            return {'CANCELLED'}

class MQT_PT_Helldivers2Panel(Panel):
    """绝地潜兵2MOD制作面板"""
    bl_label = "绝地潜兵2MOD制作分支"
    bl_idname = "MQT_PT_Helldivers2Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        
        # 添加关于信息
        info_box = layout.box()
        info_box.label(text="绝地潜兵2MOD制作工具", icon='MODIFIER_DATA')
        info_box.label(text="适用于Blender 4.5+")
        info_box.label(text="作者: 地狱酱")
        
        # 主要功能区
        main_box = layout.box()
        main_box.label(text="模型处理工具:", icon='MESH_DATA')
        
        # 使用说明
        tips_box = main_box.box()
        tips_box.label(text="使用说明:", icon='INFO')
        tips_box.label(text="• 在物体模式下选择要处理的模型")
        tips_box.label(text="• 点击下方按钮自动处理")
        tips_box.label(text="• 将删除模型只剩一个面")
        tips_box.label(text="• 并将模型缩放至1%")
        
        # 主操作按钮
        main_box.operator(HELLDIVERS2_OT_ProcessModel.bl_idname, 
                         text="处理选中模型", 
                         icon='MOD_EXPLODE')
        
        # 警告信息
        warning_box = layout.box()
        warning_box.label(text="⚠️ 注意事项:", icon='ERROR')
        warning_box.label(text="• 此操作不可撤销，请先备份")
        warning_box.label(text="• 仅适用于绝地潜兵2MOD制作")
        warning_box.label(text="• 确保在物体模式下操作")
        
        # 版本兼容性说明
        compat_box = layout.box()
        compat_box.label(text="📋 版本说明:", icon='TEXT')
        compat_box.label(text="• 主插件支持Blender 4.5+")
        compat_box.label(text="• 如需4.0版本，请使用独立分支")

# --------------------------------------------------------------------------
# 面数排行榜（实时）
# --------------------------------------------------------------------------

FACE_COUNT_CACHE = []
FACE_COUNT_CACHE_TIMESTAMP = 0.0

class FaceCountSettings(bpy.types.PropertyGroup):
    include_hidden: bpy.props.BoolProperty(
        name="包含隐藏对象",
        description="统计时包含当前不可见的对象",
        default=False
    )
    limit: bpy.props.IntProperty(
        name="显示数量",
        description="排行榜显示的对象数量",
        default=20,
        min=1, max=9999
    )
    realtime_enable: bpy.props.BoolProperty(
        name="实时更新",
        description="自动定时刷新排行榜",
        default=True
    )
    update_interval: bpy.props.FloatProperty(
        name="刷新间隔(秒)",
        description="实时更新时的刷新时间间隔",
        default=1.0, min=0.1, max=10.0
    )
    filter_collection: bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="过滤集合",
        description="只统计该集合及其子集合内的对象"
    )


def _collect_objects_in_collection(col, out):
    out.extend([o for o in col.objects])
    for child in col.children:
        _collect_objects_in_collection(child, out)


def compute_face_counts(context, settings):
    depsgraph = context.evaluated_depsgraph_get()
    objs = []
    if settings.filter_collection:
        _collect_objects_in_collection(settings.filter_collection, objs)
    else:
        objs = [o for o in context.view_layer.objects]

    results = []
    for obj in objs:
        if obj.type != 'MESH':
            continue
        if not settings.include_hidden and not obj.visible_get():
            continue
        try:
            obj_eval = obj.evaluated_get(depsgraph)
            me = obj_eval.to_mesh()
            face_count = len(me.polygons) if me is not None else 0
            if me is not None:
                obj_eval.to_mesh_clear()
            results.append((obj.name, face_count))
        except Exception:
            # 忽略无法评估的对象
            continue

    # 去重（按对象名）
    uniq = {}
    for name, cnt in results:
        if name not in uniq or cnt > uniq[name]:
            uniq[name] = cnt

    # 排序并限制
    sorted_list = sorted([(n, c) for n, c in uniq.items()], key=lambda x: x[1], reverse=True)
    return sorted_list[:settings.limit]


class MQT_OT_RefreshFaceCounts(bpy.types.Operator):
    bl_idname = "mqtools.refresh_face_counts"
    bl_label = "刷新排行榜"
    bl_description = "立即重新统计面数并更新排行榜"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global FACE_COUNT_CACHE, FACE_COUNT_CACHE_TIMESTAMP
        settings = context.scene.mq_face_count_settings
        FACE_COUNT_CACHE = compute_face_counts(context, settings)
        FACE_COUNT_CACHE_TIMESTAMP = time.time()
        return {'FINISHED'}


class MQT_PT_FaceCountPanel(bpy.types.Panel):
    bl_label = "面数排行榜"
    bl_idname = "MQT_PT_FaceCountPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        global FACE_COUNT_CACHE, FACE_COUNT_CACHE_TIMESTAMP
        layout = self.layout
        settings = context.scene.mq_face_count_settings

        # 设置区域
        box = layout.box()
        row = box.row(align=True)
        row.prop(settings, "realtime_enable", text="实时更新")
        row.prop(settings, "include_hidden", text="包含隐藏对象")
        row = box.row(align=True)
        row.prop(settings, "update_interval", text="刷新间隔(秒)")
        row.prop(settings, "limit", text="显示数量")
        box.prop_search(settings, "filter_collection", bpy.data, "collections", text="过滤集合")

        # 实时刷新（考虑修改器）
        if settings.realtime_enable:
            now = time.time()
            if now - FACE_COUNT_CACHE_TIMESTAMP >= max(settings.update_interval, 0.1):
                FACE_COUNT_CACHE = compute_face_counts(context, settings)
                FACE_COUNT_CACHE_TIMESTAMP = now
        elif not FACE_COUNT_CACHE:
            FACE_COUNT_CACHE = compute_face_counts(context, settings)
            FACE_COUNT_CACHE_TIMESTAMP = time.time()

        # 显示排行榜
        list_box = layout.box()
        list_box.label(text="对象面数排行(考虑修改器):", icon='MESH_DATA')
        if FACE_COUNT_CACHE:
            for idx, (name, cnt) in enumerate(FACE_COUNT_CACHE, start=1):
                row = list_box.row()
                row.label(text=f"{idx}. {name}")
                row.label(text=f"面数: {cnt}")
        else:
            list_box.label(text="没有可统计的网格对象", icon='INFO')

        # 操作
        layout.operator(MQT_OT_RefreshFaceCounts.bl_idname, icon='FILE_REFRESH')

# --------------------------------------------------------------------------
# 精简修改器实时显示切换
# --------------------------------------------------------------------------

class DecimateToggleSettings(bpy.types.PropertyGroup):
    only_selected: bpy.props.BoolProperty(
        name="仅选中对象",
        description="只处理当前选中的对象",
        default=False
    )
    include_hidden: bpy.props.BoolProperty(
        name="包含隐藏对象",
        description="处理时包含不可见对象",
        default=False
    )
    filter_collection: bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="过滤集合",
        description="只处理该集合及其子集合内的对象"
    )


def _gather_target_objects(context, settings: DecimateToggleSettings):
    objs = []
    if settings.only_selected:
        objs = [o for o in context.selected_objects]
    elif settings.filter_collection:
        _collect_objects_in_collection(settings.filter_collection, objs)
    else:
        objs = [o for o in context.view_layer.objects]

    filtered = []
    for obj in objs:
        if obj.type != 'MESH':
            continue
        if not settings.include_hidden and not obj.visible_get():
            continue
        filtered.append(obj)
    return filtered


class DECIMATE_OT_EnableViewportAll(bpy.types.Operator):
    bl_idname = "mqtools.decimate_enable_viewport"
    bl_label = "开启全部实时显示"
    bl_description = "为所有 Decimate 修改器开启视图中显示"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.decimate_toggle_settings
        targets = _gather_target_objects(context, settings)
        count = 0
        for obj in targets:
            for mod in obj.modifiers:
                if mod.type == 'DECIMATE':
                    if not getattr(mod, 'show_viewport', True):
                        try:
                            mod.show_viewport = True
                            count += 1
                        except Exception:
                            pass
        self.report({'INFO'}, f"已开启 {count} 个 Decimate 修改器的视图显示")
        return {'FINISHED'}


class DECIMATE_OT_DisableViewportAll(bpy.types.Operator):
    bl_idname = "mqtools.decimate_disable_viewport"
    bl_label = "关闭全部实时显示"
    bl_description = "为所有 Decimate 修改器关闭视图中显示"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.decimate_toggle_settings
        targets = _gather_target_objects(context, settings)
        count = 0
        for obj in targets:
            for mod in obj.modifiers:
                if mod.type == 'DECIMATE':
                    if getattr(mod, 'show_viewport', True):
                        try:
                            mod.show_viewport = False
                            count += 1
                        except Exception:
                            pass
        self.report({'INFO'}, f"已关闭 {count} 个 Decimate 修改器的视图显示")
        return {'FINISHED'}


class MQT_PT_DecimateTogglePanel(bpy.types.Panel):
    bl_label = "精简修改器实时显示控制"
    bl_idname = "MQT_PT_DecimateTogglePanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MQ Tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.decimate_toggle_settings

        box = layout.box()
        box.label(text="作用范围设置:", icon='FILTER')
        row = box.row(align=True)
        row.prop(settings, "only_selected", text="仅选中对象")
        row.prop(settings, "include_hidden", text="包含隐藏对象")
        box.prop_search(settings, "filter_collection", bpy.data, "collections", text="过滤集合")

        row = layout.row(align=True)
        row.operator(DECIMATE_OT_EnableViewportAll.bl_idname, icon='CHECKMARK')
        row.operator(DECIMATE_OT_DisableViewportAll.bl_idname, icon='X')

# --------------------------------------------------------------------------
# 类注册和注销
# --------------------------------------------------------------------------

# (其他类的注册保持不变)

classes = (
    # 快速拆分助手相关类
    ExcludedItem,
    ExcludedMaterial,
    MaterialBlankControl,
    QSeparatorSettings,
    QSEPARATOR_OT_CopyText,
    QSEPARATOR_OT_CopyDefineVariable,
    QSEPARATOR_OT_AddSearchItem,
    QSEPARATOR_OT_RemoveSearchItem,
    QSEPARATOR_OT_ClearAllItems,
    QSEPARATOR_OT_OptimizeMaterialNames,
    QSEPARATOR_OT_QuickSeparate,
    QSEPARATOR_OT_MMDSeparate,
    QSEPARATOR_OT_SelectItem,
    QSEPARATOR_OT_AddMaterialItem,
    QSEPARATOR_OT_RemoveMaterialItem,
    QSEPARATOR_OT_ClearAllMaterials,
    QSEPARATOR_OT_AddBlankControlItem,
    QSEPARATOR_OT_RemoveBlankControlItem,
    QSEPARATOR_OT_ClearAllBlankControls,
    QSEPARATOR_OT_OrganizeOutlines,
    MQT_PT_SeparatorPanel,
    QS_UL_ExcludedItems,
    QS_UL_BlankControlItems,
    
    # 安全拆分面板
    MQT_PT_SafeSeparatePanel,
    
    # 快速选择骨骼相关类
    BONE_OT_SelectBonesByKeyword,
    MQT_PT_BoneSelectorPanel,
    
    # 一键描边相关类
    OUTLINE_OT_AddAll,
    OUTLINE_OT_AddSelected,
    OUTLINE_OT_DeleteAll,
    OUTLINE_OT_CopySMD,
    MQT_PT_OutlinePanel,
    
    # 清除骨骼形状相关类
    BONE_OT_ClearCustomShapes,
    MQT_PT_BoneShapePanel,
    
    # VMT材质批量复制工具相关类
    MaterialGroupItem,
    VMT_OT_RefreshList,
    VMT_OT_AssignSource,
    VMT_OT_CopyMaterials,
    VMT_OT_SelectAll,
    VMT_OT_DeselectAll,
    MQT_PT_VMTPanel,
    
    # 骨骼工具相关类
    BONE_OT_merge_to_parent,
    BONE_OT_merge_to_active,
    BONE_OT_merge_siblings_half,
    BONE_OT_remove_zero_weight,
    BONE_OT_remove_constraints,
    OBJECT_OT_RemoveRigidbodiesJoints,
    BONE_OT_apply_pose_transform,
    BONE_OT_GFL2_preprocess,
    BONE_OT_mmd_quick_merge,
    BONE_OT_unlock_all_transforms,
    RenamePrimarySettings,
    BONE_OT_rename_primary_bones,
    MQT_PT_BoneToolsPanel,
    
    # 骨骼捕捉相关类
    BoneCaptureSettings,
    BONECAPTURE_OT_Start,
    BONECAPTURE_OT_Stop,
    MQT_PT_BoneCapturePanel,
    
    # 顶点组工具相关类
    VertexGroupSelectItem,
    VERTEX_OT_MergeVertexGroups,
    MQT_PT_VertexGroupPanel,
    
    # 一键PBR材质着色工具相关类 (使用重构后的 Operator)
    PBRMaterialSettings,  # 添加PBR设置属性组
    AUTO_OT_create_pbr_materials,
    MQT_PT_PBRMaterialPanel,

    # 网格权重显示工具 (新功能)
    MeshWeightToolsSettings,
    MESH_OT_isolate_zero_weight_meshes,
    MQT_PT_MeshWeightDisplayPanel,
    
    # MMD材质转换工具
    MMD_OT_convert_materials_to_blender,
    MMD_OT_convert_materials_to_cycles,
    MMD_OT_convert_materials_to_mmd,
    MQT_PT_MMDMaterialPanel,
    
    # 面数排行榜（实时）
    FaceCountSettings,
    MQT_OT_RefreshFaceCounts,
    MQT_PT_FaceCountPanel,
    
    # 精简修改器实时显示切换
    DecimateToggleSettings,
    DECIMATE_OT_EnableViewportAll,
    DECIMATE_OT_DisableViewportAll,
    MQT_PT_DecimateTogglePanel,
    
    # 静态对象GLB导出工具
    StaticGLBExportSettings,
    STATIC_OT_export_glb,
    MQT_PT_StaticGLBExportPanel,
    
    # 绝地潜兵2MOD制作工具
    HELLDIVERS2_OT_ProcessModel,
    MQT_PT_Helldivers2Panel,
)

def register():
    bpy.utils.register_class(MMDSeparatorSettings)
    bpy.types.Scene.mmd_separator_settings = PointerProperty(type=MMDSeparatorSettings)
    # (其他类的注册保持不变)
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # 注册快速拆分助手设置
    bpy.types.Scene.qseparator_settings = bpy.props.PointerProperty(type=QSeparatorSettings)
    
    # 注册主体骨骼重命名设置
    bpy.types.Scene.rename_primary_settings = bpy.props.PointerProperty(type=RenamePrimarySettings)
    
    # 注册骨骼选择器设置
    bpy.types.Scene.bone_keyword = bpy.props.StringProperty(
        name="关键词",
        description="输入关键词搜索骨骼",
        default=""
    )
    bpy.types.Scene.case_sensitive = bpy.props.BoolProperty(
        name="区分大小写搜索骨骼",
        description="区分大小写搜索骨骼",
        default=False
    )
    
    # 注册描边设置
    bpy.types.Scene.outline_size = bpy.props.FloatProperty(
        name="描边大小",
        description="设置描边的大小（米），沿法线方向缩放，输入正值，自动转为负值",
        default=0.05,
        min=0.001,
        soft_min=0.001,
        soft_max=1.0
    )
    bpy.types.Scene.use_outline_base = bpy.props.BoolProperty(
        name="使用统一 Outline_Base 材质",
        description="如果开启，第一个材质槽将使用 Outline_Base 材质，其他槽保留原材质但添加前缀",
        default=True
    )
    bpy.types.Scene.use_named_materials = bpy.props.BoolProperty(
        name="根据名称使用特定材质",
        description="如果开启，根据模型名称分配描边材质，如 Outline_Hair 或 Outline_Face",
        default=True
    )
    bpy.types.Scene.outline_mode = bpy.props.EnumProperty(
        name="描边放置模式",
        description="选择描边对象的放置模式",
        items=[
            ('ORIGINAL', "原集合", "描边对象和原对象放在相同的集合中"),
            ('SINGLE', "统一集合", "所有描边对象放在一个统一的集合中"),
            ('SEPARATE', "单独集合", "每个描边对象放在单独的集合中")
        ],
        default='SEPARATE'  # 默认放在单独集合中
    )
    bpy.types.Scene.include_all_models = bpy.props.BoolProperty(
        name="输出全部",
        description="是否输出原模型与描边模型，排除名称为 'Face' 和 'smd_bone_vis' 的对象",
        default=False
    )
    
    # 注册VMT材质批量复制工具设置
    bpy.types.Scene.material_groups = bpy.props.CollectionProperty(type=MaterialGroupItem)
    bpy.types.Scene.source_vmt_path = bpy.props.StringProperty(
        name="源VMT文件夹",
        description="选择包含源VMT文件的文件夹",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.target_vmt_path = bpy.props.StringProperty(
        name="目标VMT路径",
        description="选择VMT文件复制的目标文件夹",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.vmt_log_path = bpy.props.StringProperty(
        name="日志输出文件夹",
        description="选择日志文件输出的文件夹",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.vmt_enable_logging = bpy.props.BoolProperty(
        name="启用日志输出",
        description="启用后将在刷新材质列表时输出详细日志到指定文件夹",
        default=False
    )
    
    # 注册一键PBR材质工具设置
    # REMOVED: bpy.types.Scene.pbr_output_directory
    bpy.types.Scene.pbr_clean_data = bpy.props.BoolProperty(
        name="清理未使用的数据",
        description="清理未使用的贴图和材质数据，避免.001后缀",
        default=True
    )
    bpy.types.Scene.pbr_skinuber_cloth_type = bpy.props.EnumProperty(
        name="Skinuber贴图类型",
        description="选择用于skinuber材质的贴图类型",
        items=[
            ('NONE', "不处理", "不处理skinuber材质"),
            ('CLOTH1', "Cloth1贴图", "使用名称中包含cloth1的贴图"),
            ('CLOTH2', "Cloth2贴图", "使用名称中包含cloth2的贴图"),
        ],
        default='CLOTH2'
    )
    bpy.types.Scene.pbr_cloth2double_cloth_type = bpy.props.EnumProperty(
        name="Cloth2Double贴图类型",
        description="选择用于cloth2Double_uber材质的贴图类型",
        items=[
            ('NONE', "不处理", "不处理cloth2Double_uber材质，使用自动匹配"),
            ('CLOTH1', "Cloth1贴图", "使用名称中包含cloth1的贴图"),
            ('CLOTH2', "Cloth2贴图", "使用名称中包含cloth2的贴图"),
        ],
        default='CLOTH2'
    )
    bpy.types.Scene.pbr_silkstock_cloth_type = bpy.props.EnumProperty(
        name="Silkstock贴图类型",
        description="选择用于silkstock_uber材质的贴图类型",
        items=[
            ('NONE', "不处理", "不处理silkstock_uber材质，使用自动匹配"),
            ('CLOTH1', "Cloth1贴图", "使用名称中包含cloth1的贴图"),
            ('CLOTH2', "Cloth2贴图", "使用名称中包含cloth2的贴图"),
        ],
        default='CLOTH1'
    )
    bpy.types.Scene.pbr_processing_mode = bpy.props.EnumProperty(
        name="处理模式",
        description="选择 PBR 材质处理模式",
        items=[
            ('FULL', "完整PBR", "处理基础色、RMO和Alpha"),
            ('BASE_ALPHA', "仅基础色+Alpha", "只处理基础色和Alpha，跳过RMO"),
        ],
        default='FULL'
    )
    # 注册复制外部纹理设置
    bpy.types.Scene.pbr_copy_textures_externally = bpy.props.BoolProperty(
        name="复制纹理到外部文件夹",
        description="为每个材质创建纹理文件的物理副本到指定文件夹，避免导出合并",
        default=False
    )
    bpy.types.Scene.pbr_external_texture_directory = bpy.props.StringProperty(
        name="外部纹理文件夹",
        description="选择存储复制纹理的目标文件夹",
        subtype='DIR_PATH'
    )

    # 注册PBR日志设置
    bpy.types.Scene.pbr_material_settings = bpy.props.PointerProperty(type=PBRMaterialSettings)
    # 注册网格权重显示工具设置 (新功能)
    bpy.types.Scene.mq_mesh_weight_settings = bpy.props.PointerProperty(type=MeshWeightToolsSettings)
    # 注册面数排行榜设置
    bpy.types.Scene.mq_face_count_settings = bpy.props.PointerProperty(type=FaceCountSettings)
    # 注册精简修改器实时显示设置
    bpy.types.Scene.decimate_toggle_settings = bpy.props.PointerProperty(type=DecimateToggleSettings)
    # 注册静态对象GLB导出设置
    bpy.types.Scene.static_glb_settings = bpy.props.PointerProperty(type=StaticGLBExportSettings)
    
    # 注册顶点组合并工具设置
    bpy.types.Scene.vertex_group_selected_groups = bpy.props.CollectionProperty(type=VertexGroupSelectItem)
    # 注册骨骼捕捉设置
    bpy.types.Scene.bone_capture_settings = bpy.props.PointerProperty(type=BoneCaptureSettings)


def unregister():
    bpy.utils.unregister_class(MMDSeparatorSettings)
    del bpy.types.Scene.mmd_separator_settings
    # (其他类的注销保持不变)

    # 注销VMT材质批量复制工具设置
    if hasattr(bpy.types.Scene, 'material_groups'):
        del bpy.types.Scene.material_groups
    if hasattr(bpy.types.Scene, 'source_vmt_path'):
        del bpy.types.Scene.source_vmt_path
    if hasattr(bpy.types.Scene, 'target_vmt_path'):
        del bpy.types.Scene.target_vmt_path
    if hasattr(bpy.types.Scene, 'vmt_log_path'):
        del bpy.types.Scene.vmt_log_path
    if hasattr(bpy.types.Scene, 'vmt_enable_logging'):
        del bpy.types.Scene.vmt_enable_logging

    # 注销一键PBR材质工具设置 (保持不变)
    # REMOVED: del bpy.types.Scene.pbr_output_directory
    del bpy.types.Scene.pbr_clean_data
    del bpy.types.Scene.pbr_skinuber_cloth_type
    del bpy.types.Scene.pbr_cloth2double_cloth_type
    del bpy.types.Scene.pbr_silkstock_cloth_type
    del bpy.types.Scene.pbr_processing_mode
    # 注销复制外部纹理设置
    del bpy.types.Scene.pbr_copy_textures_externally
    del bpy.types.Scene.pbr_external_texture_directory

    # 注销PBR日志设置
    if hasattr(bpy.types.Scene, 'pbr_material_settings'):
        del bpy.types.Scene.pbr_material_settings
    # 注销网格权重显示工具设置 (新功能)
    if hasattr(bpy.types.Scene, 'mq_mesh_weight_settings'):
        del bpy.types.Scene.mq_mesh_weight_settings
    # 注销面数排行榜设置
    if hasattr(bpy.types.Scene, 'mq_face_count_settings'):
        del bpy.types.Scene.mq_face_count_settings
    # 注销精简修改器实时显示设置
    if hasattr(bpy.types.Scene, 'decimate_toggle_settings'):
        del bpy.types.Scene.decimate_toggle_settings
    # 注销静态对象GLB导出设置
    if hasattr(bpy.types.Scene, 'static_glb_settings'):
        del bpy.types.Scene.static_glb_settings
    
    # 注销顶点组合并工具设置
    if hasattr(bpy.types.Scene, 'vertex_group_selected_groups'):
        del bpy.types.Scene.vertex_group_selected_groups
    # 注销主体骨骼重命名设置
    if hasattr(bpy.types.Scene, 'rename_primary_settings'):
        del bpy.types.Scene.rename_primary_settings

    # 注销骨骼捕捉设置
    if hasattr(bpy.types.Scene, 'bone_capture_settings'):
        del bpy.types.Scene.bone_capture_settings
    
    # 注销所有类 (包括重构后的 PBR Operator)
    for cls in reversed(classes):
        if hasattr(bpy.utils, "unregister_class"): # Check if unregister_class exists
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError: # Catch errors if class was already unregistered or not registered
                pass # Or log a warning: print(f"Could not unregister class {cls.__name__}")

# 主函数 (保持不变)
if __name__ == "__main__":
    register()