from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class TwoForOneEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "two_for_one"

    @property
    def display_name(self) -> str:
        return "2-for-1"

    @property
    def description(self) -> str:
        return "Should we push for a quick shot to get two possessions this quarter?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "seconds_left",
                    "label": "Seconds left in quarter",
                    "type": "button_group",
                    "options": ["30-35s", "35-40s", "40+s"],
                    "default": "30-35s",
                },
                {
                    "key": "score_differential",
                    "label": "Score situation",
                    "type": "button_group",
                    "options": ["Down 5+", "Within 4", "Up 5+"],
                    "default": "Within 4",
                },
                {
                    "key": "quarter",
                    "label": "Which quarter?",
                    "type": "button_group",
                    "options": ["1st/2nd/3rd", "4th"],
                    "default": "1st/2nd/3rd",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        seconds_left = inputs.get("seconds_left", "30-35s")
        score_diff = inputs.get("score_differential", "Within 4")
        quarter = inputs.get("quarter", "1st/2nd/3rd")

        score_map = {
            "Down 5+": "down_5_plus",
            "Within 4": "within_4",
            "Up 5+": "up_5_plus",
        }
        score_situation = score_map.get(score_diff, "within_4")
        quarter_group = "4th" if quarter == "4th" else "1st_2nd_3rd"

        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT pushed_2for1, avg_points_scored, total
                FROM stats_two_for_one
                WHERE score_situation = ? AND quarter_group = ?
                """,
                (score_situation, quarter_group),
            ).fetchall()

        pushed_row = next((r for r in rows if r["pushed_2for1"] == 1), None)
        normal_row = next((r for r in rows if r["pushed_2for1"] == 0), None)

        if not pushed_row and not normal_row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Avg pts scored pushing 2-for-1",
                primary_sample_size=0,
                insufficient_data=True,
            )

        pushed_n = pushed_row["total"] if pushed_row else 0
        normal_n = normal_row["total"] if normal_row else 0
        min_n = min(n for n in [pushed_n, normal_n] if n > 0) if (pushed_n or normal_n) else 0

        if min_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Avg pts scored pushing 2-for-1",
                primary_sample_size=min_n,
                insufficient_data=True,
            )

        pushed_pts = pushed_row["avg_points_scored"] if pushed_row else 0.0
        normal_pts = normal_row["avg_points_scored"] if normal_row else 0.0

        # If up big, 2-for-1 risk may not be worth it
        if score_diff == "Up 5+" and (pushed_pts - normal_pts) < 0.3:
            recommended = "play normal offense"
        elif pushed_pts > normal_pts:
            recommended = "push for 2-for-1"
        else:
            recommended = "play normal offense"

        low_sample = min_n < LOW_SAMPLE_THRESHOLD
        edge = round(abs(pushed_pts - normal_pts), 2)

        if pushed_pts > normal_pts:
            primary_pts, primary_n, primary_label = pushed_pts, pushed_n, "Avg pts scored pushing 2-for-1"
            comp_pts, comp_n, comp_label = normal_pts, normal_n, "Avg pts scored (normal pace)"
        else:
            primary_pts, primary_n, primary_label = normal_pts, normal_n, "Avg pts scored (normal pace)"
            comp_pts, comp_n, comp_label = pushed_pts, pushed_n, "Avg pts scored pushing 2-for-1"

        if edge >= 0.5:
            confidence = "low" if low_sample else "high"
        elif edge >= 0.2:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        details = {}
        if quarter == "4th":
            details["note"] = "Q4: clock management adds extra value to possession control"

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=round(primary_pts, 2),
            primary_stat_label=primary_label,
            primary_sample_size=primary_n,
            comparison_stat=round(comp_pts, 2),
            comparison_stat_label=comp_label,
            comparison_sample_size=comp_n,
            edge_pct=edge,
            details=details,
            low_sample_warning=low_sample,
        )
