"""Opt-in live proof of the complete Module 2 -> Module 1 gateway."""

import asyncio
import os
from collections.abc import Awaitable
from uuid import uuid4

import httpx

from careerops_automation_mcp_hub.application.errors import (
    AgentEngineNotFoundError,
)
from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDuplicateAction,
    EvidenceDuplicateResolution,
    EvidenceLifecycleStatus,
    EvidenceReviewDecision,
)
from careerops_automation_mcp_hub.application.final_cv import (
    CVArtifactFormat,
    CVArtifactVerificationStatus,
    FinalCVGenerationRequest,
)
from careerops_automation_mcp_hub.application.job_analysis import (
    JobAnalysisAwaitingReview,
    JobAnalysisCompleted,
    JobAnalysisReviewDecision,
    JobAnalysisStartRequest,
    JobReviewAction,
)
from careerops_automation_mcp_hub.application.services.evidence_registry import (
    EvidenceRegistryService,
)
from careerops_automation_mcp_hub.application.services.evidence_workflow import (
    EvidenceWorkflowService,
)
from careerops_automation_mcp_hub.application.services.job_cv_gateway import (
    JobCVGatewayService,
)
from careerops_automation_mcp_hub.core.config import get_settings
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)

_DEFAULT_JOB_DESCRIPTION = (
    "AI Engineer requiring hands-on Python software engineering, FastAPI API "
    "development, automated testing, and production AI workflow experience."
)
_DEFAULT_EVIDENCE_TEXT = "Skills\nPython\nFastAPI\npytest"


async def _require_cross_user_not_found(
    operation: Awaitable[object],
    *,
    label: str,
) -> None:
    try:
        await operation
    except AgentEngineNotFoundError:
        print(f"   isolation: {label} blocked")
        return

    raise RuntimeError(f"Cross-user {label} was not blocked.")


async def main() -> None:
    settings = get_settings()
    suffix = uuid4().hex[:10].upper()
    user_id = f"USER-M2-E2E-{suffix}"
    other_user_id = f"USER-M2-OTHER-{suffix}"
    job_description = os.getenv(
        "CAREEROPS_LIVE_JOB_DESCRIPTION",
        _DEFAULT_JOB_DESCRIPTION,
    ).strip()
    evidence_text = os.getenv(
        "CAREEROPS_LIVE_EVIDENCE_TEXT",
        _DEFAULT_EVIDENCE_TEXT,
    ).strip()
    if not evidence_text:
        raise RuntimeError("CAREEROPS_LIVE_EVIDENCE_TEXT must not be blank.")

    timeout = httpx.Timeout(
        connect=settings.agent_engine_connect_timeout_seconds,
        read=settings.agent_engine_read_timeout_seconds,
        write=settings.agent_engine_write_timeout_seconds,
        pool=settings.agent_engine_pool_timeout_seconds,
    )

    async with httpx.AsyncClient(
        base_url=str(settings.agent_engine_base_url),
        timeout=timeout,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key=settings.agent_engine_service_key.get_secret_value(),
        )
        workflow = EvidenceWorkflowService(client)
        registry = EvidenceRegistryService(client)
        job_cv = JobCVGatewayService(client)

        print("=== CareerOps Module 2 -> Module 1 final live proof ===")
        print(f"user_id: {user_id}")
        print("source: deterministic pasted-text evidence")

        document = await workflow.create_text_source(
            user_id=user_id,
            title="Module 2 live proof skills",
            content=evidence_text,
        )
        pending_review = await workflow.start_review(
            user_id=user_id,
            document_id=document.document_id,
        )
        if not pending_review.proposals:
            raise RuntimeError("Evidence extraction produced no review proposals.")

        resolutions = [
            EvidenceDuplicateResolution(
                proposal_id=finding.proposal_id,
                scope=finding.scope,
                action=EvidenceDuplicateAction.ACCEPT_SEPARATE,
                matching_proposal_id=finding.matching_proposal_id,
                matching_evidence_id=finding.matching_evidence_id,
            )
            for finding in pending_review.overlap_findings
        ]
        completed_review = await workflow.submit_review(
            user_id=user_id,
            review_run_id=pending_review.review_run_id,
            decision=EvidenceReviewDecision(
                approved_proposal_ids=[
                    proposal.proposal_id for proposal in pending_review.proposals
                ],
                duplicate_resolutions=resolutions,
                reviewer_comment="Module 2 final live proof approval.",
            ),
        )
        if completed_review.review_result is None:
            raise RuntimeError("Evidence review did not persist a result.")

        evidence_ids = [
            item.evidence_id
            for item in completed_review.review_result.approved_evidence
        ]
        if not evidence_ids:
            raise RuntimeError("Evidence review approved no registry records.")
        print(f"1. ingestion/review: {len(evidence_ids)} evidence record(s) approved")

        active_page = await registry.query(user_id=user_id)
        if not set(evidence_ids).issubset(
            {item.evidence_id for item in active_page.items}
        ):
            raise RuntimeError("Approved evidence is missing from the registry.")

        for evidence_id in evidence_ids:
            await registry.archive(user_id=user_id, evidence_id=evidence_id)

        archived_default_page = await registry.query(user_id=user_id)
        if any(
            item.evidence_id in evidence_ids for item in archived_default_page.items
        ):
            raise RuntimeError("Archived evidence leaked into the active registry.")

        archived_page = await registry.query(
            user_id=user_id,
            lifecycle_status=EvidenceLifecycleStatus.ARCHIVED,
        )
        if not set(evidence_ids).issubset(
            {item.evidence_id for item in archived_page.items}
        ):
            raise RuntimeError("Archived evidence is missing from lifecycle history.")

        archived_analysis = await job_cv.start_analysis(
            user_id=user_id,
            request=JobAnalysisStartRequest(
                job_id=f"JOB-M2-ARCHIVED-{suffix}",
                job_description=job_description,
            ),
        )
        if any(
            match.direct_evidence_ids or match.related_evidence_ids
            for match in archived_analysis.evidence_matches
        ):
            raise RuntimeError("Archived evidence was used in job analysis.")
        print("2. archive: excluded from registry defaults and job grounding")

        for evidence_id in evidence_ids:
            await registry.restore(user_id=user_id, evidence_id=evidence_id)

        restored_page = await registry.query(user_id=user_id)
        if not set(evidence_ids).issubset(
            {item.evidence_id for item in restored_page.items}
        ):
            raise RuntimeError("Restored evidence did not return to the registry.")

        restored_analysis = await job_cv.start_analysis(
            user_id=user_id,
            request=JobAnalysisStartRequest(
                job_id=f"JOB-M2-RESTORED-{suffix}",
                job_description=job_description,
            ),
        )
        grounded_ids = {
            evidence_id
            for match in restored_analysis.evidence_matches
            for evidence_id in (match.direct_evidence_ids + match.related_evidence_ids)
        }
        if not grounded_ids.intersection(evidence_ids):
            raise RuntimeError("Restored evidence was not used in job analysis.")
        if restored_analysis.fit_score <= archived_analysis.fit_score:
            raise RuntimeError("Restored evidence did not improve the fit score.")
        print("3. restore: evidence returned to job grounding")

        if isinstance(restored_analysis, JobAnalysisAwaitingReview):
            if not restored_analysis.reviewable_proposal_ids:
                raise RuntimeError(
                    "Awaiting-review analysis produced no reviewable CV proposal."
                )

            completed_analysis = await job_cv.review_analysis(
                user_id=user_id,
                thread_id=restored_analysis.thread_id,
                decision=JobAnalysisReviewDecision(
                    action=JobReviewAction.APPROVE,
                    approved_proposal_ids=restored_analysis.reviewable_proposal_ids,
                    reviewer_comment="Module 2 final live proof approval.",
                ),
            )
            if not isinstance(completed_analysis, JobAnalysisCompleted):
                raise TypeError("Job analysis did not complete after review.")
            print("   review: reviewable proposals approved")
            version = await job_cv.generate_final_cv(
                user_id=user_id,
                request=FinalCVGenerationRequest(
                    thread_id=completed_analysis.thread_id,
                    source_document_id=document.document_id,
                ),
            )
            artifact_formats = {
                artifact.artifact_format
                for artifact in version.artifacts
                if artifact.verification_status is CVArtifactVerificationStatus.VERIFIED
            }
            if artifact_formats != {CVArtifactFormat.DOCX, CVArtifactFormat.PDF}:
                raise RuntimeError("Final CV did not produce verified DOCX and PDF.")

            replay = await job_cv.generate_final_cv(
                user_id=user_id,
                request=FinalCVGenerationRequest(
                    thread_id=completed_analysis.thread_id,
                    source_document_id=document.document_id,
                ),
            )
            if (
                replay.cv_version_id != version.cv_version_id
                or not replay.reused_existing_version
            ):
                raise RuntimeError("Final-CV generation retry was not safely reused.")

            docx = await job_cv.download_final_cv_artifact(
                user_id=user_id,
                cv_version_id=version.cv_version_id,
                artifact_format=CVArtifactFormat.DOCX,
            )
            pdf = await job_cv.download_final_cv_artifact(
                user_id=user_id,
                cv_version_id=version.cv_version_id,
                artifact_format=CVArtifactFormat.PDF,
            )
            if not docx.data.startswith(b"PK") or not pdf.data.startswith(b"%PDF"):
                raise RuntimeError(
                    "Downloaded final-CV artifacts failed signature checks."
                )
            print("4. final CV: verified DOCX/PDF generated, reused, and downloaded")
            cv_version_id: str | None = version.cv_version_id
        else:
            print("4. safety: unsupported CV proposals blocked; final CV not generated")
            cv_version_id = None

        await _require_cross_user_not_found(
            registry.get(user_id=other_user_id, evidence_id=evidence_ids[0]),
            label="evidence retrieval",
        )
        await _require_cross_user_not_found(
            job_cv.recover_analysis(
                user_id=other_user_id,
                thread_id=restored_analysis.thread_id,
            ),
            label="job-analysis recovery",
        )
        if cv_version_id is not None:
            await _require_cross_user_not_found(
                job_cv.get_final_cv(
                    user_id=other_user_id,
                    cv_version_id=cv_version_id,
                ),
                label="final-CV retrieval",
            )

        print("MODULE 2 -> MODULE 1 FINAL LIVE PROOF PASSED")


if __name__ == "__main__":
    asyncio.run(main())
