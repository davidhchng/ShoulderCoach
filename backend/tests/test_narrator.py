"""
Tests for the narrative layer.
Verifies: exact numbers pass through, fallback on failure, no AI when insufficient_data.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.engine.base import DecisionResult
from app.narrative.narrator import narrate, _build_fallback


def make_result(**kwargs) -> DecisionResult:
    defaults = dict(
        decision_type="foul_up_3",
        recommended_action="foul",
        confidence="high",
        primary_stat=84.2,
        primary_stat_label="Win % when fouling",
        primary_sample_size=1247,
        comparison_stat=78.1,
        comparison_stat_label="Win % without fouling",
        comparison_sample_size=983,
        edge_pct=6.1,
        low_sample_warning=False,
        insufficient_data=False,
    )
    defaults.update(kwargs)
    return DecisionResult(**defaults)


def test_fallback_contains_exact_numbers():
    result = make_result(primary_stat=84.2, primary_sample_size=1247)
    text = _build_fallback(result)
    assert "84.2" in text
    assert "1247" in text


def test_fallback_includes_comparison_when_present():
    result = make_result(comparison_stat=78.1, comparison_stat_label="Win % without fouling", comparison_sample_size=983)
    text = _build_fallback(result)
    assert "78.1" in text
    assert "983" in text


def test_fallback_warns_on_low_sample():
    result = make_result(low_sample_warning=True)
    text = _build_fallback(result)
    assert "small sample" in text.lower() or "directional" in text.lower()


def test_fallback_for_insufficient_data():
    result = make_result(insufficient_data=True)
    text = _build_fallback(result)
    assert "not enough" in text.lower()


def test_narrate_uses_fallback_when_no_api_key():
    result = make_result()
    with patch("app.narrative.narrator.OPENAI_API_KEY", ""):
        narrative, available = narrate(result)
    assert available is False
    assert "84.2" in narrative  # Fallback numbers present


def test_narrate_uses_fallback_when_insufficient_data():
    result = make_result(insufficient_data=True)
    # Should never call OpenAI even with a key
    with patch("app.narrative.narrator.OPENAI_API_KEY", "sk-test"):
        with patch("app.narrative.narrator.OpenAI") as mock_openai:
            narrative, available = narrate(result)
    mock_openai.assert_not_called()
    assert available is False


def test_narrate_calls_openai_with_exact_numbers():
    result = make_result(primary_stat=84.2, primary_sample_size=1247)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        "Based on 1,247 similar situations, fouling gives you an 84.2% win rate."
    )

    with patch("app.narrative.narrator.OPENAI_API_KEY", "sk-test"):
        with patch("app.narrative.narrator.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai_cls.return_value = mock_client

            narrative, available = narrate(result, display_name="Foul Up 3")

    assert available is True
    assert "84.2" in narrative
    assert "1,247" in narrative or "1247" in narrative

    # Verify OpenAI was called with the user message containing the result
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "84.2" in user_msg["content"]
    assert "1247" in user_msg["content"]


def test_narrate_falls_back_on_openai_error():
    result = make_result()
    with patch("app.narrative.narrator.OPENAI_API_KEY", "sk-test"):
        with patch("app.narrative.narrator.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("API timeout")
            mock_openai_cls.return_value = mock_client

            narrative, available = narrate(result)

    assert available is False
    assert "84.2" in narrative  # Fallback numbers still present


def test_narrate_system_prompt_not_in_user_message():
    """The system prompt rules must not be sent as user content."""
    result = make_result()
    with patch("app.narrative.narrator.OPENAI_API_KEY", "sk-test"):
        with patch("app.narrative.narrator.OpenAI") as mock_openai_cls:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Foul them."
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai_cls.return_value = mock_client

            narrate(result)

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    system_msg = next(m for m in messages if m["role"] == "system")
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "STRICT RULES" in system_msg["content"]
    assert "STRICT RULES" not in user_msg["content"]
