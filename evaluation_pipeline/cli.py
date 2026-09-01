from .runner import BatchEvaluator
from .settings import load_settings


def main() -> None:
    """加载评测配置并启动批量评测。"""
    evaluator = BatchEvaluator(load_settings())
    evaluator.run()
