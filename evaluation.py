import json
import os
import time
import random
from openai import OpenAI
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from config import load_llm_settings

# ========== 配置 ==========
LLM_SETTINGS = load_llm_settings()

# 模型名称（
MODEL_DEEPSEEK = os.getenv("MODEL_DEEPSEEK", "deepseek-v4-pro-260425")
MODEL_DOUBAO = os.getenv("MODEL_DOUBAO", "doubao-seed-2-0-pro-260215")

# 文件路径
SCRIPT_DIR = Path(__file__).parent
INPUT_JSON = SCRIPT_DIR / "data/agent_log.json"  # 确保包含 predict 字段
OUTPUT_CSV = SCRIPT_DIR / "data/judge_results.csv"  # 可选，保存详细结果

# 是否保存详细日志
SAVE_DETAILS = True

# 多线程配置
MAX_WORKERS = 20  # 最大线程数，可根据 API 限流情况调整

# ========== 初始化客户端 ==========
client = OpenAI(
    api_key=LLM_SETTINGS["api_key"],
    base_url=LLM_SETTINGS["base_url"],
)

# 线程安全的计数器
counter_lock = Lock()
completed_count = 0
total_count = 0

# ========== 评判 Prompt ==========
JUDGE_PROMPT_TEMPLATE = """你是一个文本相似度判断专家。请判断下面两段文本是否在**语义上相似**（即表达的意思、核心信息、逻辑走向是否一致）。。

只回答"是"或"否"，不要输出任何其他内容。

真实上文：
{real_top}

文本A（真实下文）：
{real_bottom}

文本B（预测下文）：
{predict}

问题：文本B与文本A在语义上是否相似？回答（是/否）："""


def call_judge(real_bottom, predict, real_top, model_name, max_retries=2):
    """调用模型判断相似性，返回 1（相似）或 0（不相似）"""
    prompt = JUDGE_PROMPT_TEMPLATE.format(real_top=real_top, real_bottom=real_bottom, predict=predict)
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,  # 只需要一个"是"或"否"
                temperature=0.0,  # 确定性输出
            )
            answer = response.choices[0].message.content.strip()
            # 解析答案
            if answer == "是":
                return 1
            elif answer == "否":
                return 0
            else:
                # 如果输出不是预期，尝试模糊匹配
                if "是" in answer:
                    return 1
                else:
                    return 0
        except Exception as e:
            print(f"  调用失败 (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return 0  # 重试失败则判为 0 分


def judge_single_article(idx, art):
    """评判单篇文章，返回结果"""
    global completed_count

    real_bottom = art["article_bottom"]
    predict = art["predict"]
    real_top = art["article_top"]
    title = art.get("title", f"第{idx + 1}篇")

    print(f"\n正在评判第 {idx + 1}/{total_count} 篇：{title[:40]}...")

    # DeepSeek 评判
    print("  → DeepSeek 判断中...")
    score_ds = call_judge(real_bottom, predict, real_top, MODEL_DEEPSEEK)
    print(f"    DeepSeek 得分: {score_ds}")

    # Doubao 评判
    print("  → Doubao 判断中...")
    score_db = call_judge(real_bottom, predict, real_top, MODEL_DOUBAO)
    print(f"    Doubao 得分: {score_db}")

    # 更新完成计数
    with counter_lock:
        completed_count += 1
        print(f"✅ 已完成 {completed_count}/{total_count} 条")

    # 记录详情
    return {
        "index": idx,
        "title": title,
        "deepseek_score": score_ds,
        "doubao_score": score_db,
    }


# ========== 主流程 ==========
def main():
    global total_count, completed_count

    # 1. 加载数据
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        articles = json.load(f)

    total_count = len(articles)
    completed_count = 0

    print(f"已加载 {total_count} 篇文章")
    print(f"开始多线程评判，最大线程数: {MAX_WORKERS}")
    print("=" * 80)

    # 检查是否有 predict 字段
    if "predict" not in articles[0]:
        raise ValueError("JSON 文件中缺少 'predict' 字段，请确保每条数据都包含你自己生成的预测下文。")

    # 存储结果
    results = []
    total_ds = 0
    total_db = 0

    # 2. 多线程逐篇评判
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(judge_single_article, idx, art): idx
            for idx, art in enumerate(articles)
        }

        # 收集结果（按完成顺序）
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                results.append(result)
                total_ds += result["deepseek_score"]
                total_db += result["doubao_score"]

                # 避免 API 限流，稍微延迟
                time.sleep(random.uniform(0.2, 0.5))
            except Exception as e:
                print(f"\n❌ 任务异常 [第 {idx + 1} 篇]: {e}")

    # 按原始索引排序结果
    results.sort(key=lambda x: x["index"])

    # 3. 输出总成绩
    print("\n" + "=" * 50)
    print(f"DeepSeek 总分: {total_ds} / {len(articles)}  (准确率: {total_ds / len(articles) * 100:.2f}%)")
    print(f"Doubao   总分: {total_db} / {len(articles)}  (准确率: {total_db / len(articles) * 100:.2f}%)")
    print("=" * 50)

    # 4. 保存详细结果（可选）
    if SAVE_DETAILS:
        import csv
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["index", "title", "deepseek_score", "doubao_score"])
            writer.writeheader()
            writer.writerows(results)
        print(f"\n详细结果已保存至 {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
