from pathlib import Path
from typing import Any, Dict

from core.prompts import base_system_prompt
from skill_core import SkillRegistry
from toolkit import BashTool, ReadFileTool, SkillTool, Tool


class AgentBase:
    """Shared agent state and tool wiring."""

    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry
        self.tools: Dict[str, Tool] = {}
        self.conversation_history: list[Dict[str, Any]] = []
        self.agent_context: Dict[str, Any] = {"working_directory": Path.cwd()}

        self._register_tool(SkillTool(skill_registry))
        self._register_tool(BashTool())

    def _register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        return base_system_prompt.format(skills_registry=self.skill_registry.get_registry_prompt())

    def _get_tool_schema(self):
        return [tool.to_schema() for tool in self.tools.values()]

    def _reset_agent_context(self) -> None:
        self.agent_context = {"working_directory": Path.cwd()}

    def _in_skill_context(self) -> bool:
        return "skill_context" in self.agent_context

    def _set_skill_context(self, skill_context: Dict[str, Any]) -> None:
        self.agent_context["skill_context"] = skill_context

    def _attach_read_file_tool(self) -> None:
        read_file_tool = ReadFileTool()
        read_file_tool.set_context(self.agent_context)
        self._register_tool(read_file_tool)
