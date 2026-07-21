"""Reflection Agent 产出质量的确定性评分器。

四个维度，各 0-1 分：
- FORMAT       格式：回复可解析为合法的反思 JSON（schema 校验通过）
- EVIDENCE     证据：每条洞察引用了具体数字/用户数据
- CATEGORY     分类：category 落在受控词表内
- CALIBRATION  置信度校准：confidence 不走极端（有证据支撑的区间）
"""

from __future__ import annotations

import json
import re
from enum import StrEnum

from pydantic import BaseModel

ALLOWED_CATEGORIES = {"sleep", "training", "nutrition", "mood", "recovery", "habit"}
_HAS_NUMBER = re.compile(r"\d")


class ReflectionDimension(StrEnum):
    FORMAT = "format"
    EVIDENCE = "evidence"
    CATEGORY = "category"
    CALIBRATION = "calibration"


class ReflectionEvaluation(BaseModel):
    scores: dict[ReflectionDimension, float]
    notes: dict[ReflectionDimension, str] = {}

    @property
    def total(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


class HeuristicReflectionEvaluator:
    """对 Reflection 的原始回复（应为 JSON）打四维分。解析失败则全维度 0。"""

    def evaluate(self, raw_reply: str) -> ReflectionEvaluation:
        from agents.reflection.agent import _extract_json

        scores: dict[ReflectionDimension, float] = {}
        notes: dict[ReflectionDimension, str] = {}

        try:
            parsed = _extract_json(raw_reply)
            insights = parsed.get("insights")
            if not isinstance(insights, list):
                raise ValueError("insights is not a list")
        except (ValueError, json.JSONDecodeError) as exc:
            notes[ReflectionDimension.FORMAT] = f"unparseable: {exc}"
            return ReflectionEvaluation(scores=dict.fromkeys(ReflectionDimension, 0.0), notes=notes)

        # 纯 JSON（无围栏/杂文）满分；能提取但有包装扣一半
        stripped = raw_reply.strip()
        pure = stripped.startswith("{") and stripped.endswith("}")
        scores[ReflectionDimension.FORMAT] = 1.0 if pure else 0.5
        notes[ReflectionDimension.FORMAT] = "pure JSON" if pure else "JSON with wrapping"

        if not insights:
            # 空产出：格式合法但无从评其余维度，视为保守中性
            scores[ReflectionDimension.EVIDENCE] = 0.5
            scores[ReflectionDimension.CATEGORY] = 1.0
            scores[ReflectionDimension.CALIBRATION] = 1.0
            notes[ReflectionDimension.EVIDENCE] = "no insights produced"
            return ReflectionEvaluation(scores=scores, notes=notes)

        contents = [str(i.get("content", "")) for i in insights if isinstance(i, dict)]
        categories = [str(i.get("category", "")) for i in insights if isinstance(i, dict)]
        confidences = [float(i.get("confidence", -1.0)) for i in insights if isinstance(i, dict)]

        with_numbers = [c for c in contents if _HAS_NUMBER.search(c)]
        scores[ReflectionDimension.EVIDENCE] = len(with_numbers) / len(contents)
        notes[ReflectionDimension.EVIDENCE] = f"{len(with_numbers)}/{len(contents)} cite numbers"

        valid_categories = [c for c in categories if c in ALLOWED_CATEGORIES]
        scores[ReflectionDimension.CATEGORY] = len(valid_categories) / len(categories)
        notes[ReflectionDimension.CATEGORY] = f"invalid: {set(categories) - ALLOWED_CATEGORIES}"

        calibrated = [c for c in confidences if 0.05 <= c <= 0.95]
        scores[ReflectionDimension.CALIBRATION] = (
            len(calibrated) / len(confidences) if confidences else 0.0
        )
        notes[ReflectionDimension.CALIBRATION] = f"{len(calibrated)}/{len(confidences)} in range"

        return ReflectionEvaluation(scores=scores, notes=notes)
