"""加载 Skill 完整指令的工具。"""

from typing import Any, Dict

from ..skills import SkillRegistry
from . import Tool, ToolContext


class SkillTool(Tool):
    """按名称返回完整技能指令，实现第二级渐进披露。"""

    def __init__(self, registry: SkillRegistry):
        super().__init__(
            name="Skill",
            description="加载技能（skills）完整指令。参数: {'command': '技能名称'}",
            parameters={
                "command": {"type": "string", "description": "技能名称，如 'code-reviewer'"}
            },
            required=["command"],
        )
        self.registry = registry

    def execute(self, context: ToolContext, command: str) -> Dict[str, Any]:
        """加载技能正文，并把该技能设置为本轮当前技能。"""
        skill = self.registry.get(command)
        if not skill:
            return {"status": "failed", "message": "Skill '%s' 不存在" % command}

        context.active_skill = skill
        return {
            "status": "succeed",
            "message": "启动技能: %s" % command,
            "command_name": command,
            "base_path": str(skill.base_path),
            "content": skill.content,
            "note": (
                "请按照上述技能指令执行。如需查阅引用文件（如 references/xxx.md），"
                "使用 ReadFile 工具并基于 Base Path 构造路径"
            ),
        }
