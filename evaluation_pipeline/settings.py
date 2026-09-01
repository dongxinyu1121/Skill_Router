from dataclasses import dataclass
from pathlib import Path
import os

from core.config import load_llm_settings


@dataclass(frozen=True)
class EvaluationSettings:
    script_dir: Path
    input_json: Path
    output_csv: Path
    model_deepseek: str
    model_doubao: str
    max_workers: int = 20
    save_details: bool = True


def load_settings(script_dir: Path | None = None) -> EvaluationSettings:
    base_dir = script_dir or Path(__file__).resolve().parents[1]
    load_llm_settings()
    return EvaluationSettings(
        script_dir=base_dir,
        input_json=base_dir / "data" / "agent_log.json",
        output_csv=base_dir / "data" / "judge_results.csv",
        model_deepseek=os.getenv("MODEL_DEEPSEEK", "deepseek-v4-pro-260425"),
        model_doubao=os.getenv("MODEL_DOUBAO", "doubao-seed-2-0-pro-260215"),
        max_workers=int(os.getenv("EVAL_MAX_WORKERS", "20")),
        save_details=os.getenv("EVAL_SAVE_DETAILS", "true").lower() != "false",
    )
