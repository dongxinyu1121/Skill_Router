JUDGE_PROMPT_TEMPLATE = """你是一个文本相似度判断专家。请判断下面两段文本是否在**语义上相似**（即表达的意思、核心信息、逻辑走向是否一致）。。

只回答"是"或"否"，不要输出任何其他内容。

真实上文：
{real_top}

文本A（真实下文）：
{real_bottom}

文本B（预测下文）：
{predict}

问题：文本B与文本A在语义上是否相似？回答（是/否）："""


def build_prompt(real_bottom: str, predict: str, real_top: str) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(
        real_top=real_top,
        real_bottom=real_bottom,
        predict=predict,
    )


def score_answer(answer: str) -> int:
    answer = answer.strip()
    if answer == "是":
        return 1
    if answer == "否":
        return 0
    return 1 if "是" in answer else 0
