import hashlib
import json
import time
import logging
from typing import Any

from app.config import (
    NBA_API_SLEEP_SECONDS,
    NBA_API_MAX_RETRIES,
    NBA_API_BACKOFF_BASE,
)
from app.database import get_connection

logger = logging.getLogger(__name__)

# Apply headers to all nba_api requests
try:
    from nba_api.stats import endpoints as _endpoints
    import nba_api.stats.library.http as _http

    _http.NBAStatsHTTP.headers = {
        "User-Agent": "ShoulderCoach/1.0 (basketball research)",
        "Referer": "https://stats.nba.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "Connection": "keep-alive",
    }
    _http.NBAStatsHTTP.timeout = 60
except Exception:
    pass  # nba_api may not be installed in test env


def _make_params_hash(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True)
    return hashlib.md5(canonical.encode()).hexdigest()


def is_already_fetched(db_path: str, endpoint: str, season: str, params_hash: str) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM fetch_log WHERE endpoint=? AND season=? AND params_hash=?",
            (endpoint, season, params_hash),
        ).fetchone()
    return row is not None


def mark_fetched(db_path: str, endpoint: str, season: str, params_hash: str, row_count: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO fetch_log (endpoint, season, params_hash, row_count)
            VALUES (?, ?, ?, ?)
            """,
            (endpoint, season, params_hash, row_count),
        )


def rate_limited_fetch(endpoint_cls, **kwargs) -> Any:
    """
    Fetch from nba_api with rate limiting and exponential backoff.
    Sleeps 0.6s before every call. Retries up to 3x on error.
    """
    time.sleep(NBA_API_SLEEP_SECONDS)

    last_exc = None
    for attempt in range(NBA_API_MAX_RETRIES):
        try:
            result = endpoint_cls(**kwargs)
            return result
        except Exception as exc:
            last_exc = exc
            exc_str = str(exc).lower()
            is_retryable = (
                isinstance(exc, (ConnectionError, TimeoutError, OSError))
                or "429" in exc_str
                or "timeout" in exc_str
                or "connection" in exc_str
                or "read" in exc_str
            )
            if is_retryable:
                wait = NBA_API_BACKOFF_BASE ** (attempt + 1)
                logger.warning(
                    f"nba_api error (attempt {attempt+1}/{NBA_API_MAX_RETRIES}): {exc}. "
                    f"Backing off {wait:.0f}s..."
                )
                time.sleep(wait)
            else:
                # Non-retryable error
                logger.error(f"nba_api non-retryable error: {exc}")
                raise

    logger.error(f"nba_api failed after {NBA_API_MAX_RETRIES} retries. Last error: {last_exc}")
    raise last_exc


def fetch_team_season_stats(db_path: str, season: str) -> int:
    """Fetch team season stats and insert into team_season_stats."""
    from nba_api.stats.endpoints import LeagueDashTeamStats

    params = {"season": season, "season_type_all_star": "Regular Season"}
    params_hash = _make_params_hash(params)
    endpoint_name = "LeagueDashTeamStats"

    if is_already_fetched(db_path, endpoint_name, season, params_hash):
        logger.info(f"Skipping {endpoint_name} for {season} (already fetched)")
        return 0

    logger.info(f"Fetching {endpoint_name} for {season}...")
    result = rate_limited_fetch(LeagueDashTeamStats, **params)
    df = result.get_data_frames()[0]

    rows_inserted = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            # Calculate points per possession from off_rating (off_rating ~= PPP * 100)
            off_rating = row.get("OFF_RATING") or row.get("E_OFF_RATING")
            ppp = (off_rating / 100.0) if off_rating else None
            conn.execute(
                """
                INSERT OR IGNORE INTO team_season_stats
                    (team_id, season, team_name, three_pt_pct, ft_pct, pace,
                     off_rating, def_rating, points_per_possession)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("TEAM_ID"),
                    season,
                    row.get("TEAM_NAME"),
                    row.get("FG3_PCT"),
                    row.get("FT_PCT"),
                    row.get("PACE") or row.get("E_PACE"),
                    off_rating,
                    row.get("DEF_RATING") or row.get("E_DEF_RATING"),
                    ppp,
                ),
            )
            rows_inserted += 1

    mark_fetched(db_path, endpoint_name, season, params_hash, rows_inserted)
    logger.info(f"Inserted {rows_inserted} rows into team_season_stats for {season}")
    return rows_inserted


def fetch_player_season_stats(db_path: str, season: str) -> int:
    """Fetch player season stats and insert into player_season_stats."""
    from nba_api.stats.endpoints import LeagueDashPlayerStats

    params = {"season": season, "season_type_all_star": "Regular Season"}
    params_hash = _make_params_hash(params)
    endpoint_name = "LeagueDashPlayerStats"

    if is_already_fetched(db_path, endpoint_name, season, params_hash):
        logger.info(f"Skipping {endpoint_name} for {season} (already fetched)")
        return 0

    logger.info(f"Fetching {endpoint_name} for {season}...")
    result = rate_limited_fetch(LeagueDashPlayerStats, **params)
    df = result.get_data_frames()[0]

    rows_inserted = 0
    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            conn.execute(
                """
                INSERT OR IGNORE INTO player_season_stats
                    (player_id, season, player_name, ft_pct, ft_attempts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row.get("PLAYER_ID"),
                    season,
                    row.get("PLAYER_NAME"),
                    row.get("FT_PCT"),
                    row.get("FTA"),
                ),
            )
            rows_inserted += 1

    mark_fetched(db_path, endpoint_name, season, params_hash, rows_inserted)
    logger.info(f"Inserted {rows_inserted} rows into player_season_stats for {season}")
    return rows_inserted


def fetch_game_ids(db_path: str, season: str) -> list[tuple[str, str, int, int]]:
    """
    Fetch all game IDs for a season. Returns list of
    (game_id, game_date, home_team_id, away_team_id).
    Also inserts into games table.
    """
    from nba_api.stats.endpoints import LeagueGameLog

    params = {"season": season, "season_type_all_star": "Regular Season", "direction": "ASC"}
    params_hash = _make_params_hash(params)
    endpoint_name = "LeagueGameLog"

    if is_already_fetched(db_path, endpoint_name, season, params_hash):
        logger.info(f"Skipping {endpoint_name} for {season} (already fetched)")
        # Still return existing game IDs from DB
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT game_id, game_date, home_team_id, away_team_id FROM games WHERE season=?",
                (season,),
            ).fetchall()
        return [(r["game_id"], r["game_date"], r["home_team_id"], r["away_team_id"]) for r in rows]

    logger.info(f"Fetching {endpoint_name} for {season}...")
    result = rate_limited_fetch(LeagueGameLog, **params)
    df = result.get_data_frames()[0]

    game_ids = []
    processed_games = set()

    with get_connection(db_path) as conn:
        for _, row in df.iterrows():
            game_id = str(row.get("GAME_ID", ""))
            if game_id in processed_games:
                continue
            processed_games.add(game_id)

            # LeagueGameLog returns one row per team per game
            # We need to pair home and away — use MATCHUP field "TEAM vs. OPP" = home, "TEAM @ OPP" = away
            matchup = str(row.get("MATCHUP", ""))
            game_date = str(row.get("GAME_DATE", ""))

            # Insert skeleton; scores filled in after processing all rows for this game
            conn.execute(
                """
                INSERT OR IGNORE INTO games
                    (game_id, season, game_date, home_team_id, away_team_id,
                     home_score_final, away_score_final, winner_team_id, went_to_ot)
                VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, 0)
                """,
                (game_id, season, game_date),
            )

        # Second pass: fill home/away from MATCHUP
        for _, row in df.iterrows():
            game_id = str(row.get("GAME_ID", ""))
            matchup = str(row.get("MATCHUP", ""))
            team_id = row.get("TEAM_ID")
            pts = row.get("PTS")
            wl = row.get("WL")

            if "vs." in matchup:
                # This team is home
                conn.execute(
                    "UPDATE games SET home_team_id=?, home_score_final=? WHERE game_id=?",
                    (team_id, pts, game_id),
                )
                if wl == "W":
                    conn.execute(
                        "UPDATE games SET winner_team_id=? WHERE game_id=?",
                        (team_id, game_id),
                    )
            elif "@" in matchup:
                # This team is away
                conn.execute(
                    "UPDATE games SET away_team_id=?, away_score_final=? WHERE game_id=?",
                    (team_id, pts, game_id),
                )
                if wl == "W":
                    conn.execute(
                        "UPDATE games SET winner_team_id=? WHERE game_id=?",
                        (team_id, game_id),
                    )

    mark_fetched(db_path, endpoint_name, season, params_hash, len(processed_games))

    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT game_id, game_date, home_team_id, away_team_id FROM games WHERE season=?",
            (season,),
        ).fetchall()

    logger.info(f"Found {len(rows)} games for {season}")
    return [(r["game_id"], r["game_date"], r["home_team_id"], r["away_team_id"]) for r in rows]


def fetch_play_by_play(db_path: str, game_id: str, season: str, progress: str = "") -> int:
    """
    Fetch play-by-play for a single game and insert relevant events
    into clutch_events. Returns number of events inserted.
    Uses PlayByPlayV3 (V2 is deprecated and returns empty JSON).
    """
    import re
    from nba_api.stats.endpoints import PlayByPlayV3

    params = {"game_id": game_id}
    params_hash = _make_params_hash(params)
    endpoint_name = "PlayByPlayV3"

    # Also skip if the old V2 endpoint was already fetched for this game
    old_hash = _make_params_hash(params)
    if (
        is_already_fetched(db_path, endpoint_name, season, params_hash)
        or is_already_fetched(db_path, "PlayByPlayV2", season, old_hash)
    ):
        return 0  # Already fetched this game

    if progress:
        logger.info(progress)

    try:
        result = rate_limited_fetch(PlayByPlayV3, **params)
    except Exception as exc:
        logger.error(f"Failed to fetch PBP for game {game_id}: {exc}")
        return 0

    df = result.get_data_frames()[0]

    # Get game info for context
    with get_connection(db_path) as conn:
        game_row = conn.execute(
            "SELECT home_team_id, away_team_id FROM games WHERE game_id=?",
            (game_id,),
        ).fetchone()

    home_team_id = game_row["home_team_id"] if game_row else None
    away_team_id = game_row["away_team_id"] if game_row else None

    # Track running score between events (V3 only shows score on scoring plays)
    last_home_score: int | None = None
    last_away_score: int | None = None

    rows_inserted = 0
    events_to_insert = []

    for _, row in df.iterrows():
        period = int(row.get("period", 0))
        clock_str = str(row.get("clock", "PT00M00.00S"))
        action_type = str(row.get("actionType", ""))
        sub_type = str(row.get("subType", ""))
        description = str(row.get("description", ""))
        player_id = row.get("personId") or None
        team_id = row.get("teamId") or None
        shot_value = row.get("shotValue", 0) or 0
        score_home_raw = str(row.get("scoreHome", "") or "")
        score_away_raw = str(row.get("scoreAway", "") or "")

        # Parse ISO 8601 clock: PT12M00.00S
        seconds_remaining = None
        m = re.match(r"PT(\d+)M(\d+(?:\.\d+)?)S", clock_str)
        if m:
            seconds_remaining = int(m.group(1)) * 60 + int(float(m.group(2)))

        # Update running score
        if score_home_raw.strip():
            try:
                last_home_score = int(score_home_raw.strip())
            except ValueError:
                pass
        if score_away_raw.strip():
            try:
                last_away_score = int(score_away_raw.strip())
            except ValueError:
                pass

        home_score = last_home_score
        away_score = last_away_score
        score_margin = (home_score - away_score) if (home_score is not None and away_score is not None) else None

        # Filter: Q4/OT or last 2 mins of any quarter, plus end-of-quarter for 2-for-1
        is_clutch = period >= 4 or (seconds_remaining is not None and seconds_remaining <= 120)
        is_end_of_quarter = seconds_remaining is not None and seconds_remaining <= 45

        if not (is_clutch or is_end_of_quarter):
            continue

        event_type_str, event_detail_str = _classify_event_v3(
            action_type, sub_type, description, int(shot_value)
        )

        if event_type_str is None:
            continue

        events_to_insert.append((
            game_id, season, None,
            period, seconds_remaining, score_margin,
            home_team_id, away_team_id,
            event_type_str, event_detail_str, description[:500],
            player_id, team_id,
            home_score, away_score,
        ))

    if events_to_insert:
        with get_connection(db_path) as conn:
            conn.executemany(
                """
                INSERT INTO clutch_events
                    (game_id, season, game_date, period, seconds_remaining,
                     score_margin, home_team_id, away_team_id,
                     event_type, event_detail, event_description,
                     player_id, team_id, home_score, away_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                events_to_insert,
            )
        rows_inserted = len(events_to_insert)

    mark_fetched(db_path, endpoint_name, season, params_hash, rows_inserted)
    return rows_inserted


def _classify_event_v3(action_type: str, sub_type: str, description: str, shot_value: int) -> tuple[str | None, str | None]:
    """Map PlayByPlayV3 actionType/subType to our event_type / event_detail strings."""
    desc_lower = description.lower()
    sub_lower = sub_type.lower()

    if action_type == "Made Shot":
        if shot_value == 3:
            return "shot", "3pt_made"
        return "shot", "2pt_made"

    elif action_type == "Missed Shot":
        if shot_value == 3:
            return "shot", "3pt_missed"
        return "shot", "2pt_missed"

    elif action_type == "Free Throw":
        if "miss" in desc_lower:
            return "free_throw", "ft_missed"
        return "free_throw", "ft_made"

    elif action_type == "Turnover":
        if "bad pass" in sub_lower or "bad pass" in desc_lower:
            return "turnover", "bad_pass"
        if "lost ball" in sub_lower or "lost ball" in desc_lower:
            return "turnover", "lost_ball"
        if "shot clock" in sub_lower or "shot clock" in desc_lower:
            return "turnover", "shot_clock"
        if "backcourt" in sub_lower or "backcourt" in desc_lower:
            return "turnover", "backcourt"
        if "8 second" in sub_lower or "8 second" in desc_lower:
            return "turnover", "8_second"
        return "turnover", "other"

    elif action_type == "Foul":
        if "shooting" in sub_lower:
            return "foul", "shooting_foul"
        if "personal" in sub_lower:
            if "away from play" in desc_lower or "away.from" in desc_lower:
                return "foul", "intentional_foul"
            return "foul", "personal_foul"
        if "flagrant" in sub_lower:
            return "foul", "flagrant_foul"
        if "loose ball" in sub_lower:
            return "foul", "loose_ball_foul"
        if "offensive" in sub_lower:
            return "foul", "offensive_foul"
        return "foul", "other_foul"

    elif action_type == "Timeout":
        return "timeout", "timeout_called"

    elif action_type == "Rebound":
        return "rebound", "rebound"

    return None, None


def _classify_event(event_type, event_action, description: str, player2_id) -> tuple[str | None, str | None]:
    """Legacy V2 classifier — kept for test compatibility."""
    desc_lower = description.lower()

    if event_type == 1:
        if "3pt" in desc_lower or "three" in desc_lower or "3-pt" in desc_lower:
            return "shot", "3pt_made"
        return "shot", "2pt_made"
    elif event_type == 2:
        if "3pt" in desc_lower or "three" in desc_lower or "3-pt" in desc_lower:
            return "shot", "3pt_missed"
        return "shot", "2pt_missed"
    elif event_type == 3:
        if "makes" in desc_lower or "make" in desc_lower:
            return "free_throw", "ft_made"
        return "free_throw", "ft_missed"
    elif event_type == 5:
        if "bad pass" in desc_lower:
            return "turnover", "bad_pass"
        if "lost ball" in desc_lower:
            return "turnover", "lost_ball"
        if "shot clock" in desc_lower:
            return "turnover", "shot_clock"
        if "backcourt" in desc_lower:
            return "turnover", "backcourt"
        if "8 second" in desc_lower:
            return "turnover", "8_second"
        return "turnover", "other"
    elif event_type == 6:
        if "personal" in desc_lower:
            if player2_id and ("away from play" in desc_lower or "away.from" in desc_lower):
                return "foul", "intentional_foul"
            return "foul", "personal_foul"
        if "flagrant" in desc_lower:
            return "foul", "flagrant_foul"
        if "loose ball" in desc_lower:
            return "foul", "loose_ball_foul"
        if "offensive" in desc_lower:
            return "foul", "offensive_foul"
        if "shooting" in desc_lower:
            return "foul", "shooting_foul"
        return "foul", "other_foul"
    elif event_type == 9:
        return "timeout", "timeout_called"
    elif event_type == 4:
        return "rebound", "rebound"
    return None, None
