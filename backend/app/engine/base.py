from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionResult:
    """Universal result container for all decision types."""
    decision_type: str
    recommended_action: str          # e.g. "foul", "call timeout", "play 2-for-1"
    confidence: str                  # "high", "moderate", "low", "insufficient"
    primary_stat: float              # main probability/percentage driving the rec
    primary_stat_label: str          # e.g. "Win % when fouling"
    primary_sample_size: int
    comparison_stat: float | None = None
    comparison_stat_label: str | None = None
    comparison_sample_size: int | None = None
    edge_pct: float | None = None    # difference between primary and comparison
    details: dict = field(default_factory=dict)  # engine-specific extra data
    low_sample_warning: bool = False
    insufficient_data: bool = False


class DecisionEngine(ABC):
    """All engines implement this interface."""

    @property
    @abstractmethod
    def decision_type(self) -> str:
        """Unique key: 'foul_up_3', 'timeout', etc."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human label: 'Foul Up 3', 'Call Timeout', etc."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description shown on the home screen."""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """
        Describes the 3-4 input fields for this decision.
        Format:
        {
            "fields": [
                {
                    "key": "seconds_remaining",
                    "label": "Time Left",
                    "type": "button_group",
                    "options": ["<10s", "10-30s", "30-60s"],
                    "default": "<10s"
                },
                ...
            ]
        }
        """
        ...

    @abstractmethod
    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        """
        Pure deterministic computation. No AI, no network calls.
        `inputs` keys match the `key` fields in input_schema.
        """
        ...
