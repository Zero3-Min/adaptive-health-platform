"""评分器单元测试（无需数据库）。"""

from __future__ import annotations

from core.evaluation import Dimension, HeuristicCoachEvaluator

evaluator = HeuristicCoachEvaluator()

GOOD_REPLY = """\
考虑到你昨晚只睡了 5.5 小时、情绪评分 4 分，今天不适合上强度。建议：
1. 30 分钟低强度游泳（配合你的膝盖情况，避免深蹲类动作的替代选择）
2. 傍晚散步 20 分钟，目标 6000 步
3. 22:30 前上床，目标睡眠 7.5 小时"""

VAGUE_REPLY = "多运动，注意休息，饮食均衡就好。"


class TestSpecificity:
    def test_quantified_reply_scores_high(self) -> None:
        result = evaluator.evaluate(GOOD_REPLY, [], [])
        assert result.scores[Dimension.SPECIFICITY] == 1.0

    def test_vague_reply_scores_zero(self) -> None:
        result = evaluator.evaluate(VAGUE_REPLY, [], [])
        assert result.scores[Dimension.SPECIFICITY] == 0.0


class TestPersonalization:
    def test_citing_user_data_scores(self) -> None:
        result = evaluator.evaluate(GOOD_REPLY, ["5.5", "膝", "4"], [])
        assert result.scores[Dimension.PERSONALIZATION] == 1.0

    def test_ignoring_user_data_scores_zero(self) -> None:
        result = evaluator.evaluate(VAGUE_REPLY, ["5.5", "膝", "4"], [])
        assert result.scores[Dimension.PERSONALIZATION] == 0.0

    def test_no_terms_is_full_score(self) -> None:
        assert evaluator.evaluate(VAGUE_REPLY, [], []).scores[Dimension.PERSONALIZATION] == 1.0


class TestSafety:
    def test_violation_detected(self) -> None:
        reply = "今天做 5 组深蹲，每组 12 次。"
        result = evaluator.evaluate(reply, [], ["深蹲", "跳跃"])
        assert result.scores[Dimension.SAFETY] == 0.5

    def test_mentioning_avoidance_is_not_violation(self) -> None:
        reply = "记得避免深蹲，改为坐姿腿屈伸 3 组。"
        result = evaluator.evaluate(reply, [], ["深蹲"])
        assert result.scores[Dimension.SAFETY] == 1.0

    def test_clean_reply(self) -> None:
        assert evaluator.evaluate(GOOD_REPLY, [], ["跳跃"]).scores[Dimension.SAFETY] == 1.0


class TestActionability:
    def test_numbered_plan_scores_high(self) -> None:
        assert evaluator.evaluate(GOOD_REPLY, [], []).scores[Dimension.ACTIONABILITY] == 1.0

    def test_prose_scores_low(self) -> None:
        assert evaluator.evaluate(VAGUE_REPLY, [], []).scores[Dimension.ACTIONABILITY] == 0.0


class TestTotal:
    def test_total_is_mean(self) -> None:
        result = evaluator.evaluate(GOOD_REPLY, ["5.5", "膝"], ["跳跃"])
        assert result.total == sum(result.scores.values()) / 4
        assert result.total > 0.9


# ---------------------------------------------------------------------------
# Reflection 评分器
# ---------------------------------------------------------------------------
from core.evaluation.reflection_evaluator import (  # noqa: E402
    HeuristicReflectionEvaluator,
    ReflectionDimension,
)

reflection_evaluator = HeuristicReflectionEvaluator()

GOOD_JSON = (
    '{"insights": [{"content": "过去 3 天平均睡眠 5.4 小时，次日情绪均值下降 2 分",'
    ' "category": "sleep", "confidence": 0.8}], "strategy_suggestions": []}'
)


class TestReflectionEvaluator:
    def test_pure_json_full_scores(self) -> None:
        result = reflection_evaluator.evaluate(GOOD_JSON)
        assert result.scores[ReflectionDimension.FORMAT] == 1.0
        assert result.scores[ReflectionDimension.EVIDENCE] == 1.0
        assert result.scores[ReflectionDimension.CATEGORY] == 1.0
        assert result.scores[ReflectionDimension.CALIBRATION] == 1.0

    def test_fenced_json_penalized_format(self) -> None:
        result = reflection_evaluator.evaluate(f"```json\n{GOOD_JSON}\n```")
        assert result.scores[ReflectionDimension.FORMAT] == 0.5

    def test_unparseable_scores_zero(self) -> None:
        result = reflection_evaluator.evaluate("I cannot analyze this data.")
        assert result.total == 0.0

    def test_invalid_category_penalized(self) -> None:
        bad = GOOD_JSON.replace('"sleep"', '"vibes"')
        result = reflection_evaluator.evaluate(bad)
        assert result.scores[ReflectionDimension.CATEGORY] == 0.0

    def test_no_numbers_penalizes_evidence(self) -> None:
        bad = (
            '{"insights": [{"content": "睡眠似乎不太好", "category": "sleep",'
            ' "confidence": 0.8}], "strategy_suggestions": []}'
        )
        result = reflection_evaluator.evaluate(bad)
        assert result.scores[ReflectionDimension.EVIDENCE] == 0.0

    def test_extreme_confidence_penalized(self) -> None:
        bad = GOOD_JSON.replace("0.8", "1.0")
        result = reflection_evaluator.evaluate(bad)
        assert result.scores[ReflectionDimension.CALIBRATION] == 0.0

    def test_empty_insights_neutral(self) -> None:
        result = reflection_evaluator.evaluate('{"insights": [], "strategy_suggestions": []}')
        assert result.scores[ReflectionDimension.FORMAT] == 1.0
        assert result.scores[ReflectionDimension.EVIDENCE] == 0.5
