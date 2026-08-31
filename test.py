import json
from pathlib import Path

inputs = json.load(open(Path(__file__).parent / "data/agent_log.json", "r", encoding="utf-8"))
print(len(inputs))