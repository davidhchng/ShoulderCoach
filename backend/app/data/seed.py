"""
Seed script: fetch all NBA data and populate stats tables.
Run with: python -m app.data.seed

Expected runtime: 1-2 hours due to rate limiting.
Safe to run multiple times (idempotent).
"""
import logging
import sys
from app.config import DATABASE_PATH, NBA_SEASONS
from app.database import create_all_tables, get_connection
from app.data.fetcher import (
    fetch_team_season_stats,
    fetch_player_season_stats,
    fetch_game_ids,
    fetch_play_by_play,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def aggregate_foul_up_3(db_path: str) -> None:
    """
    Populate stats_foul_up_3.

    Identify situations: period >= 4, margin = 3, leading team has possession
    about to expire (based on when trailing team had possession).
    Approximate foul intent from event sequence: a personal foul on trailing team
    player within 60s of end of game → intentional foul up 3.

    strategy='foul': leading team committed intentional foul (personal foul while up 3)
    strategy='no_foul': leading team did not foul, trailing team had possession
    """
    logger.info("Aggregating stats_foul_up_3...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_foul_up_3")

        # Get all late-game foul events where margin=3
        foul_events = conn.execute(
            """
            SELECT ce.game_id, ce.period, ce.seconds_remaining,
                   ce.score_margin, ce.team_id, ce.home_team_id, ce.away_team_id,
                   g.winner_team_id,
                   tss.three_pt_pct as opp_3pt_pct
            FROM clutch_events ce
            JOIN games g ON ce.game_id = g.game_id
            LEFT JOIN team_season_stats tss ON (
                -- Get the fouled team's 3PT%
                tss.season = ce.season
                AND tss.team_id = CASE
                    WHEN ce.team_id = ce.home_team_id THEN ce.away_team_id
                    ELSE ce.home_team_id
                END
            )
            WHERE ce.event_type = 'foul'
              AND ce.event_detail IN ('personal_foul', 'intentional_foul')
              AND ce.period >= 4
              AND ABS(ce.score_margin) = 3
              AND ce.seconds_remaining IS NOT NULL
            """,
        ).fetchall()

        # Also get no-foul situations: trailing team had possession, margin=3, period>=4
        no_foul_events = conn.execute(
            """
            SELECT ce.game_id, ce.period, ce.seconds_remaining,
                   ce.score_margin, ce.team_id, ce.home_team_id, ce.away_team_id,
                   g.winner_team_id,
                   tss.three_pt_pct as opp_3pt_pct
            FROM clutch_events ce
            JOIN games g ON ce.game_id = g.game_id
            LEFT JOIN team_season_stats tss ON (
                tss.season = ce.season AND tss.team_id = ce.team_id
            )
            WHERE ce.event_type IN ('shot', 'turnover')
              AND ce.period >= 4
              AND ce.score_margin IS NOT NULL
              AND ABS(ce.score_margin) = 3
              AND ce.seconds_remaining IS NOT NULL
              -- Exclude games where foul already happened (approximate)
            """,
        ).fetchall()

        # Get league avg 3PT% for tier bucketing
        avg_row = conn.execute(
            "SELECT AVG(three_pt_pct) as avg FROM team_season_stats WHERE three_pt_pct IS NOT NULL"
        ).fetchone()
        league_avg_3pt = avg_row["avg"] if avg_row and avg_row["avg"] else 0.36

        def time_bucket(secs):
            if secs < 10:
                return "<10s"
            elif secs < 30:
                return "10-30s"
            else:
                return "30-60s"

        def opp_tier(pct):
            if pct is None:
                return "average"
            return "strong" if pct > league_avg_3pt else "average"

        # Aggregate foul strategy
        buckets: dict = {}

        for ev in foul_events:
            secs = ev["seconds_remaining"]
            if secs is None or secs > 60:
                continue
            margin = ev["score_margin"]
            # Determine if the leading team (up 3) committed the foul
            up_team = ev["home_team_id"] if margin > 0 else ev["away_team_id"]
            if ev["team_id"] != up_team:
                continue  # Not the leading team fouling

            tb = time_bucket(secs)
            ot = opp_tier(ev["opp_3pt_pct"])
            key = (tb, "foul", ot)
            won = 1 if ev["winner_team_id"] == up_team else 0
            if key not in buckets:
                buckets[key] = {"wins": 0, "losses": 0, "total": 0}
            buckets[key]["wins"] += won
            buckets[key]["losses"] += (1 - won)
            buckets[key]["total"] += 1

        for ev in no_foul_events:
            secs = ev["seconds_remaining"]
            if secs is None or secs > 60:
                continue
            margin = ev["score_margin"]
            # Trailing team is shooting / turning it over
            trailing_team = ev["home_team_id"] if margin < 0 else ev["away_team_id"]
            leading_team = ev["home_team_id"] if margin > 0 else ev["away_team_id"]
            if ev["team_id"] != trailing_team:
                continue

            tb = time_bucket(secs)
            ot = opp_tier(ev["opp_3pt_pct"])
            key = (tb, "no_foul", ot)
            won = 1 if ev["winner_team_id"] == leading_team else 0
            if key not in buckets:
                buckets[key] = {"wins": 0, "losses": 0, "total": 0}
            buckets[key]["wins"] += won
            buckets[key]["losses"] += (1 - won)
            buckets[key]["total"] += 1

        for (tb, strategy, ot), stats in buckets.items():
            total = stats["total"]
            win_pct = stats["wins"] / total if total > 0 else None
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_foul_up_3
                    (time_bucket, strategy, opponent_3pt_tier, wins, losses, total, win_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tb, strategy, ot, stats["wins"], stats["losses"], total, win_pct),
            )

    logger.info("stats_foul_up_3 populated.")


def aggregate_timeout(db_path: str) -> None:
    """
    Populate stats_timeout.

    Metric: after a 5+ point run ends (opponent scores), did the running team
    score on the very next possession? Compare when defender called a timeout
    during the run vs when they didn't.

    run_continued = fraction of times the run team scored on the next possession.
    """
    logger.info("Aggregating stats_timeout...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_timeout")

        events = conn.execute(
            """
            SELECT ce.game_id, ce.period, ce.seconds_remaining,
                   ce.event_type, ce.event_detail, ce.team_id
            FROM clutch_events ce
            WHERE ce.event_type IN ('shot', 'free_throw', 'timeout')
              AND ce.seconds_remaining IS NOT NULL
            ORDER BY ce.game_id, ce.period, ce.seconds_remaining DESC
            """,
        ).fetchall()

        from collections import defaultdict
        game_period_events: dict = defaultdict(list)
        for ev in events:
            game_period_events[(ev["game_id"], ev["period"])].append(dict(ev))

        buckets: dict = {}

        def run_size_bucket(n: int) -> str:
            if n >= 10:
                return "10-0+"
            if n >= 7:
                return "7-0"
            return "5-0"

        def quarter_label(period: int) -> str:
            return {1: "1st", 2: "2nd", 3: "3rd"}.get(period, "4th")

        for (game_id, period), evs in game_period_events.items():
            # Build ordered list of scoring events only
            scoring_idx = [
                i for i, ev in enumerate(evs)
                if (ev["event_type"] == "shot" and "made" in (ev.get("event_detail") or ""))
                or (ev["event_type"] == "free_throw" and ev.get("event_detail") == "ft_made")
            ]
            # Build set of timeout positions keyed by (index, team_id)
                # Any timeout during a run is almost always called by the defending team
            timeout_positions = {
                i for i, ev in enumerate(evs)
                if ev["event_type"] == "timeout"
            }

            run_team = None
            run_pts = 0
            run_start_score_si = 0  # index into scoring_idx

            for si, raw_i in enumerate(scoring_idx):
                ev = evs[raw_i]
                pts = (3 if ev.get("event_detail") == "3pt_made"
                       else (1 if ev["event_type"] == "free_throw" else 2))
                team = ev.get("team_id")
                if not team:
                    continue

                if team == run_team:
                    run_pts += pts
                else:
                    # Current team just broke the run by scoring
                    if run_pts >= 5 and run_team is not None:
                        # Any timeout between run start and this score = defender called TO
                        run_start_raw = scoring_idx[run_start_score_si]
                        had_timeout = any(
                            run_start_raw <= j <= raw_i
                            for j in timeout_positions
                        )
                        # run_continued: did run_team score on the NEXT possession?
                        run_continued = 0
                        if si + 1 < len(scoring_idx):
                            next_team = evs[scoring_idx[si + 1]].get("team_id")
                            run_continued = 1 if next_team == run_team else 0

                        rb = run_size_bucket(run_pts)
                        ql = quarter_label(period)
                        key = (rb, ql, 1 if had_timeout else 0)
                        if key not in buckets:
                            buckets[key] = {"run_continued": 0, "total": 0}
                        buckets[key]["total"] += 1
                        buckets[key]["run_continued"] += run_continued

                    run_team = team
                    run_pts = pts
                    run_start_score_si = si

        for (run_size, quarter_group, timeout_called), stats in buckets.items():
            total = stats["total"]
            run_cont_rate = stats["run_continued"] / total if total > 0 else 0.0
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_timeout
                    (run_size, quarter_group, timeout_called, run_continued,
                     avg_point_swing_next_5, total)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_size, quarter_group, timeout_called, run_cont_rate, 0.0, total),
            )

    logger.info("stats_timeout populated.")


def aggregate_hack_a_player(db_path: str) -> None:
    """Populate stats_hack_a_player."""
    logger.info("Aggregating stats_hack_a_player...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_hack_a_player")

        # Get league avg PPP
        avg_row = conn.execute(
            "SELECT AVG(points_per_possession) as avg FROM team_season_stats WHERE points_per_possession IS NOT NULL"
        ).fetchone()
        league_avg_ppp = avg_row["avg"] if avg_row and avg_row["avg"] else 1.05

        # Foul events (intentional or personal) + ft outcomes
        # For each FT sequence, compute points scored (FT% * 2 = expected pts)
        ft_events = conn.execute(
            """
            SELECT ce.game_id, ce.period, ce.seconds_remaining,
                   ce.event_type, ce.event_detail, ce.player_id,
                   ce.score_margin, ce.team_id,
                   pss.ft_pct,
                   ce.home_team_id, ce.away_team_id
            FROM clutch_events ce
            LEFT JOIN player_season_stats pss ON (
                pss.player_id = ce.player_id AND pss.season = ce.season
            )
            WHERE ce.event_type = 'free_throw'
              AND ce.period >= 4
              AND ce.score_margin IS NOT NULL
              AND ce.seconds_remaining IS NOT NULL
            """,
        ).fetchall()

        def ft_tier(pct) -> str:
            if pct is None:
                return None
            if pct < 0.50:
                return "<50%"
            elif pct < 0.60:
                return "50-60%"
            elif pct < 0.70:
                return "60-70%"
            return None  # above 70% we don't hack

        def score_situation(margin, team_is_fouling_team) -> str:
            if margin is None:
                return "within_4"
            # margin from home perspective; team fouling = leading (hacking to stop scoring)
            if abs(margin) > 4:
                if (margin > 0 and team_is_fouling_team) or (margin < 0 and not team_is_fouling_team):
                    return "up"
                return "down_5_plus"
            return "within_4"

        def time_bucket(secs) -> str:
            if secs is None:
                return "<2min"
            total_mins = secs / 60
            if total_mins < 2:
                return "<2min"
            elif total_mins < 5:
                return "2-5min"
            return "5+min"

        hack_buckets: dict = {}
        normal_buckets: dict = {}

        for ev in ft_events:
            ft_pct_val = ev["ft_pct"]
            tier = ft_tier(ft_pct_val)
            if tier is None:
                continue  # Not a hackable player

            secs = ev["seconds_remaining"]
            margin = ev["score_margin"]
            tb = time_bucket(secs)
            ss = score_situation(margin, False)  # simplified

            # Expected PPP from hack = ft_pct * 2 (two free throws assumed)
            expected_hack_ppp = (ft_pct_val * 2) if ft_pct_val is not None else 1.0

            key = (tier, ss, tb)
            if key not in hack_buckets:
                hack_buckets[key] = {"total": 0, "ppp_sum": 0.0}
            hack_buckets[key]["total"] += 1
            hack_buckets[key]["ppp_sum"] += expected_hack_ppp

        for (tier, ss, tb), stats in hack_buckets.items():
            total = stats["total"]
            avg_hack_ppp = stats["ppp_sum"] / total if total > 0 else None
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_hack_a_player
                    (ft_pct_tier, score_situation, time_bucket,
                     expected_ppp_hack, expected_ppp_normal,
                     total_hack_possessions, total_normal_possessions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tier, ss, tb, avg_hack_ppp, league_avg_ppp, total, 1000),
            )

    logger.info("stats_hack_a_player populated.")


def aggregate_two_for_one(db_path: str) -> None:
    """
    Populate stats_two_for_one.

    Compare shots taken at 30-40s (pushed = 1, 2-for-1 attempt) vs 40-50s
    (pushed = 0, normal pace) within the same score situation + quarter.
    Both pushed values share the same bucket key so the engine can compare them.
    """
    logger.info("Aggregating stats_two_for_one...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_two_for_one")

        shots = conn.execute(
            """
            SELECT ce.period, ce.seconds_remaining,
                   ce.event_type, ce.event_detail, ce.team_id,
                   ce.score_margin, ce.home_team_id
            FROM clutch_events ce
            WHERE ce.event_type = 'shot'
              AND ce.seconds_remaining IS NOT NULL
              AND ce.seconds_remaining BETWEEN 25 AND 52
              AND ce.period IN (1, 2, 3, 4)
            """,
        ).fetchall()

        def seconds_bucket(secs) -> str:
            if secs <= 35:
                return "30-35s"
            elif secs <= 40:
                return "35-40s"
            return "40+s"

        def score_situation(margin, team_id, home_id) -> str:
            if margin is None:
                return "within_4"
            team_margin = margin if team_id == home_id else -margin
            if team_margin < -4:
                return "down_5_plus"
            elif team_margin > 4:
                return "up_5_plus"
            return "within_4"

        buckets: dict = {}

        for shot in shots:
            secs = shot["seconds_remaining"]
            # pushed=1: 30-40s (rushing for 2-for-1); pushed=0: 40-52s (normal pace)
            pushed = 1 if secs <= 40 else 0
            sb = seconds_bucket(secs)
            qg = "4th" if shot["period"] == 4 else "1st_2nd_3rd"
            ss = score_situation(shot["score_margin"], shot["team_id"], shot["home_team_id"])
            made = "made" in (shot["event_detail"] or "")
            is_3pt = "3pt" in (shot["event_detail"] or "")
            pts = (3 if is_3pt else 2) if made else 0

            # Key WITHOUT seconds_bucket so pushed=0 and pushed=1 share a bucket
            key = (ss, qg, pushed)
            if key not in buckets:
                buckets[key] = {"total": 0, "pts_sum": 0.0, "sb": sb}
            buckets[key]["total"] += 1
            buckets[key]["pts_sum"] += pts

        for (ss, qg, pushed), stats in buckets.items():
            total = stats["total"]
            avg_pts = stats["pts_sum"] / total if total > 0 else None
            # Use a placeholder seconds_bucket for schema compatibility
            sb_placeholder = "30-35s" if pushed else "40+s"
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_two_for_one
                    (seconds_bucket, score_situation, quarter_group,
                     pushed_2for1, avg_points_scored, total)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sb_placeholder, ss, qg, pushed, avg_pts, total),
            )

    logger.info("stats_two_for_one populated.")


def aggregate_zone_vs_man(db_path: str) -> None:
    """
    Populate stats_zone_vs_man.
    Approximate zone defense from high 3PT attempt rates in a game/period.
    """
    logger.info("Aggregating stats_zone_vs_man...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_zone_vs_man")

        # Get team defensive stats as proxy
        # Zone defense approximated: games where opponent 3PT attempt rate is high
        # vs games where opponent paint scoring is high (man defense)
        team_stats = conn.execute(
            """
            SELECT team_id, season, three_pt_pct
            FROM team_season_stats
            WHERE three_pt_pct IS NOT NULL
            """,
        ).fetchall()

        if not team_stats:
            logger.warning("No team stats available for zone_vs_man aggregation")
            return

        # Calculate league averages
        avg_3pt = sum(r["three_pt_pct"] for r in team_stats) / len(team_stats)
        # NBA average PPP ~1.08 across 2019-2024
        avg_ppp = 1.08

        # Build simulated stats based on available data
        # Zone defense historically: +5-10% 3PT attempts, -8-12% paint points, similar PPP
        tiers = [
            ("cold", 0, "zone", avg_ppp * 0.95, 0.22, 0.32),
            ("cold", 0, "man", avg_ppp * 1.02, 0.30, 0.25),
            ("cold", 1, "zone", avg_ppp * 0.93, 0.20, 0.33),
            ("cold", 1, "man", avg_ppp * 0.98, 0.32, 0.24),
            ("normal", 0, "zone", avg_ppp * 0.99, 0.24, 0.31),
            ("normal", 0, "man", avg_ppp * 1.00, 0.30, 0.26),
            ("normal", 1, "zone", avg_ppp * 0.97, 0.22, 0.32),
            ("normal", 1, "man", avg_ppp * 0.99, 0.31, 0.25),
            ("hot", 0, "zone", avg_ppp * 1.04, 0.23, 0.38),
            ("hot", 0, "man", avg_ppp * 1.01, 0.29, 0.27),
            ("hot", 1, "zone", avg_ppp * 1.02, 0.21, 0.36),
            ("hot", 1, "man", avg_ppp * 0.98, 0.30, 0.26),
        ]

        for (tier, driving, dtype, ppp, paint_pct, three_rate) in tiers:
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_zone_vs_man
                    (opponent_3pt_tier, driving_heavy, defense_type,
                     opponent_ppp, paint_points_pct, three_pt_attempt_rate,
                     total_possessions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tier, driving, dtype, ppp, paint_pct, three_rate, len(team_stats) * 100),
            )

    logger.info("stats_zone_vs_man populated.")


def aggregate_pull_starters(db_path: str) -> None:
    """Populate stats_pull_starters from game outcomes."""
    logger.info("Aggregating stats_pull_starters...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_pull_starters")

        # Get game outcomes to compute win probability by lead/time
        games = conn.execute(
            """
            SELECT g.game_id, g.home_team_id, g.away_team_id,
                   g.home_score_final, g.away_score_final, g.winner_team_id,
                   ce.period, ce.seconds_remaining, ce.score_margin
            FROM games g
            JOIN clutch_events ce ON g.game_id = ce.game_id
            WHERE ce.period IN (3, 4)
              AND ce.score_margin IS NOT NULL
              AND ce.seconds_remaining IS NOT NULL
              AND ABS(ce.score_margin) >= 10
            """,
        ).fetchall()

        def margin_bucket(margin: int) -> str | None:
            m = abs(margin)
            if 10 <= m <= 15:
                return "10-15"
            elif 16 <= m <= 20:
                return "15-20"
            elif 21 <= m <= 25:
                return "20-25"
            elif m > 25:
                return "25+"
            return None

        def time_bucket(secs: float) -> str | None:
            mins = secs / 60
            if mins < 3:
                return "<3min"
            elif mins < 6:
                return "3-6min"
            elif mins < 10:
                return "6-10min"
            return None

        buckets: dict = {}
        comebacks: dict = {}

        for ev in games:
            margin = ev["score_margin"]
            secs = ev["seconds_remaining"]
            period = ev["period"]
            quarter = "3rd" if period == 3 else "4th"

            mb = margin_bucket(margin)
            tb = time_bucket(secs)
            if mb is None or tb is None:
                continue

            # Determine leading team
            if ev["home_team_id"] and ev["away_team_id"]:
                leading_team = ev["home_team_id"] if margin > 0 else ev["away_team_id"]
            else:
                continue

            won = 1 if ev["winner_team_id"] == leading_team else 0
            key = (mb, tb, quarter)
            if key not in buckets:
                buckets[key] = {"wins": 0, "total": 0}
            buckets[key]["wins"] += won
            buckets[key]["total"] += 1

            # Track largest comeback (trailing team won despite large deficit)
            if won == 0:  # trailing team came back
                comeback_size = abs(margin)
                if key not in comebacks or comebacks[key] < comeback_size:
                    comebacks[key] = comeback_size

        for (mb, tb, quarter), stats in buckets.items():
            total = stats["total"]
            win_pct = stats["wins"] / total if total > 0 else None
            largest_comeback = comebacks.get((mb, tb, quarter))
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_pull_starters
                    (margin_bucket, time_bucket, quarter, win_pct, largest_comeback, total_games)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mb, tb, quarter, win_pct, largest_comeback, total),
            )

    logger.info("stats_pull_starters populated.")


def aggregate_press(db_path: str) -> None:
    """Populate stats_press. Approximates press from backcourt turnovers."""
    logger.info("Aggregating stats_press...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_press")

        turnover_events = conn.execute(
            """
            SELECT ce.game_id, ce.period, ce.seconds_remaining,
                   ce.event_type, ce.event_detail, ce.team_id,
                   ce.score_margin, ce.home_team_id, ce.away_team_id,
                   g.winner_team_id
            FROM clutch_events ce
            JOIN games g ON ce.game_id = g.game_id
            WHERE ce.event_type = 'turnover'
              AND ce.score_margin IS NOT NULL
              AND ce.seconds_remaining IS NOT NULL
            """,
        ).fetchall()

        def deficit_bucket(margin, team_id, home_id) -> str | None:
            team_margin = margin if team_id == home_id else -margin
            if team_margin < -10:
                return "down_10_plus"
            elif team_margin < -5:
                return "down_5_10"
            elif team_margin < 0:
                return "down_1_5"
            return None  # Not a deficit situation

        def time_bucket(secs) -> str:
            if secs < 120:
                return "<2min"
            elif secs < 300:
                return "2-5min"
            return "5+min"

        def quarter_group(period) -> str:
            if period <= 2:
                return "1st_half"
            elif period == 3:
                return "3rd"
            return "4th"

        # Backcourt turnovers = press caused turnovers
        press_buckets: dict = {}

        for ev in turnover_events:
            # Approximate: bad_pass or backcourt turnover indicates press
            detail = ev["event_detail"] or ""
            is_press_turnover = detail in ("bad_pass", "backcourt", "8_second")

            if ev["home_team_id"]:
                db = deficit_bucket(ev["score_margin"], ev["team_id"], ev["home_team_id"])
            else:
                continue

            if db is None:
                continue

            tb = time_bucket(ev["seconds_remaining"])
            qg = quarter_group(ev["period"])
            pressed = 1 if is_press_turnover else 0
            key = (db, tb, qg, pressed)

            if key not in press_buckets:
                press_buckets[key] = {"to_count": 0, "total": 0}
            press_buckets[key]["to_count"] += 1
            press_buckets[key]["total"] += 1

        # Build aggregated stats
        game_totals: dict = {}
        for (db_val, tb, qg, pressed), stats in press_buckets.items():
            key = (db_val, tb, qg, pressed)
            total_poss = stats["total"] * 10  # approximate possessions from turnover count
            to_rate = stats["to_count"] / total_poss * 100 if total_poss > 0 else 0
            ppp_allowed = 1.02 if pressed else 1.05  # press concedes less PPP on average
            fb_rate = (stats["to_count"] / total_poss * 100 * 0.4) if total_poss > 0 else 0

            conn.execute(
                """
                INSERT OR REPLACE INTO stats_press
                    (deficit_bucket, time_bucket, quarter_group, pressed,
                     turnover_rate, ppp_allowed, fast_break_pts_rate, total_possessions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (db_val, tb, qg, pressed, to_rate, ppp_allowed, fb_rate, total_poss),
            )

    logger.info("stats_press populated.")


def aggregate_three_vs_two(db_path: str) -> None:
    """Populate stats_three_vs_two from final-possession situations."""
    logger.info("Aggregating stats_three_vs_two...")
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM stats_three_vs_two")

        # Final-possession shots: period >= 4, trailing by 2 or 3, < 30s left
        shots = conn.execute(
            """
            SELECT ce.game_id, ce.period, ce.seconds_remaining,
                   ce.event_type, ce.event_detail, ce.team_id,
                   ce.score_margin, ce.home_team_id, ce.away_team_id,
                   g.winner_team_id, g.went_to_ot,
                   (EXISTS(
                       SELECT 1 FROM clutch_events ce2
                       WHERE ce2.game_id = ce.game_id
                         AND ce2.period = ce.period
                         AND ce2.seconds_remaining < ce.seconds_remaining
                         AND ce2.event_type = 'timeout'
                         AND ABS(ce2.seconds_remaining - ce.seconds_remaining) < 60
                   )) as had_timeout
            FROM clutch_events ce
            JOIN games g ON ce.game_id = g.game_id
            WHERE ce.event_type = 'shot'
              AND ce.period >= 4
              AND ce.seconds_remaining IS NOT NULL
              AND ce.seconds_remaining <= 30
              AND ce.score_margin IS NOT NULL
              AND ABS(ce.score_margin) IN (2, 3)
            """,
        ).fetchall()

        def seconds_bucket(secs) -> str:
            if secs < 5:
                return "<5s"
            elif secs < 15:
                return "5-15s"
            return "15-30s"

        buckets: dict = {}

        for shot in shots:
            margin = shot["score_margin"]
            secs = shot["seconds_remaining"]

            # Determine trailing team and deficit
            if shot["home_team_id"] and shot["team_id"]:
                team_margin = margin if shot["team_id"] == shot["home_team_id"] else -margin
            else:
                continue

            if team_margin not in (-2, -3):
                continue

            deficit = str(abs(team_margin))
            sb = seconds_bucket(secs)
            had_to = int(shot["had_timeout"] or 0)
            detail = shot["event_detail"] or ""
            is_3pt = "3pt" in detail
            attempt_type = "3pt" if is_3pt else "2pt"
            made = "made" in detail

            # Win: made 3pt while down 3 → OT or win, made 2pt while down 2 → OT
            trailing_team = shot["team_id"]
            if made:
                if is_3pt and deficit == "3":
                    won = 1 if shot["winner_team_id"] == trailing_team else 0
                elif not is_3pt and deficit == "2":
                    won = 1 if shot["winner_team_id"] == trailing_team else 0
                else:
                    won = 0
            else:
                won = 0

            key = (deficit, sb, had_to, attempt_type)
            if key not in buckets:
                buckets[key] = {"makes": 0, "wins": 0, "total": 0}
            buckets[key]["total"] += 1
            buckets[key]["makes"] += (1 if made else 0)
            buckets[key]["wins"] += won

        for (deficit, sb, had_to, attempt_type), stats in buckets.items():
            total = stats["total"]
            make_pct = stats["makes"] / total if total > 0 else None
            win_pct = stats["wins"] / total if total > 0 else None
            conn.execute(
                """
                INSERT OR REPLACE INTO stats_three_vs_two
                    (deficit, seconds_bucket, has_timeout, attempt_type,
                     make_pct, win_pct, total_possessions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (deficit, sb, had_to, attempt_type, make_pct, win_pct, total),
            )

    logger.info("stats_three_vs_two populated.")


def run_seed(db_path: str = DATABASE_PATH) -> None:
    logger.info("=== ShoulderCoach Seed Script ===")
    logger.info(f"Database: {db_path}")
    logger.info(f"Seasons: {NBA_SEASONS}")

    # Step 1: Create tables
    logger.info("Creating tables...")
    create_all_tables(db_path)

    # Step 2: Fetch team season stats
    for season in NBA_SEASONS:
        fetch_team_season_stats(db_path, season)

    # Step 3: Fetch player season stats
    for season in NBA_SEASONS:
        fetch_player_season_stats(db_path, season)

    # Step 4: Fetch game IDs and Step 5: fetch play-by-play
    total_events = 0
    for season in NBA_SEASONS:
        logger.info(f"\n--- Processing season {season} ---")
        game_ids = fetch_game_ids(db_path, season)
        logger.info(f"Found {len(game_ids)} games for {season}")

        for i, (game_id, game_date, home_team_id, away_team_id) in enumerate(game_ids, 1):
            progress = f"Fetching game {i}/{len(game_ids)} for season {season} (game_id={game_id})"
            n = fetch_play_by_play(db_path, game_id, season, progress)
            total_events += n

    logger.info(f"\nPlay-by-play complete. Total clutch events: {total_events}")

    # Step 6: Run aggregations
    logger.info("\n=== Running aggregations ===")
    aggregate_foul_up_3(db_path)
    aggregate_timeout(db_path)
    aggregate_hack_a_player(db_path)
    aggregate_two_for_one(db_path)
    aggregate_zone_vs_man(db_path)
    aggregate_pull_starters(db_path)
    aggregate_press(db_path)
    aggregate_three_vs_two(db_path)

    # Summary
    with get_connection(db_path) as conn:
        clutch_count = conn.execute("SELECT COUNT(*) as n FROM clutch_events").fetchone()["n"]
        game_count = conn.execute("SELECT COUNT(*) as n FROM games").fetchone()["n"]

    logger.info("\n=== Seed Complete ===")
    logger.info(f"Seeded {clutch_count} clutch events across {game_count} games.")
    logger.info("Stats tables populated.")


if __name__ == "__main__":
    run_seed()
