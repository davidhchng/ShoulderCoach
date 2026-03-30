from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class PullStartersEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "pull_starters"

    @property
    def display_name(self) -> str:
        return "Pull Starters"

    @property
    def description(self) -> str:
        return "Is this game effectively over? Can I rest my starters?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "score_margin",
                    "label": "Your lead",
                    "type": "button_group",
                    "options": ["10-15", "15-20", "20-25", "25+"],
                    "default": "15-20",
                },
                {
                    "key": "time_remaining",
                    "label": "Time remaining",
                    "type": "button_group",
                    "options": ["<3 min", "3-6 min", "6-10 min"],
                    "default": "3-6 min",
                },
                {
                    "key": "quarter",
                    "label": "Quarter",
                    "type": "button_group",
                    "options": ["3rd", "4th"],
                    "default": "4th",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        margin = inputs.get("score_margin", "15-20")
        time_remaining = inputs.get("time_remaining", "3-6 min")
        quarter = inputs.get("quarter", "4th")

        time_map = {
            "<3 min": "<3min",
            "3-6 min": "3-6min",
            "6-10 min": "6-10min",
        }
        time_bucket = time_map.get(time_remaining, "3-6min")

        with get_connection(db_path) as conn:
            row = conn.execute(
                """
                SELECT win_pct, largest_comeback, total_games
                FROM stats_pull_starters
                WHERE margin_bucket = ? AND time_bucket = ? AND quarter = ?
                """,
                (margin, time_bucket, quarter),
            ).fetchone()

        if not row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Win % with this lead",
                primary_sample_size=0,
                insufficient_data=True,
            )

        n = row["total_games"]
        win_pct = row["win_pct"]
        largest_comeback = row["largest_comeback"]

        if n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=round(win_pct * 100, 1) if win_pct else 0.0,
                primary_stat_label="Win % with this lead",
                primary_sample_size=n,
                insufficient_data=True,
            )

        win_pct_display = round(win_pct * 100, 1) if win_pct <= 1 else round(win_pct, 1)

        if win_pct_display >= 95:
            recommended = "pull starters"
            confidence = "low" if n < LOW_SAMPLE_THRESHOLD else "high"
        elif win_pct_display >= 90:
            recommended = "borderline — your call"
            confidence = "low" if n < LOW_SAMPLE_THRESHOLD else "moderate"
        else:
            recommended = "keep starters in"
            confidence = "low" if n < LOW_SAMPLE_THRESHOLD else "moderate"

        details = {}
        if largest_comeback is not None:
            details["largest_comeback_from_similar_deficit"] = largest_comeback
            details["largest_comeback_note"] = (
                f"Largest comeback from a similar deficit: {largest_comeback} points"
            )

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=win_pct_display,
            primary_stat_label="Win % with this lead",
            primary_sample_size=n,
            details=details,
            low_sample_warning=n < LOW_SAMPLE_THRESHOLD,
        )
