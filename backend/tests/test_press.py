import pytest
from tests.conftest import insert_press
from app.engine.press import PressEngine

engine = PressEngine()


def test_recommends_press_when_down_10_plus(db_path):
    insert_press(db_path, [
        ("down_10_plus", "2-5min", "4th", 1, 18.0, 1.02, 5.0, 500),
        ("down_10_plus", "2-5min", "4th", 0, 10.0, 1.05, 2.0, 500),
    ])
    result = engine.evaluate(
        {"score_differential": "Down 10+", "time_remaining": "2-5 min", "quarter": "4th"},
        db_path,
    )
    assert result.recommended_action == "press full court"
    assert result.primary_stat > 0
    assert result.primary_sample_size == 500


def test_down_1_5_recommends_no_press(db_path):
    insert_press(db_path, [
        ("down_1_5", "5+min", "4th", 1, 12.0, 1.02, 4.0, 500),
        ("down_1_5", "5+min", "4th", 0, 9.0, 1.04, 2.0, 500),
    ])
    result = engine.evaluate(
        {"score_differential": "Down 1-5", "time_remaining": "5+ min", "quarter": "4th"},
        db_path,
    )
    assert "don't press" in result.recommended_action.lower()


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"score_differential": "Down 5-10", "time_remaining": "2-5 min", "quarter": "4th"},
        db_path,
    )
    assert result.insufficient_data is True


def test_details_include_tradeoff_data(db_path):
    insert_press(db_path, [
        ("down_5_10", "2-5min", "4th", 1, 15.0, 1.02, 5.0, 300),
        ("down_5_10", "2-5min", "4th", 0, 9.0, 1.05, 2.0, 300),
    ])
    result = engine.evaluate(
        {"score_differential": "Down 5-10", "time_remaining": "2-5 min", "quarter": "4th"},
        db_path,
    )
    assert "extra_turnovers_per_100_poss" in result.details
    assert "extra_fast_break_pts_allowed_per_100_poss" in result.details


def test_input_schema_has_3_fields():
    assert len(engine.input_schema["fields"]) == 3
