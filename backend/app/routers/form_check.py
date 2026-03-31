"""
POST /api/form-check  — multipart video upload → biomechanical analysis + GPT note + annotated video
GET  /api/form-check/video/{video_id} — stream annotated video file
"""
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import OPENAI_API_KEY

router = APIRouter()
logger = logging.getLogger(__name__)

# ── temp video cache: video_id → file_path, expires after 30 min ─────────────
_video_cache: dict[str, tuple[str, float]] = {}  # id → (path, created_at)
_CACHE_TTL = 1800  # seconds


def _cleanup_old_videos():
    now = time.time()
    expired = [vid for vid, (path, ts) in _video_cache.items() if now - ts > _CACHE_TTL]
    for vid in expired:
        path, _ = _video_cache.pop(vid)
        try:
            os.unlink(path)
        except OSError:
            pass


def _store_video(path: str) -> str:
    _cleanup_old_videos()
    vid = str(uuid.uuid4())
    _video_cache[vid] = (path, time.time())
    return vid


# ── GPT narration ─────────────────────────────────────────────────────────────
FORM_COACH_SYSTEM = (
    "You are ShoulderCoach, a shooting form coach. "
    "Given biomechanical metrics from a video analysis, give 2-3 sentences of specific coaching feedback. "
    "Reference the exact numbers. Be direct and practical. Speak to the coach or player with no hedging. "
    "Do not use em dashes or dashes of any kind. Use plain sentences only."
)


def _narrate(metrics: list[dict], passing: int, total: int) -> str:
    if not OPENAI_API_KEY:
        issues = [m["note"] for m in metrics if m.get("in_range") is False]
        return " ".join(issues[:2]) if issues else f"{passing}/{total} metrics in range."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        metrics_json = json.dumps(
            [{"name": m["name"], "value": m["value"], "unit": m["unit"],
              "in_range": m["in_range"], "ideal_range": m["ideal_range"], "note": m["note"]}
             for m in metrics], indent=2)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": FORM_COACH_SYSTEM},
                {"role": "user", "content": f"Metrics ({passing}/{total} passing):\n{metrics_json}"},
            ],
            max_tokens=200, temperature=0.4,
        )
        text = resp.choices[0].message.content.strip()
        return text.replace("\u2014", " ").replace("\u2013", " to ")
    except Exception as exc:
        logger.warning(f"GPT narration failed: {exc}")
        issues = [m["note"] for m in metrics if m.get("in_range") is False]
        return " ".join(issues[:2]) if issues else f"{passing}/{total} metrics in range."


# ── models ────────────────────────────────────────────────────────────────────
class FormMetric(BaseModel):
    name: str
    key: str
    value: Optional[float] = None
    unit: str
    ideal_range: str
    in_range: Optional[bool] = None
    note: str


class FormCheckResponse(BaseModel):
    metrics: list[FormMetric]
    passing: int
    total: int
    frames_analyzed: int
    phase_detected: bool
    narrative: str
    video_id: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────────────
@router.post("/form-check", response_model=FormCheckResponse)
async def form_check(video: UploadFile = File(...)):
    content_type = video.content_type or ""
    filename = video.filename or "video.mp4"
    if not content_type.startswith("video/") and not filename.lower().endswith(
        (".mp4", ".mov", ".avi", ".webm", ".mkv")
    ):
        raise HTTPException(status_code=400, detail="Upload must be a video file (mp4, mov, etc.)")

    suffix = os.path.splitext(filename)[1] or ".mp4"
    input_tmp = None
    output_tmp = None
    try:
        # Save upload to temp file
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            input_tmp = f.name
            f.write(await video.read())

        from app.engine.shooting_form import analyze_shooting_form, generate_annotated_video
        analysis = analyze_shooting_form(input_tmp)

        # Generate annotated video in a named temp file (keep it for serving)
        out_f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        output_tmp = out_f.name
        out_f.close()

        video_id = None
        ok = generate_annotated_video(input_tmp, analysis, output_tmp)
        if ok and os.path.getsize(output_tmp) > 0:
            video_id = _store_video(output_tmp)
            output_tmp = None  # don't delete — it's in the cache now

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if input_tmp and os.path.exists(input_tmp):
            os.unlink(input_tmp)
        if output_tmp and os.path.exists(output_tmp):
            os.unlink(output_tmp)

    metrics  = analysis["metrics"]
    passing  = analysis["passing"]
    total    = analysis["total"]
    narrative = _narrate(metrics, passing, total)

    return FormCheckResponse(
        metrics=[FormMetric(**m) for m in metrics],
        passing=passing,
        total=total,
        frames_analyzed=analysis["frames_analyzed"],
        phase_detected=analysis["phase_detected"],
        narrative=narrative,
        video_id=video_id,
    )


@router.get("/form-check/video/{video_id}")
def get_video(video_id: str):
    entry = _video_cache.get(video_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Video not found or expired")
    path, _ = entry
    if not os.path.exists(path):
        _video_cache.pop(video_id, None)
        raise HTTPException(status_code=404, detail="Video file missing")
    return FileResponse(path, media_type="video/mp4",
                        headers={"Cache-Control": "no-cache"})
