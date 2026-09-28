from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server.auth.provider import TokenVerifier
from pydantic import BaseModel, ConfigDict, Field

from careerops_automation_mcp_hub.application.evidence import (
    ApprovedEvidence,
    EvidenceCategory,
    EvidenceDocument,
    EvidenceDocumentHistory,
    EvidenceLifecycleStatus,
    EvidenceRegistryEdit,
    EvidenceRegistryPage,
    EvidenceReviewDecision,
    EvidenceReviewHistory,
    EvidenceReviewRun,
)
from careerops_automation_mcp_hub.application.services.evidence_registry import (
    EvidenceRegistryService,
)
from careerops_automation_mcp_hub.application.services.evidence_workflow import (
    EvidenceWorkflowService,
)
from careerops_automation_mcp_hub.mcp.principal import Principal

DEFAULT_MAX_EVIDENCE_UPLOAD_BYTES = 5 * 1024 * 1024


def build_evidence_router(
    *,
    service: EvidenceWorkflowService,
    registry_service: EvidenceRegistryService,
    token_verifier: TokenVerifier,
    required_scope: str,
    max_upload_bytes: int = DEFAULT_MAX_EVIDENCE_UPLOAD_BYTES,
) -> APIRouter:
    """Build the authenticated HTTP evidence gateway used by Module 3."""
    router = APIRouter(tags=["Evidence Workflow"])
    registry_router = APIRouter(tags=["Evidence Registry"])
    bearer = HTTPBearer(auto_error=False)

    async def get_principal(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer),
        ],
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = await token_verifier.verify_token(credentials.credentials)

        if access_token is None or access_token.subject is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The access token is invalid.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if required_scope not in access_token.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The access token lacks the required CareerOps scope.",
            )

        return Principal(
            user_id=access_token.subject,
            actor_id=access_token.client_id,
        )

    @router.get(
        "/api/v1/cv-documents",
        response_model=EvidenceDocumentHistory,
    )
    async def list_documents(
        principal: Annotated[Principal, Depends(get_principal)],
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> EvidenceDocumentHistory:
        return await service.list_documents(
            user_id=principal.user_id,
            limit=limit,
        )

    @router.post(
        "/api/v1/cv-documents",
        response_model=EvidenceDocument,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_document(
        principal: Annotated[Principal, Depends(get_principal)],
        file: Annotated[UploadFile, File()],
    ) -> EvidenceDocument:
        try:
            data = await file.read(max_upload_bytes + 1)

            if len(data) > max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="The evidence document exceeds the upload limit.",
                )

            return await service.upload_document(
                user_id=principal.user_id,
                filename=file.filename or "",
                media_type=file.content_type or "application/octet-stream",
                data=data,
            )
        finally:
            await file.close()

    @router.post(
        "/api/v1/cv-documents/text",
        response_model=EvidenceDocument,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_text_source(
        request: TextEvidenceSourceRequest,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> EvidenceDocument:
        return await service.create_text_source(
            user_id=principal.user_id,
            title=request.title,
            content=request.content,
        )

    @router.post(
        "/api/v1/cv-documents/{document_id}/evidence-review",
        response_model=EvidenceReviewRun,
    )
    async def start_review(
        document_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> EvidenceReviewRun:
        return await service.start_review(
            user_id=principal.user_id,
            document_id=document_id,
        )

    @router.get(
        "/api/v1/cv-evidence-reviews",
        response_model=EvidenceReviewHistory,
    )
    async def list_reviews(
        principal: Annotated[Principal, Depends(get_principal)],
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> EvidenceReviewHistory:
        return await service.list_reviews(
            user_id=principal.user_id,
            limit=limit,
        )

    @router.get(
        "/api/v1/cv-evidence-reviews/{review_run_id}",
        response_model=EvidenceReviewRun,
    )
    async def get_review(
        review_run_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> EvidenceReviewRun:
        return await service.get_review(
            user_id=principal.user_id,
            review_run_id=review_run_id,
        )

    @router.post(
        "/api/v1/cv-evidence-reviews/{review_run_id}/review",
        response_model=EvidenceReviewRun,
    )
    async def submit_review(
        review_run_id: str,
        decision: EvidenceReviewDecision,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> EvidenceReviewRun:
        return await service.submit_review(
            user_id=principal.user_id,
            review_run_id=review_run_id,
            decision=decision,
        )

    @registry_router.get(
        "/api/v1/evidence",
        response_model=EvidenceRegistryPage,
    )
    async def query_registry(
        principal: Annotated[Principal, Depends(get_principal)],
        query: Annotated[
            str | None,
            Query(alias="q", min_length=1, max_length=200),
        ] = None,
        category: Annotated[EvidenceCategory | None, Query()] = None,
        lifecycle_status: Annotated[
            EvidenceLifecycleStatus,
            Query(),
        ] = EvidenceLifecycleStatus.ACTIVE,
        offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> EvidenceRegistryPage:
        return await registry_service.query(
            user_id=principal.user_id,
            query=query,
            category=category,
            lifecycle_status=lifecycle_status,
            offset=offset,
            limit=limit,
        )

    @registry_router.get(
        "/api/v1/evidence/{evidence_id}",
        response_model=ApprovedEvidence,
    )
    async def get_evidence(
        evidence_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> ApprovedEvidence:
        return await registry_service.get(
            user_id=principal.user_id,
            evidence_id=evidence_id,
        )

    @registry_router.patch(
        "/api/v1/evidence/{evidence_id}",
        response_model=ApprovedEvidence,
    )
    async def edit_evidence(
        evidence_id: str,
        edit: EvidenceRegistryEdit,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> ApprovedEvidence:
        return await registry_service.edit(
            user_id=principal.user_id,
            evidence_id=evidence_id,
            edit=edit,
        )

    @registry_router.post(
        "/api/v1/evidence/{evidence_id}/archive",
        response_model=ApprovedEvidence,
    )
    async def archive_evidence(
        evidence_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> ApprovedEvidence:
        return await registry_service.archive(
            user_id=principal.user_id,
            evidence_id=evidence_id,
        )

    @registry_router.post(
        "/api/v1/evidence/{evidence_id}/restore",
        response_model=ApprovedEvidence,
    )
    async def restore_evidence(
        evidence_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> ApprovedEvidence:
        return await registry_service.restore(
            user_id=principal.user_id,
            evidence_id=evidence_id,
        )

    router.include_router(registry_router)
    return router


class TextEvidenceSourceRequest(BaseModel):
    """Strict pasted-text request accepted by the Module 2 gateway."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1, max_length=30_000)
