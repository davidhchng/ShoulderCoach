from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class ZoneVsManEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "zone_vs_man"

    @property
    def display_name(self) -> str:
        return "Zone vs Man"

    @property
    def description(self) -> str:
        return "Should I switch to zone defense right now?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "opponent_3pt_tonight",
                    "label": "Their 3PT shooting tonight",
                    "type": "button_group",
                    "options": ["Cold (<30%)", "Normal", "Hot (>40%)"],
                    "default": "Normal",
                },
                {
                    "key": "driving_a_lot",
                    "label": "Are they driving a lot?",
                    "type": "toggle",
                    "default": False,
                },
                {
                    "key": "score_situation",
                    "label": "Score situation",
                    "type": "button_group",
                    "options": ["Down", "Close", "Up"],
                    "default": "Close",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        opp_3pt = inputs.get("opponent_3pt_tonight", "Normal")
        driving = inputs.get("driving_a_lot", False)
        score_situation = inputs.get("score_situation", "Close")

        tier_map = {
            "Cold (<30%)": "cold",
            "Normal": "normal",
            "Hot (>40%)": "hot",
        }
        opp_tier = tier_map.get(opp_3pt, "normal")
        driving_heavy = 1 if driving else 0

        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT defense_type, opponent_ppp, paint_points_pct,
                       three_pt_attempt_rate, total_possessions
                FROM stats_zone_vs_man
                WHERE opponent_3pt_tier = ? AND driving_heavy = ?
                """,
                (opp_tier, driving_heavy),
            ).fetchall()

        zone_row = next((r for r in rows if r["defense_type"] == "zone"), None)
        man_row = next((r for r in rows if r["defense_type"] == "man"), None)

        if not zone_row and not man_row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Opponent PPP vs zone",
                primary_sample_size=0,
                insufficient_data=True,
            )

        zone_n = zone_row["total_possessions"] if zone_row else 0
        man_n = man_row["total_possessions"] if man_row else 0
        min_n = min(n for n in [zone_n, man_n] if n > 0) if (zone_n or man_n) else 0

        if min_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Opponent PPP vs zone",
                primary_sample_size=min_n,
                insufficient_data=True,
            )

        zone_ppp = zone_row["opponent_ppp"] if zone_row else 1.1
        man_ppp = man_row["opponent_ppp"] if man_row else 1.0

        # Zone reduces paint but opens 3s
        # If opponent is hot from 3, zone is riskier
        if opp_tier == "hot":
            # Extra penalty for zone when they're hot
            effective_zone_ppp = zone_ppp * 1.05
        else:
            effective_zone_ppp = zone_ppp

        # If driving a lot, zone helps clog the paint
        if driving_heavy:
            effective_zone_ppp = effective_zone_ppp * 0.97

        recommended = "switch to zone" if effective_zone_ppp < man_ppp else "stay in man"

        low_sample = min_n < LOW_SAMPLE_THRESHOLD
        ppp_diff = round(abs(zone_ppp - man_ppp), 3)

        if ppp_diff >= 0.1:
            confidence = "low" if low_sample else "high"
        elif ppp_diff >= 0.05:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        # Build tradeoff details
        details = {}
        if zone_row and man_row:
            paint_diff = (zone_row["paint_points_pct"] or 0) - (man_row["paint_points_pct"] or 0)
            three_diff = (zone_row["three_pt_attempt_rate"] or 0) - (man_row["three_pt_attempt_rate"] or 0)
            details["zone_reduces_paint_pct"] = round(-paint_diff * 100, 1)
            details["zone_increases_3pt_attempt_rate"] = round(three_diff * 100, 1)

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=round(zone_ppp, 3),
            primary_stat_label="Opponent PPP vs zone",
            primary_sample_size=zone_n,
            comparison_stat=round(man_ppp, 3),
            comparison_stat_label="Opponent PPP vs man",
            comparison_sample_size=man_n,
            edge_pct=round(ppp_diff * 100, 1),
            details=details,
            low_sample_warning=low_sample,
        )
