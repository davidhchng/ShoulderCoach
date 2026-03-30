import pytest
from tests.conftest import insert_hack
from app.engine.hack_a_player import HackAPlayerEngine

engine = HackAPlayerEngine()


def test_recommends_hack_when_ppp_much_lower(db_path):
    insert_hack(db_path, [
        ("<50%", "down_5_plus", "<2min", 0.80, 1.05, 200, 1000),
    ])
    result = engine.evaluate(
        {"opponent_ft_pct": "<50%", "score_differential": "Down 5+", "time_remaining": "<2 min"},
        db_path,
    )
    assert result.recommended_action == "hack them"
    assert result.primary_stat == 0.80
    assert result.comparison_stat == 1.05
    assert result.primary_sample_size == 200


def test_does_not_recommend_hack_when_ppp_similar(db_path):
    insert_hack(db_path, [
        ("60-70%", "within_4", "2-5min", 1.25, 1.05, 200, 1000),
    ])
    result = engine.evaluate(
        {"opponent_ft_pct": "60-70%", "score_differential": "Within 4", "time_remaining": "2-5 min"},
        db_path,
    )
    assert result.recommended_action == "don't hack"


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"opponent_ft_pct": "<50%", "score_differential": "Down 5+", "time_remaining": "<2 min"},
        db_path,
    )
    assert result.insufficient_data is True


def test_low_sample_warning(db_path):
    insert_hack(db_path, [
        ("<50%", "up", "5+min", 0.80, 1.05, 15, 1000),
    ])
    result = engine.evaluate(
        {"opponent_ft_pct": "<50%", "score_differential": "Up", "time_remaining": "5+ min"},
        db_path,
    )
    assert result.low_sample_warning is True


def test_winning_and_small_advantage_no_hack(db_path):
    insert_hack(db_path, [
        ("60-70%", "up", "<2min", 0.95, 1.05, 200, 1000),
    ])
    result = engine.evaluate(
        {"opponent_ft_pct": "60-70%", "score_differential": "Up", "time_remaining": "<2 min"},
        db_path,
    )
    assert result.recommended_action == "don't hack"


def test_input_schema_has_3_fields():
    assert len(engine.input_schema["fields"]) == 3
