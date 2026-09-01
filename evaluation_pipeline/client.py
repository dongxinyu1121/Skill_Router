from openai import OpenAI

from core.config import load_llm_settings


class JudgeClient:
    def __init__(self):
        settings = load_llm_settings()
        self.client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )

    def judge(self, model_name: str, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
