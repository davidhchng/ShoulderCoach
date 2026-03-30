from pydantic import BaseModel
from typing import Any


class DecisionRequest(BaseModel):
    inputs: dict[str, Any]


class ParseRequest(BaseModel):
    description: str


class ParseResponse(BaseModel):
    inputs: dict[str, Any]
    confidence: str  # "high", "low" — how confident GPT was in the parse


class DecisionResponse(BaseModel):
    decision_type: str
    recommended_action: str
    confidence: str
    primary_stat: float
    primary_stat_label: str
    primary_sample_size: int
    comparison_stat: float | None = None
    comparison_stat_label: str | None = None
    comparison_sample_size: int | None = None
    edge_pct: float | None = None
    details: dict[str, Any] = {}
    low_sample_warning: bool = False
    insufficient_data: bool = False
    narrative: str = ""
    narrative_available: bool = True
