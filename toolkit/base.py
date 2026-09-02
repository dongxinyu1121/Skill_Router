from typing import Any, Dict, List, Optional


class Tool:
    """Base class for callable tools."""

    def __init__(
        self,
        name: str,
        description: str,
        params: Dict[str, Any],
        required: Optional[List[str]] = None,
    ):
        """记录工具的公开名称、说明和参数 schema。"""
        self.name = name
        self.description = description
        self.params = params
        self.required = required or []
        self.context: Dict[str, Any] = {}

    def set_context(self, context: Dict[str, Any]) -> None:
        """注入当前 Agent 上下文，例如已激活 skill 的 base_path。"""
        self.context = context

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具逻辑，子类必须实现。"""
        raise NotImplementedError

    def to_schema(self) -> Dict[str, Any]:
        """转换成 OpenAI-compatible tool calling schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.params,
                    "required": self.required,
                },
            },
        }
