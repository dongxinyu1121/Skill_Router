"""导出技能数据结构与注册表，供入口、工具和评测脚本共同使用。"""

from .models import Skill, SkillMetadata
from .registry import SkillRegistry

__all__ = ["Skill", "SkillMetadata", "SkillRegistry"]
