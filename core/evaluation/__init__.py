"""评估框架：给 Agent 输出打分，为 evolution 闭环提供信号。"""

from core.evaluation.coach_evaluator import HeuristicCoachEvaluator
from core.evaluation.rubric import Dimension, EvaluationResult

__all__ = ["Dimension", "EvaluationResult", "HeuristicCoachEvaluator"]
