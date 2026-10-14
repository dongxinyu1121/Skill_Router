"""通过系统命令解释器执行命令，返回输出、错误输出和进程退出码。"""

import subprocess
from typing import Dict, Union

from .base import Tool


def _print_tool(name: str, detail: str) -> None:
    """在终端打印工具名称与即将执行的命令，便于跟踪运行过程。"""
    print(f"  \033[2m[tool: {name}] {detail}\033[0m")


class BashTool(Tool):
    """执行模型提出的命令，使用 subprocess 调用操作系统默认命令解释器。

    名称为 Bash，但具体解释器取决于平台，Windows 通常使用 cmd.exe。
    禁用字符串列表只是简单拦截，不构成完整的命令安全隔离机制。
    """

    def __init__(self):
        """声明必填命令 command 和可选说明 description，供模型发起调用。"""
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

    def execute(self, command: str, description: str = "") -> Dict[str, Union[str, int]]:
        """检查命令中的禁用字符串，然后等待进程完成，最长等待 30 秒。

        被拦截或发生异常时返回失败信息；进程正常返回时保留 stdout、
        stderr 和 returncode。当前即便退出码非零，也仍标记为 succeed，
        调用者需要结合 returncode 判断命令本身是否执行成功。
        """
        # 按字符串包含关系拦截部分命令，没有解析命令语法或限制执行目录。
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/", "mkfs", "> /dev/sd", "dd if="]
        for pattern in dangerous:
            if pattern in command:
                return {"status": "failed", "message": f"Error: Refused to run dangerous command containing '{pattern}'"}

        try:
            _print_tool("bash", command)
            # 捕获输出而不直接显示；命令没有显式 cwd，沿用进程当前工作目录。
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
