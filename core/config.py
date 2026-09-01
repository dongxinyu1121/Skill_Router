import os

from dotenv import load_dotenv


def load_llm_settings() -> dict[str, str]:
    """从 .env 或系统环境变量读取 LLM 配置，缺必填项时直接报错。"""
    load_dotenv()

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model_name = os.getenv("LLM_MODEL")

    missing = [
        name
        for name, value in (
            ("LLM_API_KEY", api_key),
            ("LLM_BASE_URL", base_url),
            ("LLM_MODEL", model_name),
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
