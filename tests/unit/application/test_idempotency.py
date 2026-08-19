import pytest

from careerops_automation_mcp_hub.application.idempotency import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    build_request_fingerprint,
    normalize_idempotency_key,
)


def test_idempotency_key_is_normalized() -> None:
    assert normalize_idempotency_key("  workflow-run-123  ") == "workflow-run-123"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
    ],
)
def test_blank_idempotency_key_is_rejected(
    value: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="must not be blank",
    ):
        normalize_idempotency_key(value)


def test_overlong_idempotency_key_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="must not exceed",
    ):
        normalize_idempotency_key("x" * (MAX_IDEMPOTENCY_KEY_LENGTH + 1))


def test_request_fingerprint_is_order_independent() -> None:
    first = build_request_fingerprint(
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        }
    )

    second = build_request_fingerprint(
        {
            "role_title": "Junior AI Engineer",
            "company_name": "Monzo",
        }
    )

    assert first == second
    assert len(first) == 64


def test_request_fingerprint_changes_when_request_changes() -> None:
    first = build_request_fingerprint(
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        }
    )

    second = build_request_fingerprint(
        {
            "company_name": "Monzo",
            "role_title": "AI Engineer",
        }
    )

    assert first != second
