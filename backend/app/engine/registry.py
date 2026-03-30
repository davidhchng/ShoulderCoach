from app.engine.foul_up_3 import FoulUp3Engine
from app.engine.timeout import TimeoutEngine
from app.engine.hack_a_player import HackAPlayerEngine
from app.engine.two_for_one import TwoForOneEngine
from app.engine.zone_vs_man import ZoneVsManEngine
from app.engine.pull_starters import PullStartersEngine
from app.engine.press import PressEngine
from app.engine.three_vs_two import ThreeVsTwoEngine
from app.engine.base import DecisionEngine

ENGINES: dict[str, type] = {
    "foul_up_3": FoulUp3Engine,
    "timeout": TimeoutEngine,
    "hack_a_player": HackAPlayerEngine,
    "two_for_one": TwoForOneEngine,
    "zone_vs_man": ZoneVsManEngine,
    "pull_starters": PullStartersEngine,
    "press": PressEngine,
    "three_vs_two": ThreeVsTwoEngine,
}


def get_engine(decision_type: str) -> DecisionEngine:
    cls = ENGINES.get(decision_type)
    if not cls:
        raise ValueError(f"Unknown decision type: {decision_type}")
    return cls()


def list_engines() -> list[dict]:
    """Returns metadata for all registered engines (for the home screen)."""
    return [
        {
            "decision_type": key,
            "display_name": cls().display_name,
            "description": cls().description,
            "input_schema": cls().input_schema,
        }
        for key, cls in ENGINES.items()
    ]
