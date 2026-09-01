from pathlib import Path
from typing import Dict

from .base import Tool


class ReadFileTool(Tool):
    """Read a file from disk, resolving relative paths from skill context."""

    def __init__(self):
        super().__init__(
            name="ReadFile",
            description="读取文件内容。支持绝对路径或基于当前 Skill Base Path 的相对路径",
            params={"file_path": {"type": "string"}},
            required=["file_path"],
        )

    def execute(self, file_path: str) -> Dict[str, str]:
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
