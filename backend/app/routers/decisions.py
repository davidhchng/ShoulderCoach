import json
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from app.engine.registry import get_engine, ENGINES
from app.models.schemas import DecisionRequest, DecisionResponse, ParseRequest, ParseResponse
from app.narrative.narrator import narrate
from app.config import DATABASE_PATH, OPENAI_API_KEY

router = APIRouter()


@router.post("/decisions/{decision_type}/parse", response_model=ParseResponse)
def parse_inputs(decision_type: str, body: ParseRequest):
    """
    Use GPT to parse a free-text situation description into structured inputs
    for the given decision type. Returns pre-filled inputs the frontend can use.
    """
    try:
        engine = get_engine(decision_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown decision type: {decision_type}")

    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    schema = engine.input_schema
    fields = schema["fields"]

    # Build a compact schema description for GPT
    schema_desc = "\n".join(
        f'- "{f["key"]}": {f["type"]}, '
        + (f'options: {f["options"]}' if f.get("options") else f'toggle (true/false), default: {f["default"]}')
        for f in fields
    )
    defaults = {f["key"]: f["default"] for f in fields}

    system_prompt = (
        "You are a basketball input parser. Given a coach's plain-English description of a game situation, "
        "extract the structured inputs for a specific decision type. "
        "Return ONLY valid JSON with the exact keys listed. "
        "If a field is unclear, use the default value. "
        "For button_group fields, the value MUST exactly match one of the listed options. "
        "For toggle fields, use true or false."
    )

    user_prompt = (
        f"Decision type: {engine.display_name}\n"
        f"Fields:\n{schema_desc}\n"
        f"Defaults: {json.dumps(defaults)}\n\n"
        f"Coach says: \"{body.description}\"\n\n"
        f"Return JSON with keys: {[f['key'] for f in fields]}"
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)

        # Validate and sanitize — fall back to defaults for invalid values
        sanitized: dict = {}
        parse_confidence = "high"
        for f in fields:
            key = f["key"]
            val = parsed.get(key, f["default"])
            if f["type"] == "button_group" and f.get("options"):
                if val not in f["options"]:
                    val = f["default"]
                    parse_confidence = "low"
            elif f["type"] == "toggle":
                val = bool(val)
            sanitized[key] = val

        return ParseResponse(inputs=sanitized, confidence=parse_confidence)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Parse error: {exc}")


def _result_to_response(result, display_name: str) -> dict:
    """Convert a DecisionResult + narration into a response dict. Used by coach router too."""
    from dataclasses import asdict
    narrative_text, narrative_available = narrate(result, display_name=display_name)
    result_dict = asdict(result)
    result_dict["narrative"] = narrative_text
    result_dict["narrative_available"] = narrative_available
    return result_dict


@router.post("/decisions/{decision_type}", response_model=DecisionResponse)
def make_decision(decision_type: str, body: DecisionRequest):
    # 1. Look up engine
    try:
        engine = get_engine(decision_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown decision type: {decision_type}")

    # 2. Validate inputs — ensure all required field keys are present
    schema_fields = engine.input_schema.get("fields", [])
    required_keys = {f["key"] for f in schema_fields}
    missing = required_keys - set(body.inputs.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required input fields: {', '.join(sorted(missing))}",
        )

    # 3. Run the deterministic engine
    try:
        result = engine.evaluate(body.inputs, DATABASE_PATH)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Engine error: {exc}")

    # 4. Narrate (OpenAI layer — graceful fallback if unavailable)
    narrative_text, narrative_available = narrate(result, display_name=engine.display_name)

    # 5. Build response
    result_dict = asdict(result)
    return DecisionResponse(
        **result_dict,
        narrative=narrative_text,
        narrative_available=narrative_available,
    )
