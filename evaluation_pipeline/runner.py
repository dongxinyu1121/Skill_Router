import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from .client import JudgeClient
from .dataset import load_articles, save_results
from .scoring import build_prompt, score_answer
from .settings import EvaluationSettings


class BatchEvaluator:
    """负责多线程调模型、汇总分数并保存评测结果。"""

    def __init__(self, settings: EvaluationSettings):
        """保存评测配置，并初始化模型客户端和进度计数器。"""
        self.settings = settings
        self.client = JudgeClient()
        self.counter_lock = Lock()
        self.completed_count = 0
        self.total_count = 0

    def _judge_once(self, real_bottom: str, predict: str, real_top: str, model_name: str, max_retries: int = 2) -> int:
        """对单个模型做一次语义相似度判断，失败时按次数重试。"""
        prompt = build_prompt(real_bottom, predict, real_top)
        for attempt in range(max_retries):
            try:
                answer = self.client.judge(model_name, prompt)
                return score_answer(answer)
            except Exception as exc:
                print(f"  调用失败 (attempt {attempt + 1}): {exc}")
                time.sleep(2)
        return 0

    def _judge_single_article(self, idx: int, article: dict) -> dict:
        """分别调用两个模型评判一篇文章，并返回结构化分数。"""
        real_bottom = article["article_bottom"]
        predict = article["predict"]
        real_top = article["article_top"]
        title = article.get("title", f"第{idx + 1}篇")

        print(f"\n正在评判第 {idx + 1}/{self.total_count} 篇：{title[:40]}...")
        print("  → DeepSeek 判断中...")
        deepseek_score = self._judge_once(real_bottom, predict, real_top, self.settings.model_deepseek)
        print(f"    DeepSeek 得分: {deepseek_score}")

        print("  → Doubao 判断中...")
        doubao_score = self._judge_once(real_bottom, predict, real_top, self.settings.model_doubao)
        print(f"    Doubao 得分: {doubao_score}")

        with self.counter_lock:
            self.completed_count += 1
            print(f"✅ 已完成 {self.completed_count}/{self.total_count} 条")

        return {
            "index": idx,
            "title": title,
            "deepseek_score": deepseek_score,
            "doubao_score": doubao_score,
        }

    def run(self) -> None:
        """执行完整批量评测流程：加载数据、并发评判、汇总、保存。"""
        articles = load_articles(self.settings.input_json)
        self.total_count = len(articles)
        self.completed_count = 0

        print(f"已加载 {self.total_count} 篇文章")
        print(f"开始多线程评判，最大线程数: {self.settings.max_workers}")
        print("=" * 80)

        results: list[dict] = []
        total_ds = 0
        total_db = 0

        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            future_to_idx = {
                executor.submit(self._judge_single_article, idx, article): idx
                for idx, article in enumerate(articles)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    results.append(result)
                    total_ds += result["deepseek_score"]
                    total_db += result["doubao_score"]
                    time.sleep(random.uniform(0.2, 0.5))
                except Exception as exc:
                    print(f"\n❌ 任务异常 [第 {idx + 1} 篇]: {exc}")

        results.sort(key=lambda x: x["index"])

        print("\n" + "=" * 50)
        print(f"DeepSeek 总分: {total_ds} / {len(articles)}  (准确率: {total_ds / len(articles) * 100:.2f}%)")
        print(f"Doubao   总分: {total_db} / {len(articles)}  (准确率: {total_db / len(articles) * 100:.2f}%)")
        print("=" * 50)

        if self.settings.save_details:
            save_results(self.settings.output_csv, results)
            print(f"\n详细结果已保存至 {self.settings.output_csv}")
