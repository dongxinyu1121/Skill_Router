from openai import OpenAI

from core.config import load_llm_settings


class JudgeClient:
    """评测阶段使用的模型客户端。"""

    def __init__(self):
        """读取环境变量配置并初始化 OpenAI-compatible 客户端。"""
        settings = load_llm_settings()
        self.client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )

    def judge(self, model_name: str, prompt: str) -> str:
        """调用指定模型，让它判断预测下文和真实下文是否语义相似。"""
        response = self.client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
