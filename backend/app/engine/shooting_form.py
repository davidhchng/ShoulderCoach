"""
Shooting form analyzer using MediaPipe Pose Tasks API + OpenCV.

Public functions:
  analyze_shooting_form(video_path) -> dict
  generate_annotated_video(video_path, analysis, output_path) -> bool
"""
import math
import logging
import os
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# ── landmark indices ──────────────────────────────────────────────────────────
_R_SHOULDER = 12
_L_SHOULDER = 11
_R_ELBOW    = 14
_R_WRIST    = 16
_R_HIP      = 24
_R_KNEE     = 26
_R_ANKLE    = 28

# ── skeleton drawing config ───────────────────────────────────────────────────
_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),   # torso
    (12, 14), (14, 16),                         # right arm
    (11, 13), (13, 15),                         # left arm
    (24, 26), (26, 28),                         # right leg
    (23, 25), (25, 27),                         # left leg
]
_KEY_JOINTS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

# Phase display config — BGR colors
_PHASE_INFO = {
    "gather":        {"label": "GATHER",         "bgr": (80,  200, 80)},
    "set_point":     {"label": "SET POINT",      "bgr": (22,  115, 249)},
    "release":       {"label": "RELEASE",        "bgr": (200, 80,  200)},
    "followthrough": {"label": "FOLLOW-THROUGH", "bgr": (200, 150, 50)},
}

# Which metrics annotate which phase, and which joint to label
_PHASE_ANNOTATIONS = {
    "gather":        [("knee_bend",          _R_KNEE)],
    "set_point":     [("elbow_angle",        _R_ELBOW)],
    "release":       [("shoulder_symmetry",  _R_SHOULDER),
                      ("body_tilt",          _R_HIP)],
    "followthrough": [("wrist_followthrough", _R_WRIST)],
}

# ── model download ────────────────────────────────────────────────────────────
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
_MODEL_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "pose_landmarker_lite.task"
))


def _ensure_model() -> str:
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    if not os.path.exists(_MODEL_PATH):
        logger.info("Downloading MediaPipe pose model (~5 MB)...")
        try:
            import subprocess
            subprocess.run(["curl", "-L", "-o", _MODEL_PATH, _MODEL_URL],
                           check=True, capture_output=True)
        except Exception:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(_MODEL_URL, context=ctx) as r, \
                 open(_MODEL_PATH, "wb") as f:
                f.write(r.read())
        logger.info("Model downloaded.")
    return _MODEL_PATH


# ── math helpers ─────────────────────────────────────────────────────────────

def _angle(a, b, c) -> float:
    ax, ay = a[0] - b[0], a[1] - b[1]
    cx, cy = c[0] - b[0], c[1] - b[1]
    dot = ax * cx + ay * cy
    mag = math.sqrt(ax**2 + ay**2) * math.sqrt(cx**2 + cy**2)
    if mag == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def _vertical_angle(top, bottom) -> float:
    dx = top[0] - bottom[0]
    dy = bottom[1] - top[1]
    return abs(math.degrees(math.atan2(abs(dx), max(dy, 1e-6))))


def _lm(landmarks, idx, fw, fh, min_vis=0.3) -> Optional[tuple]:
    """Pixel coords if visibility >= min_vis, else None."""
    lm = landmarks[idx]
    vis = getattr(lm, "visibility", None)
    if vis is not None and vis < min_vis:
        return None
    return (lm.x * fw, lm.y * fh)


def _lm_raw(landmarks, idx, fw, fh) -> tuple:
    """Pixel coords, no visibility check — for drawing."""
    lm = landmarks[idx]
    return (int(lm.x * fw), int(lm.y * fh))


def _smooth(values, window=5):
    out = []
    half = window // 2
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        chunk = [x for x in values[lo:hi] if x is not None]
        out.append(sum(chunk) / len(chunk) if chunk else (values[i] or 0.0))
    return out


def _detect_phases(wrist_ys, n):
    if n < 20:
        return {"gather": max(0, int(n * .20)), "set_point": max(0, int(n * .40)),
                "release": max(0, int(n * .60)), "followthrough": min(n-1, int(n * .80)),
                "phase_detected": False}
    smoothed = _smooth(wrist_ys)
    vels = [smoothed[i] - smoothed[i-1] for i in range(1, len(smoothed))]
    release_frame = min(range(len(vels)), key=lambda i: vels[i]) + 1
    return {"gather": max(0, release_frame - 15), "set_point": max(0, release_frame - 5),
            "release": release_frame, "followthrough": min(n-1, release_frame + 10),
            "phase_detected": True}


def _build_metric(name, key, value, unit, ideal_range, in_range, note):
    return {"name": name, "key": key,
            "value": round(value, 1) if value is not None else None,
            "unit": unit, "ideal_range": ideal_range, "in_range": in_range, "note": note}


# ── drawing helpers ───────────────────────────────────────────────────────────

def _outline_text(img, text, pos, font, scale, color, thickness=2):
    """Draw text with a dark outline for readability."""
    import cv2
    x, y = pos
    cv2.putText(img, text, (x+1, y+1), font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(img, text, pos,         font, scale, color,    thickness,     cv2.LINE_AA)


def _draw_skeleton(img, landmarks, fw, fh, line_color, dot_color, line_w=2, dot_r=5):
    import cv2
    for a_idx, b_idx in _CONNECTIONS:
        if a_idx >= len(landmarks) or b_idx >= len(landmarks):
            continue
        cv2.line(img, _lm_raw(landmarks, a_idx, fw, fh),
                      _lm_raw(landmarks, b_idx, fw, fh),
                      line_color, line_w, cv2.LINE_AA)
    for idx in _KEY_JOINTS:
        if idx >= len(landmarks):
            continue
        pt = _lm_raw(landmarks, idx, fw, fh)
        cv2.circle(img, pt, dot_r,     dot_color,   -1,          cv2.LINE_AA)
        cv2.circle(img, pt, dot_r + 1, line_color,   1,          cv2.LINE_AA)


def _draw_angle_arc(img, joint_px, arm1_px, arm2_px, angle_val, is_passing, radius=36):
    """Draw an arc at joint_px spanning between the two arm directions."""
    import cv2
    color = (22, 160, 50) if is_passing else (60, 60, 220)   # green / red BGR
    ang1 = math.degrees(math.atan2(arm1_px[1] - joint_px[1], arm1_px[0] - joint_px[0]))
    ang2 = math.degrees(math.atan2(arm2_px[1] - joint_px[1], arm2_px[0] - joint_px[0]))
    start, end = sorted([ang1, ang2])
    # avoid wrapping > 180°
    if end - start > 180:
        start, end = end, start + 360
    cv2.ellipse(img, joint_px, (radius, radius), 0, start, end, color, 2, cv2.LINE_AA)
    mid_rad = math.radians((start + end) / 2)
    tx = int(joint_px[0] + (radius + 18) * math.cos(mid_rad))
    ty = int(joint_px[1] + (radius + 18) * math.sin(mid_rad))
    _outline_text(img, f"{angle_val:.0f}\u00b0", (tx, ty),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def _annotate_frame(img, landmarks, fw, fh, phase_name, metrics):
    """Full annotation: skeleton + phase banner + metric labels."""
    import cv2

    is_phase = phase_name is not None
    if is_phase:
        phase_bgr = _PHASE_INFO[phase_name]["bgr"]
        _draw_skeleton(img, landmarks, fw, fh, phase_bgr, (255, 255, 255), 2, 6)
    else:
        _draw_skeleton(img, landmarks, fw, fh, (70, 70, 70), (110, 110, 110), 1, 4)

    if not is_phase or not metrics:
        return

    # Phase banner
    phase_label = _PHASE_INFO[phase_name]["label"]
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (fw, 32), (10, 10, 15), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)
    _outline_text(img, phase_label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, phase_bgr, 2)

    # Metric annotations for this phase
    metric_dict = {m["key"]: m for m in metrics}
    for metric_key, joint_idx in _PHASE_ANNOTATIONS.get(phase_name, []):
        metric = metric_dict.get(metric_key)
        if not metric or metric["value"] is None or joint_idx >= len(landmarks):
            continue

        joint_pt = _lm_raw(landmarks, joint_idx, fw, fh)
        is_pass = metric.get("in_range", False)
        color = (22, 160, 50) if is_pass else (60, 60, 220)  # green / red BGR

        # Highlighted joint circle
        cv2.circle(img, joint_pt, 10, color,           -1, cv2.LINE_AA)
        cv2.circle(img, joint_pt, 11, (255, 255, 255),  1, cv2.LINE_AA)

        # Angle arc for elbow and knee
        if metric_key == "elbow_angle":
            arm_a = _lm_raw(landmarks, _R_SHOULDER, fw, fh)
            arm_b = _lm_raw(landmarks, _R_WRIST,    fw, fh)
            _draw_angle_arc(img, joint_pt, arm_a, arm_b, metric["value"], is_pass)
        elif metric_key == "knee_bend":
            arm_a = _lm_raw(landmarks, _R_HIP,   fw, fh)
            arm_b = _lm_raw(landmarks, _R_ANKLE, fw, fh)
            _draw_angle_arc(img, joint_pt, arm_a, arm_b, metric["value"], is_pass)
        else:
            # Text label only
            val_str = f"{metric['value']:.0f}{metric['unit']}"
            _outline_text(img, val_str, (joint_pt[0] + 14, joint_pt[1] + 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def _draw_score_bar(img, fw, fh, passing, total, metrics):
    """Bottom bar: metric status dots."""
    import cv2
    bar_h = 30
    overlay = img.copy()
    cv2.rectangle(overlay, (0, fh - bar_h), (fw, fh), (10, 10, 15), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    dot_r = 6
    spacing = 20
    start_x = 12
    y = fh - bar_h // 2
    for i, m in enumerate(metrics):
        if m.get("in_range") is None:
            color = (80, 80, 80)
        elif m["in_range"]:
            color = (22, 160, 50)
        else:
            color = (60, 60, 220)
        cx = start_x + i * spacing
        cv2.circle(img, (cx, y), dot_r, color, -1, cv2.LINE_AA)
        cv2.circle(img, (cx, y), dot_r + 1, (200, 200, 200), 1, cv2.LINE_AA)

    score_str = f"{passing}/{total}"
    _outline_text(img, score_str,
                  (start_x + len(metrics) * spacing + 8, y + 5),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2)


# ── public: analysis ──────────────────────────────────────────────────────────

def analyze_shooting_form(video_path: str) -> dict:
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError as exc:
        raise RuntimeError("mediapipe and opencv-python required") from exc

    model_path = _ensure_model()
    options = mp_vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=mp_vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = mp_vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        landmarker.close()
        raise ValueError(f"Cannot open video file: {video_path}")

    frame_data = []
    wrist_ys = []
    frame_count = 0
    sampled = 0
    # Preserve original aspect ratio, cap longest side at 640px
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_dim = 640
    scale = max_dim / max(orig_w, orig_h, 1)
    TARGET_W = max(2, int(orig_w * scale) & ~1)  # must be even for video codecs
    TARGET_H = max(2, int(orig_h * scale) & ~1)
    MAX_FRAMES = 120
    STRIDE = 3

    while sampled < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        if frame_count % STRIDE != 0:
            continue
        resized = cv2.resize(frame, (TARGET_W, TARGET_H))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)
        if result.pose_landmarks:
            lms = result.pose_landmarks[0]
            frame_data.append((lms, TARGET_W, TARGET_H))
            rw = lms[_R_WRIST]
            vis = getattr(rw, "visibility", 1.0)
            wrist_ys.append(rw.y * TARGET_H if (vis is None or vis >= 0.5) else None)
        else:
            frame_data.append(None)
            wrist_ys.append(None)
        sampled += 1

    cap.release()
    landmarker.close()

    n = len(frame_data)
    if n == 0:
        return {"metrics": [], "passing": 0, "total": 0,
                "frames_analyzed": 0, "phase_detected": False}

    filled_ys = list(wrist_ys)
    for i in range(len(filled_ys)):
        if filled_ys[i] is None:
            for d in range(1, len(filled_ys)):
                if i - d >= 0 and filled_ys[i - d] is not None:
                    filled_ys[i] = filled_ys[i - d]; break
                if i + d < len(filled_ys) and filled_ys[i + d] is not None:
                    filled_ys[i] = filled_ys[i + d]; break
    if all(v is None for v in filled_ys):
        filled_ys = [0.0] * n

    phases = _detect_phases(filled_ys, n)

    def _landmark_vis(lm_obj, *indices):
        """Sum of visibility scores for given landmark indices."""
        total = 0.0
        for idx in indices:
            lm = lm_obj[idx]
            total += getattr(lm, "visibility", 1.0) or 1.0
        return total

    def get_lms(key, *priority_indices, window=5):
        """Return best frame within ±window of the phase frame.
        'Best' = highest combined visibility for the landmarks we care about."""
        center = phases[key]
        best_entry, best_score = None, -1.0
        for offset in range(-window, window + 1):
            idx = max(0, min(n - 1, center + offset))
            e = frame_data[idx]
            if e is None:
                continue
            lms_e, fw_e, fh_e = e
            score = _landmark_vis(lms_e, *priority_indices) if priority_indices else 1.0
            if score > best_score:
                best_score, best_entry = score, e
        if best_entry is None:
            return None, None, None
        return best_entry[0], best_entry[1], best_entry[2]

    metrics = []

    # Reference ranges based on observed elite NBA shooter mechanics.
    # These are soft guides, not pass/fail cutoffs — displayed as context only.

    # 1. Elbow angle at set point (L-shape under ball)
    # Elite range: 75–110 deg. Klay ~95, Curry ~85, textbook ~90.
    lms, fw, fh = get_lms("set_point", _R_SHOULDER, _R_ELBOW, _R_WRIST)
    ev, ep, en = None, None, "Could not detect arm landmarks in this clip"
    if lms:
        rs, re, rw = _lm(lms, _R_SHOULDER, fw, fh), _lm(lms, _R_ELBOW, fw, fh), _lm(lms, _R_WRIST, fw, fh)
        if rs and re and rw:
            ev = _angle(rs, re, rw)
            ep = 75 <= ev <= 110
            en = (f"Elbow well-positioned at {ev:.0f} deg" if ep
                  else f"Elbow {'very tucked' if ev < 75 else 'wide'} at {ev:.0f} deg. Typical elite range is 75 to 110.")
    metrics.append(_build_metric("Elbow Angle", "elbow_angle", ev, "°", "75–110°", ep, en))

    # 2. Wrist follow-through (normalized, resolution-independent)
    # Elite shooters snap wrist clearly downward after release — >=3% frame height
    lms_r, fw_r, fh_r = get_lms("release",       _R_WRIST)
    lms_ft, fw_ft, fh_ft = get_lms("followthrough", _R_WRIST)
    wv, wp, wn = None, None, "Could not detect wrist in this clip"
    if lms_r and lms_ft:
        rw_rel_lm = lms_r[_R_WRIST]
        rw_ft_lm  = lms_ft[_R_WRIST]
        vis_r  = getattr(rw_rel_lm, "visibility", 1.0) or 1.0
        vis_ft = getattr(rw_ft_lm,  "visibility", 1.0) or 1.0
        if vis_r >= 0.3 and vis_ft >= 0.3:
            norm_delta = rw_ft_lm.y - rw_rel_lm.y
            wv = round(norm_delta * 100, 1)
            wp = norm_delta >= 0.03
            wn = (f"Good wrist snap on follow-through ({wv:.1f}%)" if wp
                  else f"Limited wrist snap ({wv:.1f}%). Try finishing with fingers pointing down at the basket.")
    metrics.append(_build_metric("Wrist Follow-Through", "wrist_followthrough", wv, "%", "≥3% drop", wp, wn))

    # 3. Shoulder symmetry at release
    # Elite range: <6% tilt — some natural dip on shooting side is fine
    lms, fw, fh = get_lms("release", _L_SHOULDER, _R_SHOULDER)
    sv, sp, sn = None, None, "Could not detect shoulders in this clip"
    if lms:
        ls, rs = _lm(lms, _L_SHOULDER, fw, fh), _lm(lms, _R_SHOULDER, fw, fh)
        if ls and rs:
            raw = abs(ls[1] - rs[1]) / fh
            sv = round(raw * 100, 1)
            sp = raw < 0.06
            sn = (f"Shoulders balanced at release ({sv}% tilt)" if sp
                  else f"Pronounced shoulder tilt at release ({sv}%). Check for hip and shoulder alignment.")
    metrics.append(_build_metric("Shoulder Symmetry", "shoulder_symmetry", sv, "%", "<6% tilt", sp, sn))

    # 4. Knee bend at gather
    # Elite range: 120-165 deg. Klay/Curry sit around 145-155. 90 deg is a chair squat.
    lms, fw, fh = get_lms("gather", _R_HIP, _R_KNEE, _R_ANKLE)
    kv, kp, kn = None, None, "Could not detect lower body in this clip"
    if lms:
        rh, rk, ra = _lm(lms, _R_HIP, fw, fh), _lm(lms, _R_KNEE, fw, fh), _lm(lms, _R_ANKLE, fw, fh)
        if rh and rk and ra:
            kv = _angle(rh, rk, ra)
            kp = 120 <= kv <= 165
            kn = (f"Natural knee load at {kv:.0f} deg" if kp
                  else f"{'Very deep gather' if kv < 120 else 'Minimal knee bend'} at {kv:.0f} deg. Elite shooters typically load between 120 and 165.")
    metrics.append(_build_metric("Knee Bend", "knee_bend", kv, "°", "120–165°", kp, kn))

    # 5. Body tilt at release
    # Elite range: <=25 deg. A slight lean is fine (Klay leans back slightly, Dirk extreme).
    lms, fw, fh = get_lms("release", _L_SHOULDER, _R_SHOULDER, _R_HIP)
    tv, tp, tn = None, None, "Could not detect torso in this clip"
    if lms:
        ls, rs = _lm(lms, _L_SHOULDER, fw, fh), _lm(lms, _R_SHOULDER, fw, fh)
        rh = _lm(lms, _R_HIP, fw, fh)
        if ls and rs and rh:
            smid = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
            tv = _vertical_angle(smid, rh)
            tp = tv <= 25
            tn = (f"Balanced release position ({tv:.0f} deg tilt)" if tp
                  else f"Significant lean at release ({tv:.0f} deg). This can affect shot consistency over a long game.")
    metrics.append(_build_metric("Body Tilt", "body_tilt", tv, "°", "≤25°", tp, tn))

    scored = [m for m in metrics if m["in_range"] is not None]
    return {
        "metrics": metrics,
        "passing": sum(1 for m in scored if m["in_range"]),
        "total": len(scored),
        "frames_analyzed": n,
        "phase_detected": phases["phase_detected"],
        # internal — used by generate_annotated_video
        "_frame_data": frame_data,
        "_phases": phases,
        "_stride": STRIDE,
        "_size": (TARGET_W, TARGET_H),
    }


# ── public: annotation ────────────────────────────────────────────────────────

def generate_annotated_video(video_path: str, analysis: dict, output_path: str) -> bool:
    """
    Render an annotated video with pose skeleton, phase labels, and angle arcs.
    Returns True on success.
    """
    try:
        import cv2
    except ImportError:
        return False

    frame_data = analysis.get("_frame_data", [])
    phases     = analysis.get("_phases", {})
    metrics    = analysis.get("metrics", [])
    stride     = analysis.get("_stride", 3)
    TARGET_W, TARGET_H = analysis.get("_size", (640, 360))

    if not frame_data:
        return False

    # Build phase-frame map: sampled_index → phase_name
    phase_frame_map: dict[int, str] = {}
    for name in ("gather", "set_point", "release", "followthrough"):
        idx = phases.get(name)
        if idx is not None:
            phase_frame_map[idx] = name

    # Get original video fps
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    out_fps = max(orig_fps / stride, 8.0)

    # Create VideoWriter — try H.264 then MPEG-4
    writer = None
    for fourcc_str in ("avc1", "mp4v"):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        w = cv2.VideoWriter(output_path, fourcc, out_fps, (TARGET_W, TARGET_H))
        if w.isOpened():
            writer = w
            break
    if writer is None:
        return False

    passing = analysis.get("passing", 0)
    total   = analysis.get("total", 0)

    # Re-read video and annotate using stored landmark data
    cap = cv2.VideoCapture(video_path)
    frame_count  = 0
    sampled_idx  = 0

    while sampled_idx < len(frame_data):
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        if frame_count % stride != 0:
            continue

        img = cv2.resize(frame, (TARGET_W, TARGET_H))
        entry      = frame_data[sampled_idx]
        phase_name = phase_frame_map.get(sampled_idx)

        if entry is not None:
            lms, fw, fh = entry
            _annotate_frame(img, lms, fw, fh, phase_name, metrics)

        _draw_score_bar(img, TARGET_W, TARGET_H, passing, total, metrics)
        writer.write(img)
        sampled_idx += 1

    cap.release()
    writer.release()
    return True
