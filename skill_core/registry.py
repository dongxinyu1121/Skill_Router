"""扫描技能文件并提供三级披露所需的数据。

启动时会把元数据和正文一起缓存到程序内存，但只把名称和描述交给模型。
渐进式披露控制的是模型看到的内容，并非技能正文从磁盘读取的时机。
"""

from pathlib import Path
from typing import Dict, Optional

import yaml

from .models import Skill, SkillMetadata


class SkillRegistry:
    """以技能名称为索引，管理目录提示词、完整指令和引用资源的读取。"""

    def __init__(self, skills_dir: Path):
        """保存技能根目录，立即扫描并缓存其中可识别的技能文件。"""
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        """按目录名排序扫描一级子目录，解析其中的技能说明文件。

        根目录不存在时保留空注册表；根目录下的普通文件不会被当作技能。
        这里只检查每个子目录的入口文件，不递归扫描更深层目录。
        """
        if not self.skills_dir.exists():
            return

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_md = self._find_skill_file(skill_dir)
                if skill_md:
                    self._load_skill(skill_dir, skill_md)

    def _find_skill_file(self, skill_dir: Path) -> Optional[Path]:
        """查找技能入口文件，优先使用 SKILL.md，未找到时尝试 skill.md。

        返回找到的路径；两种名称均不存在时返回 None。
        """
        for candidate in ("SKILL.md", "skill.md"):
            skill_md = skill_dir / candidate
            if skill_md.exists():
                return skill_md
        return None

    def _load_skill(self, skill_dir: Path, skill_md: Path) -> None:
        """拆分文件头部的 YAML 元数据与正文，构造技能对象并加入缓存。

        文件必须以 --- 开始，并包含结束元数据的第二个 ---。
        不符合该格式或 YAML 解析失败时跳过；缺少名称时使用目录名。
        同名技能会覆盖此前缓存的对象。
        """
        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return

        # 最多分割两次，后面的正文可以继续包含 Markdown 分隔线。
        parts = content.split("---", 2)
        if len(parts) < 3:
            return

        try:
            meta = yaml.safe_load(parts[1]) or {}
        except Exception as exc:
            print(f"加载技能失败 {skill_dir.name}: {exc}")
            return

        # 当前从 YAML 顶层读取作者和版本，不读取 metadata 子字典中的同名项。
        metadata = SkillMetadata(
            name=meta.get("name", skill_dir.name),
            description=meta.get("description", ""),
            author=meta.get("author"),
            version=meta.get("version"),
        )
        self._skills[metadata.name] = Skill(
            metadata=metadata,
            content=parts[2].strip(),
            base_path=skill_dir,
        )

    def get_registry_prompt(self) -> str:
        """生成第一级披露的目录提示词：技能名称、描述和调用说明。

        此处不拼接完整技能正文，让模型先依据简短描述选择技能。
        返回字符串由 AgentBase 填入系统提示词模板。
        """
        lines = [
            "# 技能注册表（Skills Registry）\n",
            "以下是你可用的技能列表。每个技能包含名称和描述。**当用户需求匹配某个技能的描述时，调用 `Skill` 工具加载完整指令**：\n",
        ]

        for name, skill in self._skills.items():
            lines.append(f"1. **{name}**: {skill.metadata.description}")

        lines.extend(
            [
                "\n如何使用技能：",
                "- 使用技能描述判断用户意图，而非仅匹配关键词",
                "- 只要意图相符，立即调用对应 Skill 工具，不要直接回应",
                "- 你不需要知道 Skill 的文件路径，只需传递技能名称给 Skill 工具",
            ]
        )
        return "\n".join(lines)

    def load_full_skill(self, name: str) -> Optional[Skill]:
        """返回内存中已有的技能对象，用于第二级披露；名称不存在则返回 None。

        此方法不会重新读取磁盘。SkillTool 会将正文作为工具结果返回给模型。
        """
        return self._skills.get(name)

    def load_reference(self, skill_name: str, ref_path: str) -> Optional[str]:
        """读取指定技能目录下的引用文件，用于第三级资源披露。

        ref_path 通常为 references/xxx.md 等相对路径。技能或文件不存在
        时返回 None；每次调用都会读取磁盘，不使用 references 字段缓存。
        当前方法只拼接路径，没有限制读取范围；交互运行层使用的是 ReadFile 工具。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return None

        full_path = skill.base_path / ref_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None
