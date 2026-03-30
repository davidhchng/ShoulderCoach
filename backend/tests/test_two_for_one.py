import pytest
from tests.conftest import insert_two_for_one
from app.engine.two_for_one import TwoForOneEngine

engine = TwoForOneEngine()


def test_recommends_push_when_more_points(db_path):
    insert_two_for_one(db_path, [
        ("30-35s", "within_4", "1st_2nd_3rd", 1, 2.80, 200),
        ("30-35s", "within_4", "1st_2nd_3rd", 0, 2.10, 200),
    ])
    result = engine.evaluate(
        {"seconds_left": "30-35s", "score_differential": "Within 4", "quarter": "1st/2nd/3rd"},
        db_path,
    )
    assert result.recommended_action == "push for 2-for-1"
    assert result.primary_stat == 2.80
    assert result.primary_sample_size == 200


def test_recommends_normal_when_up_big_small_edge(db_path):
    insert_two_for_one(db_path, [
        ("30-35s", "up_5_plus", "1st_2nd_3rd", 1, 2.15, 200),
        ("30-35s", "up_5_plus", "1st_2nd_3rd", 0, 2.00, 200),
    ])
    result = engine.evaluate(
        {"seconds_left": "30-35s", "score_differential": "Up 5+", "quarter": "1st/2nd/3rd"},
        db_path,
    )
    assert result.recommended_action == "play normal offense"


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"seconds_left": "30-35s", "score_differential": "Within 4", "quarter": "1st/2nd/3rd"},
        db_path,
    )
    assert result.insufficient_data is True


def test_q4_note_in_details(db_path):
    insert_two_for_one(db_path, [
        ("30-35s", "within_4", "4th", 1, 2.80, 200),
        ("30-35s", "within_4", "4th", 0, 2.10, 200),
    ])
    result = engine.evaluate(
        {"seconds_left": "30-35s", "score_differential": "Within 4", "quarter": "4th"},
        db_path,
    )
    assert "note" in result.details


def test_input_schema_has_3_fields():
    assert len(engine.input_schema["fields"]) == 3
