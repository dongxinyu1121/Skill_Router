import subprocess
from typing import Dict

from .base import Tool


def _print_tool(name: str, detail: str) -> None:
    """用统一格式打印即将执行的工具命令。"""
    print(f"  \033[2m[tool: {name}] {detail}\033[0m")


class BashTool(Tool):
    """Execute shell commands."""

    def __init__(self):
        """声明 Bash 工具名称、说明和参数 schema。"""
        super().__init__(
            name="Bash",
            description="""执行 shell 命令（在 Unix/macOS 上使用 bash，在 Windows 上使用 cmd.exe）。
                    使用场景：
                    运行技能脚本
                    安装依赖
                    文件操作
                    任何 shell 命令""",
            params={"command": {"type": "string"}, "description": {"type": "string"}},
            required=["command"],
        )

    def execute(self, command: str, description: str = "") -> Dict[str, str | int]:
        """执行 shell 命令，并返回 stdout、stderr 和退出码。"""
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/", "mkfs", "> /dev/sd", "dd if="]
        for pattern in dangerous:
            if pattern in command:
                return {"status": "failed", "message": f"Error: Refused to run dangerous command containing '{pattern}'"}

        try:
            _print_tool("bash", command)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "status": "succeed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "description": description,
            }
        except Exception as exc:
            return {"status": "failed", "message": str(exc)}
