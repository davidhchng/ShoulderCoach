from app.engine.base import DecisionEngine, DecisionResult
from app.database import get_connection
from app.config import LOW_SAMPLE_THRESHOLD, INSUFFICIENT_DATA_THRESHOLD

# Historical NBA OT win rate for the team that ties it (roughly 50%)
OT_WIN_RATE = 0.50


class ThreeVsTwoEngine(DecisionEngine):
    @property
    def decision_type(self) -> str:
        return "three_vs_two"

    @property
    def display_name(self) -> str:
        return "Go for 3 or 2?"

    @property
    def description(self) -> str:
        return "We're down 2 or 3. Should we go for the 3 or play for a quick 2?"

    @property
    def input_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "down_by",
                    "label": "Down by",
                    "type": "button_group",
                    "options": ["2", "3"],
                    "default": "3",
                },
                {
                    "key": "seconds_remaining",
                    "label": "Seconds remaining",
                    "type": "button_group",
                    "options": ["<5s", "5-15s", "15-30s"],
                    "default": "5-15s",
                },
                {
                    "key": "has_timeout",
                    "label": "Do you have a timeout?",
                    "type": "toggle",
                    "default": False,
                },
            ]
        }

    def evaluate(self, inputs: dict, db_path: str) -> DecisionResult:
        down_by = inputs.get("down_by", "3")
        seconds_remaining = inputs.get("seconds_remaining", "5-15s")
        has_timeout = inputs.get("has_timeout", False)
        has_timeout_int = 1 if has_timeout else 0

        with get_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT attempt_type, make_pct, win_pct, total_possessions
                FROM stats_three_vs_two
                WHERE deficit = ? AND seconds_bucket = ? AND has_timeout = ?
                """,
                (down_by, seconds_remaining, has_timeout_int),
            ).fetchall()

        two_pt_row = next((r for r in rows if r["attempt_type"] == "2pt"), None)
        three_pt_row = next((r for r in rows if r["attempt_type"] == "3pt"), None)

        if not two_pt_row and not three_pt_row:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Win % going for 3",
                primary_sample_size=0,
                insufficient_data=True,
            )

        two_n = two_pt_row["total_possessions"] if two_pt_row else 0
        three_n = three_pt_row["total_possessions"] if three_pt_row else 0
        min_n = min(n for n in [two_n, three_n] if n > 0) if (two_n or three_n) else 0

        if min_n < INSUFFICIENT_DATA_THRESHOLD:
            return DecisionResult(
                decision_type=self.decision_type,
                recommended_action="insufficient data",
                confidence="insufficient",
                primary_stat=0.0,
                primary_stat_label="Win % going for 3",
                primary_sample_size=min_n,
                insufficient_data=True,
            )

        if down_by == "2":
            # Key decision: go for 3 (win outright or lose) vs go for 2 (tie & OT)
            three_make_pct = three_pt_row["make_pct"] if three_pt_row else 0.33
            two_make_pct = two_pt_row["make_pct"] if two_pt_row else 0.48

            p_win_go_3 = three_make_pct  # win outright if 3 goes in, lose if not
            p_win_go_2 = two_make_pct * OT_WIN_RATE  # tie then 50/50 OT

            if p_win_go_3 > p_win_go_2:
                recommended = "go for the 3"
                primary_win_pct = p_win_go_3
                primary_label = "Win % going for 3"
                primary_n = three_n
                comp_win_pct = p_win_go_2
                comp_label = "Win % going for 2 (tie + OT)"
                comp_n = two_n
            else:
                recommended = "play for 2 and OT"
                primary_win_pct = p_win_go_2
                primary_label = "Win % going for 2 (tie + OT)"
                primary_n = two_n
                comp_win_pct = p_win_go_3
                comp_label = "Win % going for 3"
                comp_n = three_n

            edge = round(abs(p_win_go_3 - p_win_go_2) * 100, 1)
            details = {
                "p_win_go_for_3": round(p_win_go_3 * 100, 1),
                "p_win_go_for_2": round(p_win_go_2 * 100, 1),
                "three_pt_make_pct": round(three_make_pct * 100, 1),
                "two_pt_make_pct": round(two_make_pct * 100, 1),
                "ot_win_rate": round(OT_WIN_RATE * 100, 1),
            }

        else:  # down by 3 — almost always go for 3
            three_win_pct = three_pt_row["win_pct"] if three_pt_row else None
            three_make_pct = three_pt_row["make_pct"] if three_pt_row else None

            # Down 3: going for 3 is essentially the only path to a win
            recommended = "go for the 3"
            primary_win_pct = three_win_pct if three_win_pct else (three_make_pct * OT_WIN_RATE if three_make_pct else 0.33)
            primary_label = "Win % going for 3"
            primary_n = three_n
            comp_win_pct = 0.02  # going for 2 down 3 is essentially conceding
            comp_label = "Win % going for 2 (still lose)"
            comp_n = two_n if two_n else 0
            edge = round(abs(primary_win_pct - comp_win_pct) * 100, 1)
            details = {
                "three_pt_make_pct": round(three_make_pct * 100, 1) if three_make_pct else None,
                "timeout_note": "Timeout to draw up a play increases 3PT success rate" if has_timeout else None,
            }

        low_sample = min_n < LOW_SAMPLE_THRESHOLD
        if edge >= 10:
            confidence = "low" if low_sample else "high"
        elif edge >= 5:
            confidence = "low" if low_sample else "moderate"
        else:
            confidence = "low"

        return DecisionResult(
            decision_type=self.decision_type,
            recommended_action=recommended,
            confidence=confidence,
            primary_stat=round(primary_win_pct * 100, 1),
            primary_stat_label=primary_label,
            primary_sample_size=primary_n,
            comparison_stat=round(comp_win_pct * 100, 1),
            comparison_stat_label=comp_label,
            comparison_sample_size=comp_n or None,
            edge_pct=edge,
            details=details,
            low_sample_warning=low_sample,
        )
