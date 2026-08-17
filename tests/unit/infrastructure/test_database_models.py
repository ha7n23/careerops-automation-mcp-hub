from sqlalchemy import CheckConstraint

from careerops_automation_mcp_hub.infrastructure.database.base import Base
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ActionItemRecord,
    ApplicationEventRecord,
    ApprovalRequestRecord,
    JobApplicationRecord,
)


def test_expected_database_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "action_items",
        "application_events",
        "approval_requests",
        "job_applications",
    }


def test_job_application_table_has_expected_primary_key() -> None:
    primary_key_columns = {
        column.name for column in JobApplicationRecord.__table__.primary_key
    }

    assert primary_key_columns == {"application_id"}


def test_application_event_references_job_application() -> None:
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in ApplicationEventRecord.__table__.foreign_keys
    }

    assert "job_applications.application_id" in foreign_keys


def test_action_item_references_job_application() -> None:
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in ActionItemRecord.__table__.foreign_keys
    }

    assert "job_applications.application_id" in foreign_keys


def test_approval_request_references_job_application() -> None:
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in ApprovalRequestRecord.__table__.foreign_keys
    }

    assert "job_applications.application_id" in foreign_keys


def test_domain_enum_check_constraints_are_present() -> None:
    constraint_names = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_job_applications_status",
        "ck_application_events_event_type",
        "ck_action_items_action_type",
        "ck_action_items_status",
        "ck_approval_requests_action_type",
        "ck_approval_requests_status",
    }.issubset(constraint_names)
