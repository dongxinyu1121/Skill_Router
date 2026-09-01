from .runner import BatchEvaluator
from .settings import load_settings


def main() -> None:
    evaluator = BatchEvaluator(load_settings())
    evaluator.run()
