from __future__ import annotations

import argparse
import importlib
import os
from dataclasses import dataclass
from itertools import count
from typing import Any

import uvicorn

_CONTRACT_SERVICE_KEY = "c" * 32
_PROPOSAL_ID = "CVP-CONTRACT-001"


@dataclass(frozen=True, slots=True)
class _Execution:
    """Minimal execution object consumed by Module 1's real API router."""

    thread_id: str
    state: dict[str, object]
    interrupt_payload: dict[str, object] | None

    @property
    def awaiting_review(self) -> bool:
        return self.interrupt_payload is not None


class _ContractJobAnalysisService:
    """Deterministic replacement for only Module 1's AI workflow."""

    def __init__(
        self,
        thread_unavailable_error: type[Exception],
    ) -> None:
        self._thread_unavailable_error = thread_unavailable_error
        self._thread_counter = count(1)
        self._threads: dict[str, tuple[str, str]] = {}

    def analyse(
        self,
        *,
        job_id: str,
        user_id: str,
        job_description: str,
    ) -> _Execution:
        thread_id = f"THR-CONTRACT-{next(self._thread_counter):03d}"

        self._threads[thread_id] = (
            user_id,
            job_id,
        )

        return _Execution(
            thread_id=thread_id,
            state=_build_state(
                job_id=job_id,
                user_id=user_id,
                job_description=job_description,
                status="awaiting_review",
            ),
            interrupt_payload=_build_review_payload(),
        )

    def resume_review(
        self,
        *,
        thread_id: str,
        user_id: str,
        decision: object,
    ) -> _Execution:
        stored_thread = self._threads.get(thread_id)

        if stored_thread is None or stored_thread[0] != user_id:
            raise self._thread_unavailable_error(
                "The requested review thread is unavailable."
            )

        action = getattr(
            getattr(decision, "action", None),
            "value",
            None,
        )

        if action != "approve":
            raise ValueError("The contract fixture supports approval only.")

        job_id = stored_thread[1]

        state = _build_state(
            job_id=job_id,
            user_id=user_id,
            job_description="Contract fixture.",
            status="completed",
        )

        state["review_status"] = "approved"
        state["final_cv_proposals"] = [_build_proposal()]

        return _Execution(
            thread_id=thread_id,
            state=state,
            interrupt_payload=None,
        )


def _build_requirement() -> dict[str, object]:
    return {
        "requirement_id": "REQ-CONTRACT-001",
        "name": "Python",
        "category": "essential",
        "evidence_expected": ("Evidence of professional Python engineering."),
        "importance_score": 5,
        "source_text": ("Strong Python engineering experience is required."),
    }


def _build_evidence_match() -> dict[str, object]:
    return {
        "requirement_id": "REQ-CONTRACT-001",
        "match_strength": "strong",
        "direct_evidence_ids": ["EVD-CONTRACT-001"],
        "related_evidence_ids": [],
        "explanation": ("Approved evidence supports Python engineering."),
        "gap": False,
    }


def _build_proposal() -> dict[str, object]:
    return {
        "proposal_id": _PROPOSAL_ID,
        "section": "projects",
        "target_entry_id": None,
        "current_text": None,
        "proposed_text": ("Built a tested Python API using FastAPI."),
        "requirement_ids": ["REQ-CONTRACT-001"],
        "supporting_evidence_ids": ["EVD-CONTRACT-001"],
        "confidence_score": 0.95,
        "warnings": [],
        "requires_human_approval": True,
    }


def _build_state(
    *,
    job_id: str,
    user_id: str,
    job_description: str,
    status: str,
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "user_id": user_id,
        "job_description": job_description,
        "role_title": "Junior AI Engineer",
        "requirements": [_build_requirement()],
        "evidence_matches": [_build_evidence_match()],
        "fit_score": 92.5,
        "cv_proposals": [_build_proposal()],
        "claim_verification_reports": [],
        "reviewable_proposal_ids": [_PROPOSAL_ID],
        "blocked_proposal_ids": [],
        "audit_events": [
            {
                "node": "contract_fixture",
                "event": "contract_fixture_ready",
            }
        ],
        "status": status,
    }


def _build_review_payload() -> dict[str, object]:
    return {
        "type": "cv_proposal_review",
        "proposals": [_build_proposal()],
        "verification_reports": [],
        "allowed_actions": [
            "approve",
            "edit",
            "regenerate",
            "reject",
        ],
    }


def _configure_module1_environment() -> None:
    """Force deterministic, authenticated test configuration."""
    os.environ["CAREEROPS_ENVIRONMENT"] = "test"
    os.environ["CAREEROPS_DEBUG"] = "false"
    os.environ["CAREEROPS_AUTH_MODE"] = "service_key"
    os.environ["CAREEROPS_SERVICE_API_KEY"] = _CONTRACT_SERVICE_KEY
    os.environ["CAREEROPS_TRUSTED_HOSTS"] = '["127.0.0.1","localhost"]'


def _load_module1_app() -> Any:
    """Load Module 1 dynamically without creating a Module 2 dependency."""
    main_module = importlib.import_module("careerops_agent_engine.main")
    dependencies_module = importlib.import_module(
        "careerops_agent_engine.api.dependencies"
    )
    exceptions_module = importlib.import_module(
        "careerops_agent_engine.application.exceptions"
    )

    application = main_module.app

    dependency = dependencies_module.get_job_analysis_service

    thread_unavailable_error = exceptions_module.JobAnalysisThreadUnavailableError

    service = _ContractJobAnalysisService(thread_unavailable_error)

    application.dependency_overrides[dependency] = lambda: service

    return application


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8011,
    )

    args = parser.parse_args()

    _configure_module1_environment()

    application = _load_module1_app()

    uvicorn.run(
        application,
        host=args.host,
        port=args.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
