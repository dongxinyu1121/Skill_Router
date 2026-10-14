"""执行系统命令的工具。"""

import subprocess
from typing import Any, Dict

from . import Tool, ToolContext


class BashTool(Tool):
    """通过系统默认命令解释器执行命令。"""

    BLOCKED_PATTERNS = (
        "rm -rf /",
        "sudo",
        "shutdown",
        "reboot",
        "> /dev/",
        "mkfs",
        "> /dev/sd",
        "dd if=",
    )

    def __init__(self):
        super().__init__(
            name="Bash",
            description="""执行 shell 命令（在 Unix/macOS 上使用 bash，在 Windows 上使用 cmd.exe）。
                    使用场景：
                    运行技能脚本
                    安装依赖
                    文件操作
                    任何 shell 命令""",
            parameters={
                "command": {"type": "string"},
                "description": {"type": "string"},
            },
            required=["command"],
        )

    def execute(
        self,
        context: ToolContext,
        command: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """执行命令并返回输出；非零退出码仍通过 returncode 表示。"""
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in command:
                return {
                    "status": "failed",
                    "message": "Error: Refused to run dangerous command containing '%s'" % pattern,
                }

        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            return {"status": "failed", "message": str(exc)}

        return {
            "status": "succeed",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
            "description": description,
        }
