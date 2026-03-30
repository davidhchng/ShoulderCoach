import pytest
from tests.conftest import insert_zone
from app.engine.zone_vs_man import ZoneVsManEngine

engine = ZoneVsManEngine()


def test_recommends_man_when_opponent_hot_3pt(db_path):
    insert_zone(db_path, [
        ("hot", 0, "zone", 1.12, 0.23, 0.38, 1000),
        ("hot", 0, "man", 1.00, 0.29, 0.27, 1000),
    ])
    result = engine.evaluate(
        {"opponent_3pt_tonight": "Hot (>40%)", "driving_a_lot": False, "score_situation": "Close"},
        db_path,
    )
    assert result.recommended_action == "stay in man"


def test_recommends_zone_when_cold_3pt(db_path):
    insert_zone(db_path, [
        ("cold", 0, "zone", 0.92, 0.22, 0.32, 1000),
        ("cold", 0, "man", 1.02, 0.30, 0.25, 1000),
    ])
    result = engine.evaluate(
        {"opponent_3pt_tonight": "Cold (<30%)", "driving_a_lot": False, "score_situation": "Close"},
        db_path,
    )
    assert result.recommended_action == "switch to zone"
    assert result.primary_stat == 0.92
    assert result.comparison_stat == 1.02


def test_tradeoff_details_populated(db_path):
    insert_zone(db_path, [
        ("normal", 0, "zone", 0.99, 0.24, 0.31, 1000),
        ("normal", 0, "man", 1.00, 0.30, 0.26, 1000),
    ])
    result = engine.evaluate(
        {"opponent_3pt_tonight": "Normal", "driving_a_lot": False, "score_situation": "Close"},
        db_path,
    )
    assert "zone_reduces_paint_pct" in result.details
    assert "zone_increases_3pt_attempt_rate" in result.details


def test_no_data_returns_insufficient(db_path):
    result = engine.evaluate(
        {"opponent_3pt_tonight": "Normal", "driving_a_lot": False, "score_situation": "Close"},
        db_path,
    )
    assert result.insufficient_data is True


def test_input_schema_has_3_fields():
    assert len(engine.input_schema["fields"]) == 3
