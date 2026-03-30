import pytest
from tests.conftest import insert_pull_starters
from app.engine.pull_starters import PullStartersEngine

engine = PullStartersEngine()


def test_recommends_pull_when_win_pct_above_95(db_path):
    insert_pull_starters(db_path, [
        ("20-25", "3-6min", "4th", 0.97, 12, 500),
    ])
    result = engine.evaluate(
        {"score_margin": "20-25", "time_remaining": "3-6 min", "quarter": "4th"},
        db_path,
    )
    assert result.recommended_action == "pull starters"
    assert result.primary_stat == 97.0
    assert result.primary_sample_size == 500
    assert result.details["largest_comeback_from_similar_deficit"] == 12


def test_borderline_when_90_to_95(db_path):
    insert_pull_starters(db_path, [
        ("15-20", "6-10min", "4th", 0.92, 15, 300),
    ])
    result = engine.evaluate(
        {"score_margin": "15-20", "time_remaining": "6-10 min", "quarter": "4th"},
        db_path,
    )
    assert "borderline" in result.recommended_action


def test_keep_starters_when_below_90(db_path):
    insert_pull_starters(db_path, [
        ("10-15", "6-10min", "3rd", 0.85, 20, 300),
    ])
    result = engine.evaluate(
        {"score_margin": "10-15", "time_remaining": "6-10 min", "quarter": "3rd"},
        db_path,
    )
    assert result.recommended_action == "keep starters in"


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"score_margin": "15-20", "time_remaining": "3-6 min", "quarter": "4th"},
        db_path,
    )
    assert result.insufficient_data is True


def test_low_sample_warning(db_path):
    insert_pull_starters(db_path, [
        ("25+", "<3min", "4th", 0.99, 5, 20),
    ])
    result = engine.evaluate(
        {"score_margin": "25+", "time_remaining": "<3 min", "quarter": "4th"},
        db_path,
    )
    assert result.low_sample_warning is True


def test_input_schema_has_3_fields():
    assert len(engine.input_schema["fields"]) == 3
