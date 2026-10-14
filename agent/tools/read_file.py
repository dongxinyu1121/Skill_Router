"""读取当前 Skill 引用资源的工具。"""

from pathlib import Path
from typing import Any, Dict

from . import Tool, ToolContext


class ReadFileTool(Tool):
    """读取文本文件；相对路径以当前技能目录为基准。"""

    def __init__(self):
        super().__init__(
            name="ReadFile",
            description="读取文件内容。支持绝对路径或基于当前 Skill Base Path 的相对路径",
            parameters={"file_path": {"type": "string"}},
            required=["file_path"],
        )

    def execute(self, context: ToolContext, file_path: str) -> Dict[str, Any]:
        """解析路径并读取 UTF-8 文本文件。"""
        path = Path(file_path)
        if not path.is_absolute() and context.active_skill:
            path = context.active_skill.base_path / path

        if not path.is_file():
            return {"status": "failed", "message": "文件不存在: %s" % path}

        return {
            "status": "succeed",
            "content": path.read_text(encoding="utf-8"),
            "file_path": str(path),
        }
