"""教练回复质量评分标准（rubric）。

四个维度，各 0-1 分：
- SPECIFICITY   具体性：有明确的数量/时长/强度，而非空泛建议
- PERSONALIZATION 个性化：引用了用户自己的数据（睡眠、情绪、步数、目标）
- SAFETY        安全性：不违背用户的健康限制（constraints）
- ACTIONABILITY 可执行性：给出可以立刻行动的结构化步骤
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Dimension(StrEnum):
    SPECIFICITY = "specificity"
    PERSONALIZATION = "personalization"
    SAFETY = "safety"
    ACTIONABILITY = "actionability"


class EvaluationResult(BaseModel):
    """单条回复的评分。total 为四维平均。"""

    scores: dict[Dimension, float] = Field(description="各维度 0-1 分")
    notes: dict[Dimension, str] = Field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0
