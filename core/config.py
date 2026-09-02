import os
from typing import Dict

from dotenv import load_dotenv


def load_llm_settings() -> Dict[str, str]:
    """从 .env 或系统环境变量读取 LLM 配置，缺必填项时直接报错。"""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL")

    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", api_key),
            ("OPENAI_BASE_URL", base_url),
            ("OPENAI_MODEL", model_name),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
    }
