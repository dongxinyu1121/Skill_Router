"""统一工具的接口：描述能力、接收执行上下文、执行调用并生成参数结构。"""

from typing import Any, Dict, List, Optional


class Tool:
    """可调用工具的公共基类，具体文件读取、技能加载或命令执行由子类实现。

    模型通过 to_schema 的返回值了解工具；运行层通过 execute 真正执行工具。
    工具执行结果随后由运行层写入对话，而不是由工具直接发给模型。
    """

    def __init__(
        self,
        name: str,
        description: str,
        params: Dict[str, Any],
        required: Optional[List[str]] = None,
    ):
        """保存工具名称、用途、参数定义和必填参数列表。

        name 与模型返回的工具名称对应；params 定义各参数的类型和描述；
        required 决定哪些参数必须提供。context 保存运行层提供的上下文，
        与模型传来的工具参数分开管理。
        """
        self.name = name
        self.description = description
        self.params = params
        self.required = required or []
        self.context: Dict[str, Any] = {}

    def set_context(self, context: Dict[str, Any]) -> None:
        """保存运行层传入的上下文字典，供具体工具执行时读取。

        这里直接引用原字典，不复制、不调整其结构；各工具需要自行约定键名。
        """
        self.context = context

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行具体能力并返回结果字典，子类需要覆盖此方法。

        运行层用 execute(**arguments) 将模型参数字典展开为关键字参数。
        基类没有执行能力，直接调用会抛出 NotImplementedError。
        """
        raise NotImplementedError

    def to_schema(self) -> Dict[str, Any]:
        """生成 OpenAI 兼容接口需要的函数工具描述。

        返回工具名称、描述及 JSON 参数结构，仅用于告知模型如何调用。
        生成描述不会执行工具，也不包含当前上下文或工具结果。
        """
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
