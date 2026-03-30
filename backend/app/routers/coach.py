"""
Free-form coaching Q&A endpoint.
When the question maps to one of the 8 decision engines, runs the engine
and grounds the AI response in real NBA stats.
"""
import json
import logging
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import OPENAI_API_KEY, DATABASE_PATH

router = APIRouter()
logger = logging.getLogger(__name__)

# ── engine routing schema ────────────────────────────────────────────────────

ENGINE_SCHEMAS = {
    "foul_up_3": {
        "description": "Should I foul when up 3 late in the game?",
        "fields": {
            "time_remaining": {"options": ["<10s", "10-30s", "30-60s"], "default": "<10s"},
            "opponent_has_ball": {"type": "bool", "default": True},
            "opponent_shooting": {"options": ["Average", "Strong", "Weak"], "default": "Average"},
        },
    },
    "timeout": {
        "description": "The other team is on a run. Call timeout?",
        "fields": {
            "opponent_run": {"options": ["5-0", "7-0", "10-0+"], "default": "7-0"},
            "quarter": {"options": ["1st", "2nd", "3rd", "4th"], "default": "4th"},
            "timeouts_remaining": {"options": ["1", "2", "3+"], "default": "2"},
        },
    },
    "hack_a_player": {
        "description": "Should I foul a bad free throw shooter intentionally (hack-a-player)?",
        "fields": {
            "opponent_ft_pct": {"options": ["<50%", "50-60%", "60-70%", ">70%"], "default": "<50%"},
            "score_differential": {"options": ["Down 5+", "Within 4", "Up 5+"], "default": "Within 4"},
            "time_remaining": {"options": ["<2 min", "2-5 min", "5+ min"], "default": "<2 min"},
        },
    },
    "two_for_one": {
        "description": "Should we push for a quick shot to get two possessions this quarter?",
        "fields": {
            "seconds_left": {"options": ["30-35s", "35-40s", "40+s"], "default": "30-35s"},
            "score_differential": {"options": ["Down 5+", "Within 4", "Up 5+"], "default": "Within 4"},
            "quarter": {"options": ["1st/2nd/3rd", "4th"], "default": "1st/2nd/3rd"},
        },
    },
    "zone_vs_man": {
        "description": "Should I switch to zone defense right now?",
        "fields": {
            "opponent_3pt_tonight": {"options": ["Cold", "Normal", "Hot"], "default": "Normal"},
            "driving_a_lot": {"type": "bool", "default": False},
            "score_situation": {"options": ["Close", "Down 5+", "Up 5+"], "default": "Close"},
        },
    },
    "pull_starters": {
        "description": "Should I pull my starters with a big lead?",
        "fields": {
            "score_margin": {"options": ["10-15", "15-20", "20-25", "25+"], "default": "15-20"},
            "time_remaining": {"options": ["<3 min", "3-6 min", "6-9 min", "9+ min"], "default": "3-6 min"},
            "quarter": {"options": ["3rd", "4th"], "default": "4th"},
        },
    },
    "press": {
        "description": "Should I press full court right now?",
        "fields": {
            "score_differential": {"options": ["Down 10+", "Down 5-10", "Down 1-5"], "default": "Down 5-10"},
            "time_remaining": {"options": ["<2 min", "2-5 min", "5+ min"], "default": "2-5 min"},
            "quarter": {"options": ["1st half", "3rd", "4th"], "default": "4th"},
        },
    },
    "three_vs_two": {
        "description": "We're down 2 or 3. Should we go for the 3 or play for a quick 2?",
        "fields": {
            "down_by": {"options": ["2", "3"], "default": "3"},
            "seconds_remaining": {"options": ["<5s", "5-15s", "15-30s"], "default": "5-15s"},
            "has_timeout": {"type": "bool", "default": False},
        },
    },
}

CLASSIFY_SYSTEM = """You are a basketball analytics routing assistant.

Given a coaching question, decide:
1. Which of the 8 decision engines best applies (or "none" if the question doesn't map to any)
2. Extract the engine inputs from the question/context

Engines: foul_up_3, timeout, hack_a_player, two_for_one, zone_vs_man, pull_starters, press, three_vs_two

Respond ONLY with valid JSON in this exact format:
{"engine": "<engine_name or none>", "inputs": {<extracted key-value pairs>}}

Use exact option values from the schema. If a value is unclear, use the default.
If no engine applies, return: {"engine": "none", "inputs": {}}"""

GROUNDED_SYSTEM = """You are ShoulderCoach — a basketball analytics assistant speaking directly to a coach during a live game.

You have been given:
1. The coach's question
2. Real NBA historical stats from our database (exact numbers, sample sizes, confidence)

Your job:
- Lead with the call (recommend action clearly)
- Reference the exact stats — never invent numbers
- Be concise: 2-4 sentences max
- Mention sample size naturally: "Based on X similar situations..."
- If confidence is low or sample is small, flag it: "Small sample — treat as directional"
- Tone: direct, confident, like a smart assistant coach

Do NOT add caveats not supported by the data. Do NOT say "I think" or "it depends"."""

GENERAL_SYSTEM = """You are ShoulderCoach — a basketball analytics assistant speaking to a coach.

Answer in 2-4 sentences. Be direct, practical, and specific.
Draw on basketball analytics principles. If the answer is situational, give the most common answer first.
No hedging. No preamble."""


# ── models ───────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    team_name: str | None = None
    opponent_name: str | None = None
    game_context: str | None = None


class AskResponse(BaseModel):
    answer: str
    available: bool
    engine_used: str | None = None
    decision_result: dict | None = None  # full DecisionResponse JSON if engine ran


# ── helpers ──────────────────────────────────────────────────────────────────

def _build_context_str(body: AskRequest) -> str:
    parts = []
    if body.team_name:
        parts.append(f"My team: {body.team_name}")
    if body.opponent_name:
        parts.append(f"Opponent: {body.opponent_name}")
    if body.game_context:
        parts.append(f"Situation: {body.game_context}")
    parts.append(f"Question: {body.question}")
    return "\n".join(parts)


def _classify_and_extract(client, context_str: str) -> tuple[str, dict]:
    """Ask GPT to identify which engine applies and extract inputs."""
    schema_hint = json.dumps(
        {k: {f: v.get("options", v.get("type", "bool")) for f, v in v["fields"].items()}
         for k, v in ENGINE_SCHEMAS.items()},
        indent=2,
    )
    prompt = f"Available engine schemas:\n{schema_hint}\n\nCoach input:\n{context_str}"
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    engine = data.get("engine", "none")
    inputs = data.get("inputs", {})
    # Fill missing fields with defaults
    if engine in ENGINE_SCHEMAS:
        for field, schema in ENGINE_SCHEMAS[engine]["fields"].items():
            if field not in inputs:
                inputs[field] = schema["default"]
    return engine, inputs


def _run_engine(engine_name: str, inputs: dict) -> dict | None:
    """Run the decision engine and return a dict ready for the response."""
    try:
        from app.engine.registry import get_engine
        from app.routers.decisions import _result_to_response
        engine = get_engine(engine_name)
        result = engine.evaluate(inputs, DATABASE_PATH)
        return _result_to_response(result, engine.display_name)
    except Exception as exc:
        logger.warning(f"Engine {engine_name} failed: {exc}")
        return None


def _narrate_with_data(client, context_str: str, engine_name: str, response: dict) -> str:
    """Generate a grounded answer using the real engine stats."""
    stats_json = json.dumps({
        "engine": engine_name,
        "recommended_action": response.get("recommended_action"),
        "confidence": response.get("confidence"),
        "primary_stat": response.get("primary_stat"),
        "primary_stat_label": response.get("primary_stat_label"),
        "primary_sample_size": response.get("primary_sample_size"),
        "comparison_stat": response.get("comparison_stat"),
        "comparison_stat_label": response.get("comparison_stat_label"),
        "comparison_sample_size": response.get("comparison_sample_size"),
        "edge_pct": response.get("edge_pct"),
        "low_sample_warning": response.get("low_sample_warning"),
        "insufficient_data": response.get("insufficient_data"),
        "details": response.get("details"),
    })
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": GROUNDED_SYSTEM},
            {"role": "user", "content": f"Coach input:\n{context_str}\n\nNBA stats:\n{stats_json}"},
        ],
        max_tokens=250,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def _general_answer(client, context_str: str) -> str:
    """Fallback: general coaching answer when no engine applies."""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": GENERAL_SYSTEM},
            {"role": "user", "content": context_str},
        ],
        max_tokens=250,
        temperature=0.5,
    )
    return resp.choices[0].message.content.strip()


# ── endpoint ─────────────────────────────────────────────────────────────────

@router.post("/coach/ask", response_model=AskResponse)
def ask_coach(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not OPENAI_API_KEY:
        return AskResponse(
            answer="AI coaching unavailable — OPENAI_API_KEY not configured.",
            available=False,
        )

    context_str = _build_context_str(body)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Step 1: classify
        engine_name, inputs = _classify_and_extract(client, context_str)

        if engine_name != "none":
            # Step 2: run engine
            decision_response = _run_engine(engine_name, inputs)

            if decision_response and not decision_response.get("insufficient_data"):
                # Step 3: grounded narrative
                answer = _narrate_with_data(client, context_str, engine_name, decision_response)
                return AskResponse(
                    answer=answer,
                    available=True,
                    engine_used=engine_name,
                    decision_result=decision_response,
                )

        # Fallback: general answer
        answer = _general_answer(client, context_str)
        return AskResponse(answer=answer, available=True, engine_used=None, decision_result=None)

    except Exception as exc:
        logger.warning(f"Coach ask failed: {exc}")
        return AskResponse(
            answer="AI coaching temporarily unavailable. Try again.",
            available=False,
        )
