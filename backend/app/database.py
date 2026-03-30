import sqlite3
from contextlib import contextmanager
from pathlib import Path
from app.config import DATABASE_PATH


def get_db_path() -> str:
    return DATABASE_PATH


@contextmanager
def get_connection(db_path: str | None = None):
    """Context manager yielding a SQLite connection with row_factory set."""
    path = db_path or DATABASE_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_all_tables(db_path: str | None = None) -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    with get_connection(db_path) as conn:
        conn.executescript("""
            -- ===========================================
            -- RAW DATA TABLES
            -- ===========================================

            CREATE TABLE IF NOT EXISTS clutch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                season TEXT NOT NULL,
                game_date TEXT,
                period INTEGER,
                seconds_remaining REAL,
                score_margin INTEGER,
                home_team_id INTEGER,
                away_team_id INTEGER,
                event_type TEXT,
                event_detail TEXT,
                event_description TEXT,
                player_id INTEGER,
                team_id INTEGER,
                home_score INTEGER,
                away_score INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                season TEXT NOT NULL,
                game_date TEXT,
                home_team_id INTEGER,
                away_team_id INTEGER,
                home_score_final INTEGER,
                away_score_final INTEGER,
                winner_team_id INTEGER,
                went_to_ot INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS team_season_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                season TEXT NOT NULL,
                team_name TEXT,
                three_pt_pct REAL,
                ft_pct REAL,
                pace REAL,
                off_rating REAL,
                def_rating REAL,
                points_per_possession REAL,
                UNIQUE(team_id, season)
            );

            CREATE TABLE IF NOT EXISTS player_season_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                season TEXT NOT NULL,
                player_name TEXT,
                ft_pct REAL,
                ft_attempts INTEGER,
                UNIQUE(player_id, season)
            );

            -- ===========================================
            -- PRE-AGGREGATED STATS
            -- ===========================================

            CREATE TABLE IF NOT EXISTS stats_foul_up_3 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_bucket TEXT NOT NULL,
                strategy TEXT NOT NULL,
                opponent_3pt_tier TEXT NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                overtimes INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                win_pct REAL,
                UNIQUE(time_bucket, strategy, opponent_3pt_tier)
            );

            CREATE TABLE IF NOT EXISTS stats_timeout (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_size TEXT NOT NULL,
                quarter_group TEXT NOT NULL,
                timeout_called INTEGER NOT NULL,
                run_continued INTEGER DEFAULT 0,
                avg_point_swing_next_5 REAL,
                total INTEGER DEFAULT 0,
                UNIQUE(run_size, quarter_group, timeout_called)
            );

            CREATE TABLE IF NOT EXISTS stats_hack_a_player (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ft_pct_tier TEXT NOT NULL,
                score_situation TEXT NOT NULL,
                time_bucket TEXT NOT NULL,
                expected_ppp_hack REAL,
                expected_ppp_normal REAL,
                total_hack_possessions INTEGER DEFAULT 0,
                total_normal_possessions INTEGER DEFAULT 0,
                UNIQUE(ft_pct_tier, score_situation, time_bucket)
            );

            CREATE TABLE IF NOT EXISTS stats_two_for_one (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seconds_bucket TEXT NOT NULL,
                score_situation TEXT NOT NULL,
                quarter_group TEXT NOT NULL,
                pushed_2for1 INTEGER NOT NULL,
                avg_points_scored REAL,
                total INTEGER DEFAULT 0,
                UNIQUE(seconds_bucket, score_situation, quarter_group, pushed_2for1)
            );

            CREATE TABLE IF NOT EXISTS stats_zone_vs_man (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opponent_3pt_tier TEXT NOT NULL,
                driving_heavy INTEGER NOT NULL,
                defense_type TEXT NOT NULL,
                opponent_ppp REAL,
                paint_points_pct REAL,
                three_pt_attempt_rate REAL,
                total_possessions INTEGER DEFAULT 0,
                UNIQUE(opponent_3pt_tier, driving_heavy, defense_type)
            );

            CREATE TABLE IF NOT EXISTS stats_pull_starters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                margin_bucket TEXT NOT NULL,
                time_bucket TEXT NOT NULL,
                quarter TEXT NOT NULL,
                win_pct REAL,
                largest_comeback INTEGER,
                total_games INTEGER DEFAULT 0,
                UNIQUE(margin_bucket, time_bucket, quarter)
            );

            CREATE TABLE IF NOT EXISTS stats_press (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deficit_bucket TEXT NOT NULL,
                time_bucket TEXT NOT NULL,
                quarter_group TEXT NOT NULL,
                pressed INTEGER NOT NULL,
                turnover_rate REAL,
                ppp_allowed REAL,
                fast_break_pts_rate REAL,
                total_possessions INTEGER DEFAULT 0,
                UNIQUE(deficit_bucket, time_bucket, quarter_group, pressed)
            );

            CREATE TABLE IF NOT EXISTS stats_three_vs_two (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deficit TEXT NOT NULL,
                seconds_bucket TEXT NOT NULL,
                has_timeout INTEGER NOT NULL,
                attempt_type TEXT NOT NULL,
                make_pct REAL,
                win_pct REAL,
                total_possessions INTEGER DEFAULT 0,
                UNIQUE(deficit, seconds_bucket, has_timeout, attempt_type)
            );

            -- ===========================================
            -- FETCH TRACKING
            -- ===========================================

            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                season TEXT NOT NULL,
                params_hash TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                row_count INTEGER DEFAULT 0,
                UNIQUE(endpoint, season, params_hash)
            );
        """)


def count_total_rows(db_path: str | None = None) -> int:
    """Count total rows across all stats tables for the health endpoint."""
    stats_tables = [
        "stats_foul_up_3", "stats_timeout", "stats_hack_a_player",
        "stats_two_for_one", "stats_zone_vs_man", "stats_pull_starters",
        "stats_press", "stats_three_vs_two",
    ]
    total = 0
    with get_connection(db_path) as conn:
        for table in stats_tables:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            total += row["cnt"]
    return total
