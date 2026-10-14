"""技能数据结构：将用于选择技能的元数据与完整执行指令区分开。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class SkillMetadata:
    """第一级披露使用的技能元数据。

    name 是调用技能时使用的名称，description 帮助模型判断适用场景。
    author 和 version 是可选信息，当前技能目录提示词只包含前两项。
    """

    name: str
    description: str
    author: Optional[str] = None
    version: Optional[str] = None


@dataclass
class Skill:
    """保存一个技能的元数据、完整正文及所在目录。

    content 是去掉文件头部元数据后的 Markdown 正文；base_path 是技能
    所在目录，用于定位引用资源。references 为每个实例单独创建字典，
    当前注册表读取引用文件时不会自动将内容填入这个字段。
    """

    metadata: SkillMetadata
    content: str
    base_path: Path
    references: Dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """返回技能名称，让调用者通过 skill.name 读取而无需访问元数据内部。"""
        return self.metadata.name
