"""
OpenAI GPT-4o narrative layer.
Takes a pre-computed DecisionResult and returns 2-3 plain-English sentences for coaches.
The AI NEVER computes, alters, or rounds any numbers — it only narrates them.
"""
import json
import logging
from dataclasses import asdict
from app.engine.base import DecisionResult
from app.config import OPENAI_API_KEY

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a basketball analytics assistant speaking directly to a coach during a live game. Your job is to narrate pre-computed statistics in plain, practical English.

STRICT RULES:
- You receive a JSON object containing exact statistics. NEVER invent, round, estimate, or alter ANY number. Use the exact values provided.
- Keep your response to 2-3 sentences maximum. Coaches are reading this mid-game on their phone.
- Be direct and practical. Say what to do and why the numbers support it. No hedging, no "it depends", no preamble.
- Always mention the sample size naturally. Example: "Based on 1,247 similar situations..."
- If the data includes a low sample size warning, acknowledge it briefly: "Note: small sample — treat as directional."
- If the data shows insufficient data, say so directly: "Not enough historical data to make a call here."
- Never say "I think" or "I believe". You are reporting data, not opinions.
- Never suggest the coach consider factors not in the data. Just report what the numbers say.
- Refer to the coach's team as "you" and the opponent as "they/them"."""


def _build_fallback(result: DecisionResult) -> str:
    """Plain-text fallback when OpenAI is unavailable."""
    if result.insufficient_data:
        return "Not enough historical data to make a recommendation here."
    text = (
        f"{result.recommended_action.title()}: "
        f"{result.primary_stat_label} is {result.primary_stat} "
        f"(n={result.primary_sample_size})."
    )
    if result.comparison_stat is not None and result.comparison_stat_label:
        text += (
            f" {result.comparison_stat_label}: {result.comparison_stat} "
            f"(n={result.comparison_sample_size})."
        )
    if result.low_sample_warning:
        text += " ⚠️ Small sample — treat as directional."
    return text


def narrate(result: DecisionResult, display_name: str | None = None) -> tuple[str, bool]:
    """
    Narrate a DecisionResult using GPT-4o.

    Returns:
        (narrative_text: str, narrative_available: bool)
        If OpenAI fails, returns (fallback_text, False).
    """
    # Never call OpenAI for insufficient data — return fallback
    if result.insufficient_data:
        return _build_fallback(result), False

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — using fallback narrative")
        return _build_fallback(result), False

    try:
        if OpenAI is None:
            raise ImportError("openai package not installed")
        client = OpenAI(api_key=OPENAI_API_KEY)

        user_message = json.dumps(
            {
                "decision_type": result.decision_type,
                "display_name": display_name or result.decision_type,
                "result": asdict(result),
            },
            default=str,
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=200,
            temperature=0.3,  # Low temperature for consistent factual narration
        )

        narrative = response.choices[0].message.content.strip()
        return narrative, True

    except Exception as exc:
        logger.warning(f"OpenAI narration failed: {exc}. Using fallback.")
        return _build_fallback(result), False
