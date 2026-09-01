from typing import Any, Dict, List


class Tool:
    """Base class for callable tools."""

    def __init__(
        self,
        name: str,
        description: str,
        params: Dict[str, Any],
        required: List[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.params = params
        self.required = required or []
        self.context: Dict[str, Any] = {}

    def set_context(self, context: Dict[str, Any]) -> None:
        self.context = context

    def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def to_schema(self) -> Dict[str, Any]:
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
