from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewSubmission,
    ApplicationReviewSubmissionStatus,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryApplicationReviewSubmissionRepository,
)


def _submission(
    *,
    user_id: str = "USER-001",
    key: str = "review-001",
) -> ApplicationReviewSubmission:
    return ApplicationReviewSubmission.create(
        preparation_id=uuid4(),
        application_id=uuid4(),
        user_id=user_id,
        thread_id="THR-001",
        idempotency_key=key,
        action=ApplicationReviewAction.APPROVE,
    )


@pytest.mark.anyio
async def test_review_repository_is_user_scoped() -> None:
    repository = InMemoryApplicationReviewSubmissionRepository()

    submission = _submission()
    await repository.add(submission)

    found = await repository.get_by_idempotency_key(
        user_id="USER-001",
        idempotency_key="review-001",
    )
    hidden = await repository.get_by_idempotency_key(
        user_id="USER-OTHER",
        idempotency_key="review-001",
    )

    assert found is submission
    assert hidden is None


@pytest.mark.anyio
async def test_review_repository_saves_execution_state() -> None:
    repository = InMemoryApplicationReviewSubmissionRepository()

    submission = _submission()
    await repository.add(submission)

    submission.mark_submitting()
    await repository.save(submission)

    stored = await repository.get_by_idempotency_key(
        user_id="USER-001",
        idempotency_key="review-001",
    )

    assert stored is not None
    assert stored.status is ApplicationReviewSubmissionStatus.SUBMITTING
