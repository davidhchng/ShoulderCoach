from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class FoulUp3Engine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "foul_up_3"

    @property
    def display_name(self) -> str:
        return "Foul Up 3"

    @property
    def description(self) -> str:
        return "Should I foul when up 3 late in the game?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "time_remaining",
                    "label": "Time Left",
                    "type": "button_group",
                    "options": ["<10s", "10-30s", "30-60s"],
                    "default": "<10s",
                },
                {
                    "key": "opponent_has_ball",
                    "label": "They have the ball?",
                    "type": "toggle",
                    "default": True,
                },
                {
                    "key": "opponent_shooting",
                    "label": "Their 3PT shooting",
                    "type": "button_group",
                    "options": ["Average", "Strong"],
                    "default": "Average",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        time_remaining = inputs.get("time_remaining", "<10s")
        opponent_shooting = inputs.get("opponent_shooting", "Average")

        # Map display values to DB values
        time_bucket = time_remaining  # already matches: '<10s', '10-30s', '30-60s'
        opp_tier = opponent_shooting.lower()  # 'average' or 'strong'

        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT strategy, win_pct, total
                FROM stats_foul_up_3
                WHERE time_bucket = ? AND opponent_3pt_tier = ?
                """,
                (time_bucket, opp_tier),
            ).fetchall()

        foul_row = next((r for r in rows if r["strategy"] == "foul"), None)
        no_foul_row = next((r for r in rows if r["strategy"] == "no_foul"), None)

        # Handle missing data
        if not foul_row and not no_foul_row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Win % when fouling",
                primary_sample_size=0,
                insufficient_data=True,
            )

        foul_n = foul_row["total"] if foul_row else 0
        no_foul_n = no_foul_row["total"] if no_foul_row else 0
        min_n = min(foul_n, no_foul_n) if foul_n and no_foul_n else max(foul_n, no_foul_n)

        if min_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=foul_row["win_pct"] if foul_row else 0.0,
                primary_stat_label="Win % when fouling",
                primary_sample_size=foul_n,
                comparison_stat=no_foul_row["win_pct"] if no_foul_row else None,
                comparison_stat_label="Win % without fouling",
                comparison_sample_size=no_foul_n or None,
                insufficient_data=True,
            )

        foul_pct = foul_row["win_pct"] if foul_row else 50.0
        no_foul_pct = no_foul_row["win_pct"] if no_foul_row else 50.0
        recommended = "foul" if foul_pct >= no_foul_pct else "don't foul"

        # win_pct values are fractions (0-1); convert to percentage points for edge
        foul_pct_display = round(foul_pct * 100, 1) if foul_pct <= 1 else round(foul_pct, 1)
        no_foul_pct_display = round(no_foul_pct * 100, 1) if no_foul_pct <= 1 else round(no_foul_pct, 1)

        if foul_pct >= no_foul_pct:
            primary_pct_d, primary_n2, primary_label2 = foul_pct_display, foul_n, "Win % when fouling"
            comp_pct_d, comp_n2, comp_label2 = no_foul_pct_display, no_foul_n, "Win % without fouling"
        else:
            primary_pct_d, primary_n2, primary_label2 = no_foul_pct_display, no_foul_n, "Win % without fouling"
            comp_pct_d, comp_n2, comp_label2 = foul_pct_display, foul_n, "Win % when fouling"

        edge = round(abs(foul_pct_display - no_foul_pct_display), 1)
        low_sample = min_n < LOW_SAMPLE_THRESHOLD

        if edge >= 5:
            confidence = "low" if low_sample else "high"
        elif edge >= 2:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=primary_pct_d,
            primary_stat_label=primary_label2,
            primary_sample_size=primary_n2,
            comparison_stat=comp_pct_d,
            comparison_stat_label=comp_label2,
            comparison_sample_size=comp_n2,
            edge_pct=edge,
            low_sample_warning=low_sample,
        )
