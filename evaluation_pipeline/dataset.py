import json
from pathlib import Path


def load_articles(input_json: Path) -> list[dict]:
    with open(input_json, "r", encoding="utf-8") as f:
        articles = json.load(f)
    if not isinstance(articles, list) or not articles:
        raise ValueError("输入 JSON 必须是非空列表。")
    if "predict" not in articles[0]:
        raise ValueError("JSON 文件中缺少 'predict' 字段，请确保每条数据都包含预测下文。")
    return articles


def save_results(output_csv: Path, results: list[dict]) -> None:
    import csv

    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "title", "deepseek_score", "doubao_score"],
        )
        writer.writeheader()
        writer.writerows(results)
