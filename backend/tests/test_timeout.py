import pytest
from tests.conftest import insert_timeout
from app.engine.timeout import TimeoutEngine

engine = TimeoutEngine()


def test_recommends_timeout_when_run_continues_less(db_path):
    insert_timeout(db_path, [
        ("7-0", "4th", 1, 0.30, -2.5, 200),   # with timeout: 30% run continues
        ("7-0", "4th", 0, 0.65, 3.0, 200),     # without timeout: 65% run continues
    ])
    result = engine.evaluate(
        {"opponent_run": "7-0", "quarter": "4th", "timeouts_remaining": "2"},
        db_path,
    )
    assert result.recommended_action == "call timeout"
    assert result.primary_stat == 30.0
    assert result.comparison_stat == 65.0
    assert result.primary_sample_size == 200
    assert result.confidence in ("high", "moderate")


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"opponent_run": "7-0", "quarter": "4th", "timeouts_remaining": "2"},
        db_path,
    )
    assert result.insufficient_data is True


def test_low_sample_warning(db_path):
    insert_timeout(db_path, [
        ("5-0", "1st", 1, 0.20, 0.0, 10),
        ("5-0", "1st", 0, 0.50, 0.0, 10),
    ])
    result = engine.evaluate(
        {"opponent_run": "5-0", "quarter": "1st", "timeouts_remaining": "2"},
        db_path,
    )
    assert result.low_sample_warning is True


def test_scarce_timeout_note_in_details(db_path):
    insert_timeout(db_path, [
        ("5-0", "1st", 1, 0.20, 0.0, 200),
        ("5-0", "1st", 0, 0.50, 0.0, 200),
    ])
    result = engine.evaluate(
        {"opponent_run": "5-0", "quarter": "1st", "timeouts_remaining": "1"},
        db_path,
    )
    assert result.details.get("timeout_scarcity_warning") is True
    assert "saving" in result.recommended_action.lower()


def test_input_schema_has_3_fields():
    schema = engine.input_schema
    assert len(schema["fields"]) == 3
