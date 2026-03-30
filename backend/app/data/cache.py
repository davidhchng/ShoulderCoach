"""
SQLite read/write helpers used by engines and the seed pipeline.
Engines call these to query pre-aggregated stats tables.
"""
from app.database import get_connection


def get_league_avg_ppp(db_path: str) -> float:
    """Return league average points per possession across all seasons."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT AVG(points_per_possession) as avg_ppp FROM team_season_stats WHERE points_per_possession IS NOT NULL"
        ).fetchone()
    if row and row["avg_ppp"]:
        return round(row["avg_ppp"], 3)
    return 1.05  # fallback league average


def get_league_avg_3pt_pct(db_path: str) -> float:
    """Return league average 3PT% across all seasons."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT AVG(three_pt_pct) as avg_3pt FROM team_season_stats WHERE three_pt_pct IS NOT NULL"
        ).fetchone()
    if row and row["avg_3pt"]:
        return round(row["avg_3pt"], 3)
    return 0.360  # fallback


def get_team_3pt_pct(db_path: str, team_id: int, season: str) -> float | None:
    """Get a specific team's 3PT% for a season."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT three_pt_pct FROM team_season_stats WHERE team_id=? AND season=?",
            (team_id, season),
        ).fetchone()
    return row["three_pt_pct"] if row else None


def get_player_ft_pct(db_path: str, player_id: int, season: str) -> float | None:
    """Get a specific player's FT% for a season."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT ft_pct FROM player_season_stats WHERE player_id=? AND season=?",
            (player_id, season),
        ).fetchone()
    return row["ft_pct"] if row else None
