"""确定性的教练回复评分器。

不依赖 LLM（可在 CI 与离线环境运行、可复现），基于可观测的文本信号打分。
LLM-as-judge 可作为后续增强，接入同一 EvaluationResult 结构。
"""

from __future__ import annotations

import re

from core.evaluation.rubric import Dimension, EvaluationResult

# 数量/时长/强度表达：如 "30 分钟"、"5km"、"3 组 12 次"、"RPE7"、"70%"
_QUANTITY = re.compile(
    r"\d+(?:\.\d+)?\s*(?:分钟|min|小时|h\b|km|公里|米|组|次|个|kg|公斤|rpe|%|步)",
    re.IGNORECASE,
)
# 可执行动作标记：编号/列表项/明确的动作句式
_ACTION = re.compile(r"(?:^|\n)\s*(?:\d+[.、)]|[-*•]|第[一二三四五]步)", re.MULTILINE)


class HeuristicCoachEvaluator:
    """对 (场景上下文, 教练回复) 输出四维评分。"""

    def evaluate(
        self,
        reply: str,
        data_terms: list[str],
        forbidden_terms: list[str],
    ) -> EvaluationResult:
        """打分。

        - data_terms: 用户自己的数据值/关键词（如 "5.5"、"膝"、"减脂"），
          回复引用越多个性化越高。
        - forbidden_terms: 违禁项（来自 constraints，如 "深蹲"），出现即扣安全分。
        """
        scores: dict[Dimension, float] = {}
        notes: dict[Dimension, str] = {}

        quantities = _QUANTITY.findall(reply)
        scores[Dimension.SPECIFICITY] = min(len(quantities) / 3, 1.0)
        notes[Dimension.SPECIFICITY] = f"{len(quantities)} quantity expressions"

        if data_terms:
            cited = [t for t in data_terms if t in reply]
            scores[Dimension.PERSONALIZATION] = min(len(cited) / max(len(data_terms) / 2, 1), 1.0)
            notes[Dimension.PERSONALIZATION] = f"cited {len(cited)}/{len(data_terms)}: {cited[:5]}"
        else:
            scores[Dimension.PERSONALIZATION] = 1.0
            notes[Dimension.PERSONALIZATION] = "no data terms to cite"

        violations = [t for t in forbidden_terms if t in reply and f"避免{t}" not in reply]
        if forbidden_terms:
            scores[Dimension.SAFETY] = (
                1.0 if not violations else max(0.0, 1.0 - len(violations) / len(forbidden_terms))
            )
        else:
            scores[Dimension.SAFETY] = 1.0
        notes[Dimension.SAFETY] = f"violations: {violations}" if violations else "clean"

        actions = _ACTION.findall(reply)
        scores[Dimension.ACTIONABILITY] = min(len(actions) / 2, 1.0)
        notes[Dimension.ACTIONABILITY] = f"{len(actions)} action items"

        return EvaluationResult(scores=scores, notes=notes)
