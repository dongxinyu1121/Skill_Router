"""统计历史 Agent 记录，替代原先位于 tests/test.py 的临时脚本。

从脚本位置定位 data/agent_log.json，因此不依赖终端的当前工作目录。
此功能只读取已有日志，不调用模型，也不修改数据。
"""

import json
from pathlib import Path


def main() -> None:
    """读取根目录下的日志数组并显示记录数量。"""
    log_path = Path(__file__).resolve().parents[1] / "data" / "agent_log.json"
    records = json.loads(log_path.read_text(encoding="utf-8"))
    print(len(records))


if __name__ == "__main__":
    main()
