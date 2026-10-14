"""读取模型连接配置，供模型客户端初始化时使用。"""

import os
from typing import Dict

from dotenv import load_dotenv


def load_model_settings() -> Dict[str, str]:
    """读取密钥、接口地址和模型名称，返回客户端需要的配置字典。

    .env 中的配置会覆盖已有的同名环境变量。三项配置均为必填项，
    缺失或为空时抛出 RuntimeError，避免等到模型请求时才发现配置问题。
    返回字典的键为 api_key、base_url 和 model_name。
    """
    # override=True 表示本地 .env 优先于终端中已有的配置。
    load_dotenv(override=True)

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL")

    # 先收集所有缺失项，再一次性报告，便于补齐配置。
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
            "缺少模型配置环境变量: " + ", ".join(missing)
        )

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
    }
