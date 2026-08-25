"""PostgreSQL integration tests for durable review submissions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewEdit,
    ApplicationReviewSubmission,
    ApplicationReviewSubmissionStatus,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)


@pytest.mark.anyio
async def test_application_review_submission_round_trip(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    application = JobApplication.create(
        user_id="USER-REVIEW-TEST",
        company_name="Example AI",
        role_title="Junior AI Engineer",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.applications.add(application)
        await unit_of_work.commit()

    preparation = ApplicationPreparation.create(
        application_id=application.application_id,
        user_id=application.user_id,
    )
    preparation.mark_starting()
    preparation.mark_awaiting_review(
        thread_id="THR-REVIEW-TEST",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.preparations.add(preparation)
        await unit_of_work.commit()

    submission = ApplicationReviewSubmission.create(
        preparation_id=preparation.preparation_id,
        application_id=application.application_id,
        user_id=application.user_id,
        thread_id="THR-REVIEW-TEST",
        idempotency_key="review-postgres-001",
        action=ApplicationReviewAction.EDIT,
        approved_proposal_ids=("CVP-001",),
        rejected_proposal_ids=("CVP-002",),
        edits=(
            ApplicationReviewEdit(
                proposal_id="CVP-003",
                edited_text="Improved evidence-grounded CV statement.",
            ),
        ),
        reviewer_comment="Keep this version concise.",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.review_submissions.add(submission)
        await unit_of_work.commit()

    async with unit_of_work_factory() as unit_of_work:
        stored = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id=application.user_id,
            idempotency_key="review-postgres-001",
        )

    assert stored is not None

    assert stored == submission

    assert stored.status is ApplicationReviewSubmissionStatus.PENDING
    assert stored.approved_proposal_ids == ("CVP-001",)
    assert stored.rejected_proposal_ids == ("CVP-002",)

    assert stored.edits == (
        ApplicationReviewEdit(
            proposal_id="CVP-003",
            edited_text="Improved evidence-grounded CV statement.",
        ),
    )

    submission.mark_submitting()

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.review_submissions.save(submission)
        await unit_of_work.commit()

    async with unit_of_work_factory() as unit_of_work:
        updated = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id=application.user_id,
            idempotency_key="review-postgres-001",
        )

        hidden = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id="USER-OTHER",
            idempotency_key="review-postgres-001",
        )

    assert updated is not None
    assert updated.status is ApplicationReviewSubmissionStatus.SUBMITTING

    assert hidden is None
