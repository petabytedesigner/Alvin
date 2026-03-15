from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

from contracts.reconciliation import ReconciliationMismatch, ReconciliationRepair, ReconciliationRun


@dataclass(slots=True)
class ReconciliationInputs:
    intents: list[Dict[str, Any]]
    execution_results: list[Dict[str, Any]]
    transitions: list[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intents": list(self.intents),
            "execution_results": list(self.execution_results),
            "transitions": list(self.transitions),
        }


class ReconciliationEngine:
    TERMINAL_RESULT_STATUSES = {"filled", "cancelled", "rejected", "expired", "transport_error"}
    SUCCESS_STATES = {"submitted_to_broker", "acked", "filled", "position_open", "position_closed"}

    def run(
        self,
        *,
        ts_utc: str,
        intents: Iterable[Dict[str, Any]],
        execution_results: Iterable[Dict[str, Any]],
        transitions: Iterable[Dict[str, Any]],
    ) -> ReconciliationRun:
        inputs = ReconciliationInputs(
            intents=[dict(item) for item in intents],
            execution_results=[dict(item) for item in execution_results],
            transitions=[dict(item) for item in transitions],
        )

        execution_by_intent = self._index_latest(inputs.execution_results, "intent_id")
        transitions_by_intent = self._group_by(inputs.transitions, "intent_id")

        mismatches: list[Dict[str, Any]] = []
        repairs: list[Dict[str, Any]] = []

        for intent in inputs.intents:
            intent_id = intent.get("intent_id")
            if not intent_id:
                mismatches.append(
                    ReconciliationMismatch(
                        category="intent_record_invalid",
                        severity="high",
                        intent_id=None,
                        expected={"intent_id_present": True},
                        actual={"intent": intent},
                        reasons=["intent_id_missing"],
                    ).to_dict()
                )
                continue

            current_state = str(intent.get("state") or "")
            execution_result = execution_by_intent.get(intent_id)
            intent_transitions = transitions_by_intent.get(intent_id, [])

            if current_state == "intent_created" and execution_result is None:
                continue

            if current_state == "submit_started" and execution_result is None:
                mismatches.append(
                    ReconciliationMismatch(
                        category="submit_without_execution_result",
                        severity="medium",
                        intent_id=intent_id,
                        expected={"execution_result_present": True},
                        actual={"execution_result_present": False, "state": current_state},
                        reasons=["submit_started_without_execution_result"],
                    ).to_dict()
                )
                repairs.append(
                    ReconciliationRepair(
                        action="schedule_retry_review",
                        status="proposed",
                        intent_id=intent_id,
                        details={"state": current_state},
                    ).to_dict()
                )
                continue

            if execution_result is not None:
                submitted = bool(execution_result.get("submitted"))
                result_status = str(execution_result.get("status") or "")

                if submitted and current_state not in self.SUCCESS_STATES:
                    mismatches.append(
                        ReconciliationMismatch(
                            category="submitted_result_state_mismatch",
                            severity="high",
                            intent_id=intent_id,
                            expected={"state_in": sorted(self.SUCCESS_STATES)},
                            actual={"state": current_state, "execution_status": result_status},
                            reasons=["execution_submitted_but_intent_state_not_advanced"],
                        ).to_dict()
                    )
                    repairs.append(
                        ReconciliationRepair(
                            action="review_intent_state",
                            status="proposed",
                            intent_id=intent_id,
                            details={"execution_status": result_status, "state": current_state},
                        ).to_dict()
                    )

                if not submitted and current_state in {"submitted_to_broker", "acked", "filled"}:
                    mismatches.append(
                        ReconciliationMismatch(
                            category="non_submitted_result_state_mismatch",
                            severity="high",
                            intent_id=intent_id,
                            expected={"submitted": True},
                            actual={"submitted": submitted, "state": current_state, "execution_status": result_status},
                            reasons=["intent_advanced_without_successful_submission"],
                        ).to_dict()
                    )

                if result_status in self.TERMINAL_RESULT_STATUSES and not intent_transitions:
                    mismatches.append(
                        ReconciliationMismatch(
                            category="execution_terminal_without_transition",
                            severity="medium",
                            intent_id=intent_id,
                            expected={"transition_present": True},
                            actual={"transition_present": False, "execution_status": result_status},
                            reasons=["terminal_execution_status_without_transition_record"],
                        ).to_dict()
                    )
                    repairs.append(
                        ReconciliationRepair(
                            action="backfill_transition",
                            status="proposed",
                            intent_id=intent_id,
                            details={"execution_status": result_status},
                        ).to_dict()
                    )

            if intent_transitions:
                last_transition = intent_transitions[-1]
                transition_next_state = str(last_transition.get("next_state") or "")
                if transition_next_state and current_state and transition_next_state != current_state:
                    mismatches.append(
                        ReconciliationMismatch(
                            category="transition_current_state_mismatch",
                            severity="medium",
                            intent_id=intent_id,
                            expected={"state": transition_next_state},
                            actual={"state": current_state},
                            reasons=["latest_transition_next_state_differs_from_current_intent_state"],
                        ).to_dict()
                    )
                    repairs.append(
                        ReconciliationRepair(
                            action="refresh_intent_snapshot",
                            status="proposed",
                            intent_id=intent_id,
                            details={
                                "transition_next_state": transition_next_state,
                                "current_state": current_state,
                            },
                        ).to_dict()
                    )

        status = "clean" if not mismatches else "mismatches_found"
        return ReconciliationRun(
            ts_utc=ts_utc,
            status=status,
            mismatches=mismatches,
            repairs=repairs,
        )

    def _index_latest(self, rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
        indexed: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            row_key = row.get(key)
            if not row_key:
                continue
            indexed[str(row_key)] = row
        return indexed

    def _group_by(self, rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, list[Dict[str, Any]]]:
        grouped: Dict[str, list[Dict[str, Any]]] = {}
        for row in rows:
            row_key = row.get(key)
            if not row_key:
                continue
            grouped.setdefault(str(row_key), []).append(row)
        return grouped
