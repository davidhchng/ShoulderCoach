import pytest
from tests.conftest import insert_three_vs_two
from app.engine.three_vs_two import ThreeVsTwoEngine, OT_WIN_RATE

engine = ThreeVsTwoEngine()


def test_down_2_recommends_best_win_probability(db_path):
    # 3PT make_pct = 0.33, 2PT make_pct = 0.50
    # P(win|3) = 0.33, P(win|2) = 0.50 * 0.50 = 0.25
    insert_three_vs_two(db_path, [
        ("2", "5-15s", 0, "3pt", 0.33, 0.33, 200),
        ("2", "5-15s", 0, "2pt", 0.50, 0.25, 200),
    ])
    result = engine.evaluate(
        {"down_by": "2", "seconds_remaining": "5-15s", "has_timeout": False},
        db_path,
    )
    assert result.recommended_action == "go for the 3"
    assert result.primary_stat == 33.0
    assert abs(result.comparison_stat - 25.0) < 0.1


def test_down_2_recommends_2pt_when_ot_better(db_path):
    # 3PT make_pct = 0.25, 2PT make_pct = 0.55
    # P(win|3) = 0.25, P(win|2) = 0.55 * 0.50 = 0.275
    insert_three_vs_two(db_path, [
        ("2", "<5s", 0, "3pt", 0.25, 0.25, 200),
        ("2", "<5s", 0, "2pt", 0.55, 0.275, 200),
    ])
    result = engine.evaluate(
        {"down_by": "2", "seconds_remaining": "<5s", "has_timeout": False},
        db_path,
    )
    assert result.recommended_action == "play for 2 and OT"


def test_down_3_always_go_for_3(db_path):
    insert_three_vs_two(db_path, [
        ("3", "5-15s", 0, "3pt", 0.35, 0.30, 200),
        ("3", "5-15s", 0, "2pt", 0.50, 0.02, 100),
    ])
    result = engine.evaluate(
        {"down_by": "3", "seconds_remaining": "5-15s", "has_timeout": False},
        db_path,
    )
    assert result.recommended_action == "go for the 3"


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"down_by": "3", "seconds_remaining": "5-15s", "has_timeout": False},
        db_path,
    )
    assert result.insufficient_data is True


def test_low_sample_warning(db_path):
    insert_three_vs_two(db_path, [
        ("3", "<5s", 1, "3pt", 0.35, 0.30, 20),
        ("3", "<5s", 1, "2pt", 0.50, 0.02, 5),
    ])
    result = engine.evaluate(
        {"down_by": "3", "seconds_remaining": "<5s", "has_timeout": True},
        db_path,
    )
    assert result.low_sample_warning is True


def test_timeout_note_included_in_details_down_3(db_path):
    insert_three_vs_two(db_path, [
        ("3", "5-15s", 1, "3pt", 0.38, 0.32, 200),
        ("3", "5-15s", 1, "2pt", 0.48, 0.02, 100),
    ])
    result = engine.evaluate(
        {"down_by": "3", "seconds_remaining": "5-15s", "has_timeout": True},
        db_path,
    )
    assert result.details.get("timeout_note") is not None


def test_input_schema_has_3_fields():
    assert len(engine.input_schema["fields"]) == 3
