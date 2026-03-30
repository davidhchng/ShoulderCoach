"""
Shared test fixtures. Each test gets an in-memory SQLite DB
pre-populated with known data.
"""
import sqlite3
import pytest
from app.database import create_all_tables


@pytest.fixture
def db_path(tmp_path):
    """Return path to a fresh temp SQLite DB with all tables created."""
    path = str(tmp_path / "test.db")
    create_all_tables(path)
    return path


def insert_foul_up_3(db_path: str, rows: list[tuple]) -> None:
    """Insert rows into stats_foul_up_3: (time_bucket, strategy, opp_tier, wins, losses, total, win_pct)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_foul_up_3
                (time_bucket, strategy, opponent_3pt_tier, wins, losses, total, win_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_timeout(db_path: str, rows: list[tuple]) -> None:
    """Insert rows into stats_timeout: (run_size, quarter_group, timeout_called, run_continued, avg_swing, total)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_timeout
                (run_size, quarter_group, timeout_called, run_continued, avg_point_swing_next_5, total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_hack(db_path: str, rows: list[tuple]) -> None:
    """Insert rows into stats_hack_a_player: (ft_tier, score_sit, time_bucket, ppp_hack, ppp_normal, n_hack, n_normal)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_hack_a_player
                (ft_pct_tier, score_situation, time_bucket,
                 expected_ppp_hack, expected_ppp_normal,
                 total_hack_possessions, total_normal_possessions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_two_for_one(db_path: str, rows: list[tuple]) -> None:
    """Insert rows: (seconds_bucket, score_sit, quarter_group, pushed, avg_pts, total)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_two_for_one
                (seconds_bucket, score_situation, quarter_group, pushed_2for1, avg_points_scored, total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_zone(db_path: str, rows: list[tuple]) -> None:
    """Insert rows: (opp_3pt_tier, driving_heavy, defense_type, opp_ppp, paint_pct, three_rate, total)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_zone_vs_man
                (opponent_3pt_tier, driving_heavy, defense_type,
                 opponent_ppp, paint_points_pct, three_pt_attempt_rate, total_possessions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_pull_starters(db_path: str, rows: list[tuple]) -> None:
    """Insert rows: (margin_bucket, time_bucket, quarter, win_pct, largest_comeback, total)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_pull_starters
                (margin_bucket, time_bucket, quarter, win_pct, largest_comeback, total_games)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_press(db_path: str, rows: list[tuple]) -> None:
    """Insert rows: (deficit_bucket, time_bucket, quarter_group, pressed, to_rate, ppp_allowed, fb_rate, total)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_press
                (deficit_bucket, time_bucket, quarter_group, pressed,
                 turnover_rate, ppp_allowed, fast_break_pts_rate, total_possessions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def insert_three_vs_two(db_path: str, rows: list[tuple]) -> None:
    """Insert rows: (deficit, seconds_bucket, has_timeout, attempt_type, make_pct, win_pct, total)"""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stats_three_vs_two
                (deficit, seconds_bucket, has_timeout, attempt_type, make_pct, win_pct, total_possessions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
