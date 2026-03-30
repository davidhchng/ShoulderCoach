from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class PressEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "press"

    @property
    def display_name(self) -> str:
        return "Full-Court Press"

    @property
    def description(self) -> str:
        return "Should I press full court right now?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "score_differential",
                    "label": "Score situation",
                    "type": "button_group",
                    "options": ["Down 10+", "Down 5-10", "Down 1-5"],
                    "default": "Down 5-10",
                },
                {
                    "key": "time_remaining",
                    "label": "Time remaining",
                    "type": "button_group",
                    "options": ["<2 min", "2-5 min", "5+ min"],
                    "default": "2-5 min",
                },
                {
                    "key": "quarter",
                    "label": "Quarter",
                    "type": "button_group",
                    "options": ["1st half", "3rd", "4th"],
                    "default": "4th",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        score_diff = inputs.get("score_differential", "Down 5-10")
        time_remaining = inputs.get("time_remaining", "2-5 min")
        quarter = inputs.get("quarter", "4th")

        deficit_map = {
            "Down 10+": "down_10_plus",
            "Down 5-10": "down_5_10",
            "Down 1-5": "down_1_5",
        }
        time_map = {
            "<2 min": "<2min",
            "2-5 min": "2-5min",
            "5+ min": "5+min",
        }
        quarter_map = {
            "1st half": "1st_half",
            "3rd": "3rd",
            "4th": "4th",
        }
        deficit_bucket = deficit_map.get(score_diff, "down_5_10")
        time_bucket = time_map.get(time_remaining, "2-5min")
        quarter_group = quarter_map.get(quarter, "4th")

        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT pressed, turnover_rate, ppp_allowed, fast_break_pts_rate, total_possessions
                FROM stats_press
                WHERE deficit_bucket = ? AND time_bucket = ? AND quarter_group = ?
                """,
                (deficit_bucket, time_bucket, quarter_group),
            ).fetchall()

        press_row = next((r for r in rows if r["pressed"] == 1), None)
        no_press_row = next((r for r in rows if r["pressed"] == 0), None)

        if not press_row and not no_press_row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Turnovers per 100 poss when pressing",
                primary_sample_size=0,
                insufficient_data=True,
            )

        press_n = press_row["total_possessions"] if press_row else 0
        no_press_n = no_press_row["total_possessions"] if no_press_row else 0
        min_n = min(n for n in [press_n, no_press_n] if n > 0) if (press_n or no_press_n) else 0

        if min_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Turnovers per 100 poss when pressing",
                primary_sample_size=min_n,
                insufficient_data=True,
            )

        press_to_rate = press_row["turnover_rate"] if press_row else 0
        no_press_to_rate = no_press_row["turnover_rate"] if no_press_row else 0
        press_ppp = press_row["ppp_allowed"] if press_row else 1.0
        no_press_ppp = no_press_row["ppp_allowed"] if no_press_row else 1.0
        press_fb = press_row["fast_break_pts_rate"] if press_row else 0
        no_press_fb = no_press_row["fast_break_pts_rate"] if no_press_row else 0

        extra_turnovers = round((press_to_rate or 0) - (no_press_to_rate or 0), 1)
        extra_fb_pts = round((press_fb or 0) - (no_press_fb or 0), 1)

        # Press increases variance — recommend when deficit is large enough
        # Down 10+: press is almost always the right call
        # Down 5-10: press is reasonable
        # Down 1-5: press adds unnecessary risk
        if deficit_bucket == "down_10_plus":
            recommended = "press full court"
        elif deficit_bucket == "down_5_10":
            if extra_turnovers > 3 and extra_fb_pts < 5:
                recommended = "press full court"
            else:
                recommended = "consider pressing"
        else:
            recommended = "don't press — variance not worth it"

        low_sample = min_n < LOW_SAMPLE_THRESHOLD

        to_diff = round(abs(extra_turnovers), 1)
        if to_diff >= 5:
            confidence = "low" if low_sample else "high"
        elif to_diff >= 2:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        details = {
            "extra_turnovers_per_100_poss": extra_turnovers,
            "extra_fast_break_pts_allowed_per_100_poss": extra_fb_pts,
        }

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=round(press_to_rate, 1) if press_to_rate else 0.0,
            primary_stat_label="Turnovers per 100 poss when pressing",
            primary_sample_size=press_n,
            comparison_stat=round(no_press_to_rate, 1) if no_press_to_rate else 0.0,
            comparison_stat_label="Turnovers per 100 poss (no press)",
            comparison_sample_size=no_press_n,
            edge_pct=round(extra_turnovers, 1),
            details=details,
            low_sample_warning=low_sample,
        )
