import pytest
from tests.conftest import insert_foul_up_3
from app.engine.foul_up_3 import FoulUp3Engine


engine = FoulUp3Engine()


def test_recommends_foul_when_higher_win_pct(db_path):
    insert_foul_up_3(db_path, [
        ("<10s", "foul", "average", 842, 158, 1000, 0.842),
        ("<10s", "no_foul", "average", 781, 219, 1000, 0.781),
    ])
    result = engine.evaluate(
        {"time_remaining": "<10s", "opponent_has_ball": True, "opponent_shooting": "Average"},
        db_path,
    )
    assert result.recommended_action == "foul"
    assert result.primary_stat == 84.2
    assert result.primary_sample_size == 1000
    assert result.comparison_stat == 78.1
    assert result.edge_pct == 6.1
    assert result.confidence == "high"
    assert not result.low_sample_warning
    assert not result.insufficient_data


def test_recommends_no_foul_when_no_foul_better(db_path):
    insert_foul_up_3(db_path, [
        ("30-60s", "foul", "strong", 600, 400, 1000, 0.60),
        ("30-60s", "no_foul", "strong", 720, 280, 1000, 0.72),
    ])
    result = engine.evaluate(
        {"time_remaining": "30-60s", "opponent_has_ball": True, "opponent_shooting": "Strong"},
        db_path,
    )
    assert result.recommended_action == "don't foul"
    assert result.primary_stat == 72.0


def test_low_sample_warning(db_path):
    insert_foul_up_3(db_path, [
        ("<10s", "foul", "strong", 20, 5, 25, 0.80),
        ("<10s", "no_foul", "strong", 15, 8, 23, 0.65),
    ])
    result = engine.evaluate(
        {"time_remaining": "<10s", "opponent_has_ball": True, "opponent_shooting": "Strong"},
        db_path,
    )
    assert result.low_sample_warning is True
    assert result.confidence == "low"


def test_insufficient_data_when_n_below_5(db_path):
    insert_foul_up_3(db_path, [
        ("<10s", "foul", "average", 3, 1, 4, 0.75),
        ("<10s", "no_foul", "average", 2, 2, 4, 0.50),
    ])
    result = engine.evaluate(
        {"time_remaining": "<10s", "opponent_has_ball": True, "opponent_shooting": "Average"},
        db_path,
    )
    assert result.insufficient_data is True
    assert result.confidence == "insufficient"


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"time_remaining": "<10s", "opponent_has_ball": True, "opponent_shooting": "Average"},
        db_path,
    )
    assert result.insufficient_data is True


def test_input_schema_has_3_fields():
    schema = engine.input_schema
    assert len(schema["fields"]) == 3
    keys = {f["key"] for f in schema["fields"]}
    assert "time_remaining" in keys
    assert "opponent_has_ball" in keys
    assert "opponent_shooting" in keys
