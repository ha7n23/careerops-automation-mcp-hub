import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyOperation,
)
from careerops_automation_mcp_hub.infrastructure.database.repositories import (
    SqlAlchemyIdempotencyRepository,
)


@pytest.mark.anyio
async def test_postgresql_idempotency_repository_replays_original_result(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 8, 19, 18, 0, tzinfo=UTC)

    async with postgres_session_factory() as session:
        repository = SqlAlchemyIdempotencyRepository(session)

        first = await repository.claim(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="workflow-123",
            request_fingerprint="a" * 64,
            created_at=now,
        )

        assert first.acquired is True

        await repository.complete(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="workflow-123",
            request_fingerprint="a" * 64,
            response_payload={
                "application_id": "APP-123",
            },
            completed_at=now,
        )

        await session.commit()

    async with postgres_session_factory() as session:
        repository = SqlAlchemyIdempotencyRepository(session)

        replay = await repository.claim(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="workflow-123",
            request_fingerprint="a" * 64,
            created_at=now,
        )

        assert replay.acquired is False
        assert replay.request_fingerprint == "a" * 64
        assert replay.response_payload == {"application_id": "APP-123"}


@pytest.mark.anyio
async def test_postgresql_idempotency_repository_exposes_existing_fingerprint(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 8, 19, 18, 0, tzinfo=UTC)

    async with postgres_session_factory() as session:
        repository = SqlAlchemyIdempotencyRepository(session)

        await repository.claim(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="workflow-123",
            request_fingerprint="a" * 64,
            created_at=now,
        )

        await repository.complete(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="workflow-123",
            request_fingerprint="a" * 64,
            response_payload={
                "application_id": "APP-123",
            },
            completed_at=now,
        )

        await session.commit()

    async with postgres_session_factory() as session:
        repository = SqlAlchemyIdempotencyRepository(session)

        claim = await repository.claim(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="workflow-123",
            request_fingerprint="b" * 64,
            created_at=now,
        )

        assert claim.acquired is False
        assert claim.request_fingerprint == "a" * 64


@pytest.mark.anyio
async def test_postgresql_concurrent_retry_waits_and_replays_completed_result(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 8, 19, 18, 0, tzinfo=UTC)

    async with postgres_session_factory() as first_session:
        first_repository = SqlAlchemyIdempotencyRepository(first_session)

        first = await first_repository.claim(
            user_id="USER-001",
            operation=IdempotencyOperation.CREATE_APPLICATION,
            idempotency_key="concurrent-123",
            request_fingerprint="a" * 64,
            created_at=now,
        )

        assert first.acquired is True

        async with postgres_session_factory() as second_session:
            second_repository = SqlAlchemyIdempotencyRepository(second_session)

            retry_task = asyncio.create_task(
                second_repository.claim(
                    user_id="USER-001",
                    operation=(IdempotencyOperation.CREATE_APPLICATION),
                    idempotency_key="concurrent-123",
                    request_fingerprint="a" * 64,
                    created_at=now,
                )
            )

            # Give the second transaction time to reach the
            # conflicting INSERT. It must wait for the first
            # transaction rather than acquire the same key.
            await asyncio.sleep(0.05)

            assert retry_task.done() is False

            await first_repository.complete(
                user_id="USER-001",
                operation=(IdempotencyOperation.CREATE_APPLICATION),
                idempotency_key="concurrent-123",
                request_fingerprint="a" * 64,
                response_payload={
                    "application_id": "APP-123",
                },
                completed_at=now,
            )

            await first_session.commit()

            replay = await asyncio.wait_for(
                retry_task,
                timeout=5.0,
            )

            assert replay.acquired is False
            assert replay.request_fingerprint == "a" * 64
            assert replay.response_payload == {"application_id": "APP-123"}
