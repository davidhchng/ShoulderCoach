from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD


class TimeoutEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "timeout"

    @property
    def display_name(self) -> str:
        return "Call Timeout"

    @property
    def description(self) -> str:
        return "The other team is on a run. Should I call timeout right now?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "opponent_run",
                    "label": "Their run",
                    "type": "button_group",
                    "options": ["5-0", "7-0", "10-0+"],
                    "default": "7-0",
                },
                {
                    "key": "quarter",
                    "label": "Quarter",
                    "type": "button_group",
                    "options": ["1st", "2nd", "3rd", "4th"],
                    "default": "4th",
                },
                {
                    "key": "timeouts_remaining",
                    "label": "Your timeouts left",
                    "type": "button_group",
                    "options": ["1", "2", "3+"],
                    "default": "2",
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        run_size = inputs.get("opponent_run", "7-0")
        quarter = inputs.get("quarter", "4th")
        timeouts_remaining = inputs.get("timeouts_remaining", "2")

        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT timeout_called, run_continued, avg_point_swing_next_5, total
                FROM stats_timeout
                WHERE run_size = ? AND quarter_group = ?
                """,
                (run_size, quarter),
            ).fetchall()

        to_row = next((r for r in rows if r["timeout_called"] == 1), None)
        no_to_row = next((r for r in rows if r["timeout_called"] == 0), None)

        if not to_row and not no_to_row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Run continuation rate with timeout",
                primary_sample_size=0,
                insufficient_data=True,
            )

        to_n = to_row["total"] if to_row else 0
        no_to_n = no_to_row["total"] if no_to_row else 0
        min_n = min(n for n in [to_n, no_to_n] if n > 0) if (to_n or no_to_n) else 0

        if min_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Run continuation rate with timeout",
                primary_sample_size=min_n,
                insufficient_data=True,
            )

        # run_continued is stored as a rate (fraction of possessions run continued)
        to_continue = to_row["run_continued"] if to_row else None
        no_to_continue = no_to_row["run_continued"] if no_to_row else None

        # Lower run continuation = better (timeout stops the run)
        to_swing = to_row["avg_point_swing_next_5"] if to_row else None
        no_to_swing = no_to_row["avg_point_swing_next_5"] if no_to_row else None

        # Recommend timeout if it reduces run continuation
        if to_continue is not None and no_to_continue is not None:
            timeout_helps = to_continue < no_to_continue
        else:
            timeout_helps = True  # default to recommending timeout

        # Factor in timeout scarcity: if only 1 timeout left and early quarter, note it
        scarce_timeout = (timeouts_remaining == "1" and quarter in ("1st", "2nd", "3rd"))

        if timeout_helps and not scarce_timeout:
            recommended = "call timeout"
        elif timeout_helps and scarce_timeout:
            recommended = "call timeout (consider saving for late game)"
        else:
            recommended = "don't call timeout"

        primary_rate = (to_continue * 100) if to_continue is not None else 0.0
        comp_rate = (no_to_continue * 100) if no_to_continue is not None else None

        low_sample = min_n < LOW_SAMPLE_THRESHOLD
        edge = round(abs((to_continue or 0) - (no_to_continue or 0)) * 100, 1)

        if edge >= 10:
            confidence = "low" if low_sample else "high"
        elif edge >= 5:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        details = {}
        if to_swing is not None:
            details["point_swing_with_timeout"] = round(to_swing, 2)
        if no_to_swing is not None:
            details["point_swing_without_timeout"] = round(no_to_swing, 2)
        if scarce_timeout:
            details["timeout_scarcity_warning"] = True

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=round(primary_rate, 1),
            primary_stat_label="Run continuation rate with timeout",
            primary_sample_size=to_n,
            comparison_stat=round(comp_rate, 1) if comp_rate is not None else None,
            comparison_stat_label="Run continuation rate without timeout",
            comparison_sample_size=no_to_n or None,
            edge_pct=edge,
            details=details,
            low_sample_warning=low_sample,
        )
