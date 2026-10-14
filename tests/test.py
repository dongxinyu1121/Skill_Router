"""早期日志统计脚本：读取记录列表并打印记录数量，不属于断言式测试。

当前路径相对于本文件，指向 tests/data/agent_log.json；项目里的实际数据
在根目录 data 下，因此直接执行可能因目标文件不存在而报错。
"""

import json
from pathlib import Path

# 使用 UTF-8 解码中文日志，再将 JSON 数组转换为列表以统计条数。
inputs = json.load(open(Path(__file__).parent / "data/agent_log.json", "r", encoding="utf-8"))
print(len(inputs))
