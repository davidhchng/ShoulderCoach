from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class HackAPlayerEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "hack_a_player"

    @property
    def display_name(self) -> str:
        return "Hack-a-Player"

    @property
    def description(self) -> str:
        return "Their big man can't shoot free throws. Should we keep fouling him?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "opponent_ft_pct",
                    "label": "Their FT%",
                    "type": "button_group",
                    "options": ["<50%", "50-60%", "60-70%"],
                    "default": "<50%",
                },
                {
                    "key": "score_differential",
                    "label": "Score situation",
                    "type": "button_group",
                    "options": ["Down 5+", "Within 4", "Up"],
                    "default": "Down 5+",
                },
                {
                    "key": "time_remaining",
                    "label": "Time remaining",
                    "type": "button_group",
                    "options": ["<2 min", "2-5 min", "5+ min"],
                    "default": "<2 min",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        ft_pct = inputs.get("opponent_ft_pct", "<50%")
        score_diff = inputs.get("score_differential", "Down 5+")
        time_remaining = inputs.get("time_remaining", "<2 min")

        # Map to DB values
        score_map = {
            "Down 5+": "down_5_plus",
            "Within 4": "within_4",
            "Up": "up",
        }
        time_map = {
            "<2 min": "<2min",
            "2-5 min": "2-5min",
            "5+ min": "5+min",
        }
        score_situation = score_map.get(score_diff, "down_5_plus")
        time_bucket = time_map.get(time_remaining, "<2min")

        with get_connection(db_path) as conn:
            row = conn.execute(
                """
                SELECT expected_ppp_hack, expected_ppp_normal,
                       total_hack_possessions, total_normal_possessions
                FROM stats_hack_a_player
                WHERE ft_pct_tier = ? AND score_situation = ? AND time_bucket = ?
                """,
                (ft_pct, score_situation, time_bucket),
            ).fetchone()

        if not row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Expected PPP when hacking",
                primary_sample_size=0,
                insufficient_data=True,
            )

        hack_ppp = row["expected_ppp_hack"]
        normal_ppp = row["expected_ppp_normal"]
        hack_n = row["total_hack_possessions"]
        normal_n = row["total_normal_possessions"]

        if hack_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=round(hack_ppp, 3) if hack_ppp else 0.0,
                primary_stat_label="Expected PPP when hacking",
                primary_sample_size=hack_n,
                insufficient_data=True,
            )

        hack_advantage = normal_ppp - hack_ppp  # positive = hacking is better
        recommended = "hack them" if hack_advantage > 0.05 else "don't hack"

        # If we're winning, hack is less urgent unless big FT% gap
        if score_diff == "Up" and hack_advantage < 0.15:
            recommended = "don't hack"

        low_sample = hack_n < LOW_SAMPLE_THRESHOLD
        edge = round(abs(hack_advantage), 3)

        if hack_advantage > 0.15:
            confidence = "low" if low_sample else "high"
        elif hack_advantage > 0.05:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=round(hack_ppp, 3),
            primary_stat_label="Expected PPP when hacking",
            primary_sample_size=hack_n,
            comparison_stat=round(normal_ppp, 3),
            comparison_stat_label="League avg PPP (normal offense)",
            comparison_sample_size=normal_n,
            edge_pct=round(hack_advantage, 3),
            details={"hack_advantage_per_possession": round(hack_advantage, 3)},
            low_sample_warning=low_sample,
        )
