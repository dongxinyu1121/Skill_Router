from pathlib import Path
from typing import Any, Dict

from core.prompts import base_system_prompt
from skill_core import SkillRegistry
from toolkit import BashTool, ReadFileTool, SkillTool, Tool


class AgentBase:
    """Shared agent state and tool wiring."""

    def __init__(self, skill_registry: SkillRegistry):
        """保存 skill 注册表，并注册所有 Agent 共享工具。"""
        self.skill_registry = skill_registry
        self.tools: Dict[str, Tool] = {}
        self.conversation_history: list[Dict[str, Any]] = []
        self.agent_context: Dict[str, Any] = {"working_directory": Path.cwd()}

        self._register_tool(SkillTool(skill_registry))
        self._register_tool(BashTool())

    def _register_tool(self, tool: Tool) -> None:
        """按工具名注册工具，供后续模型 tool_call 调用。"""
        self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        """把 Level 1 skills registry 注入系统提示词。"""
        return base_system_prompt.format(skills_registry=self.skill_registry.get_registry_prompt())

    def _get_tool_schema(self):
        """把所有已注册工具转换成 OpenAI tool schema。"""
        return [tool.to_schema() for tool in self.tools.values()]

    def _reset_agent_context(self) -> None:
        """开始新用户回合前重置临时 Agent 上下文。"""
        self.agent_context = {"working_directory": Path.cwd()}

    def _in_skill_context(self) -> bool:
        """判断当前回合是否已经加载过某个 Skill。"""
        return "skill_context" in self.agent_context

    def _set_skill_context(self, skill_context: Dict[str, Any]) -> None:
        """保存当前激活 Skill 的名称、路径和正文内容。"""
        self.agent_context["skill_context"] = skill_context

    def _attach_read_file_tool(self) -> None:
        """在加载 Skill 后注册可解析相对路径的 ReadFile 工具。"""
        read_file_tool = ReadFileTool()
        read_file_tool.set_context(self.agent_context)
        self._register_tool(read_file_tool)
