"""提供文本文件读取工具，支持使用上下文中的目录信息拼接路径。"""

from pathlib import Path
from typing import Dict

from .base import Tool


class ReadFileTool(Tool):
    """读取磁盘上的 UTF-8 文本，并以工具结果字典返回内容或缺失提示。"""

    def __init__(self):
        """声明工具名称和必填参数 file_path，供模型按路径请求文件内容。"""
        super().__init__(
            name="ReadFile",
            description="读取文件内容。支持绝对路径或基于当前 Skill Base Path 的相对路径",
            params={"file_path": {"type": "string"}},
            required=["file_path"],
        )

    def execute(self, file_path: str) -> Dict[str, str]:
        """根据传入路径读取文件，存在时返回正文和路径，否则返回失败信息。

        当前实现检查路径是否以 / 开头：若不以 / 开头且上下文顶层含有
        base_path，就将两者拼接；否则直接用 Path(file_path) 解析。
        未拼接的相对路径会以进程工作目录为基准。

        注意：运行层目前把 base_path 放在 skill_context 子字典里，
        本工具却读取顶层同名键，因此这条调用链并不会自动应用技能目录。
        这里如实说明现有行为；文件读取异常也会直接传给调用者。
        """
        if not file_path.startswith("/") and self.context.get("base_path"):
            full_path = Path(self.context["base_path"]) / file_path
        else:
            full_path = Path(file_path)

        if full_path.exists():
            return {
                "status": "succeed",
                "content": full_path.read_text(encoding="utf-8"),
                "file_path": str(full_path),
            }
        return {"status": "failed", "message": f"文件不存在: {full_path}"}
