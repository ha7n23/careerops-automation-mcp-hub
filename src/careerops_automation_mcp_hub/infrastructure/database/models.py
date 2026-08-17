from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from careerops_automation_mcp_hub.domain.action_item import (
    ActionItemStatus,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.approval_request import (
    ApprovalActionType,
    ApprovalRequestStatus,
)
from careerops_automation_mcp_hub.infrastructure.database.base import Base


def _enum_check(
    column_name: str,
    enum_type: type[StrEnum],
) -> str:
    allowed_values = ", ".join(f"'{member.value}'" for member in enum_type)
    return f"{column_name} IN ({allowed_values})"


class JobApplicationRecord(Base):
    __tablename__ = "job_applications"

    __table_args__ = (
        CheckConstraint(
            _enum_check("status", ApplicationStatus),
            name="ck_job_applications_status",
        ),
        CheckConstraint(
            "btrim(user_id) <> ''",
            name="ck_job_applications_user_id_not_blank",
        ),
        CheckConstraint(
            "btrim(company_name) <> ''",
            name="ck_job_applications_company_name_not_blank",
        ),
        CheckConstraint(
            "btrim(role_title) <> ''",
            name="ck_job_applications_role_title_not_blank",
        ),
        Index(
            "ix_job_applications_user_status",
            "user_id",
            "status",
        ),
    )

    application_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class ApplicationEventRecord(Base):
    __tablename__ = "application_events"

    __table_args__ = (
        CheckConstraint(
            _enum_check("event_type", ApplicationEventType),
            name="ck_application_events_event_type",
        ),
        CheckConstraint(
            "btrim(user_id) <> ''",
            name="ck_application_events_user_id_not_blank",
        ),
        CheckConstraint(
            "btrim(actor_id) <> ''",
            name="ck_application_events_actor_id_not_blank",
        ),
        Index(
            "ix_application_events_application_occurred",
            "application_id",
            "occurred_at",
        ),
    )

    event_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    application_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("job_applications.application_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attributes: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
    )


class ActionItemRecord(Base):
    __tablename__ = "action_items"

    __table_args__ = (
        CheckConstraint(
            _enum_check("action_type", ActionItemType),
            name="ck_action_items_action_type",
        ),
        CheckConstraint(
            _enum_check("status", ActionItemStatus),
            name="ck_action_items_status",
        ),
        CheckConstraint(
            "btrim(user_id) <> ''",
            name="ck_action_items_user_id_not_blank",
        ),
        CheckConstraint(
            "btrim(description) <> ''",
            name="ck_action_items_description_not_blank",
        ),
        Index(
            "ix_action_items_user_status_due",
            "user_id",
            "status",
            "due_at",
        ),
    )

    action_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    application_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("job_applications.application_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"

    __table_args__ = (
        CheckConstraint(
            _enum_check("action_type", ApprovalActionType),
            name="ck_approval_requests_action_type",
        ),
        CheckConstraint(
            _enum_check("status", ApprovalRequestStatus),
            name="ck_approval_requests_status",
        ),
        CheckConstraint(
            "btrim(user_id) <> ''",
            name="ck_approval_requests_user_id_not_blank",
        ),
        CheckConstraint(
            "btrim(requested_by) <> ''",
            name="ck_approval_requests_requested_by_not_blank",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="ck_approval_requests_expiry_after_creation",
        ),
        Index(
            "ix_approval_requests_user_status",
            "user_id",
            "status",
        ),
    )

    approval_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
    )
    application_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("job_applications.application_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    requested_by: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    payload: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decided_by: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
