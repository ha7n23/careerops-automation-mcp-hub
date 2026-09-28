from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server.auth.provider import TokenVerifier

from careerops_automation_mcp_hub.application.final_cv import (
    CVArtifactFormat,
    CVVersionMetadata,
    FinalCVGenerationRequest,
    FinalCVVersion,
)
from careerops_automation_mcp_hub.application.job_analysis import (
    JobAnalysisReviewDecision,
    JobAnalysisRun,
    JobAnalysisStartRequest,
)
from careerops_automation_mcp_hub.application.services.job_cv_gateway import (
    JobCVGatewayService,
)
from careerops_automation_mcp_hub.mcp.principal import Principal


def build_job_cv_router(
    *,
    service: JobCVGatewayService,
    token_verifier: TokenVerifier,
    required_scope: str,
) -> APIRouter:
    """Build authenticated job-analysis and final-CV routes for Module 3."""
    router = APIRouter()
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

    @router.post(
        "/api/v1/job-analysis",
        response_model=JobAnalysisRun,
        tags=["Job Analysis"],
    )
    async def start_job_analysis(
        request: JobAnalysisStartRequest,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> JobAnalysisRun:
        return await service.start_analysis(
            user_id=principal.user_id,
            request=request,
        )

    @router.get(
        "/api/v1/job-analysis/{thread_id}",
        response_model=JobAnalysisRun,
        tags=["Job Analysis"],
    )
    async def recover_job_analysis(
        thread_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> JobAnalysisRun:
        return await service.recover_analysis(
            user_id=principal.user_id,
            thread_id=thread_id,
        )

    @router.post(
        "/api/v1/job-analysis/{thread_id}/review",
        response_model=JobAnalysisRun,
        tags=["Job Analysis"],
    )
    async def review_job_analysis(
        thread_id: str,
        decision: JobAnalysisReviewDecision,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> JobAnalysisRun:
        return await service.review_analysis(
            user_id=principal.user_id,
            thread_id=thread_id,
            decision=decision,
        )

    @router.post(
        "/api/v1/cv-versions",
        response_model=FinalCVVersion,
        tags=["CV Versions"],
    )
    async def generate_final_cv(
        request: FinalCVGenerationRequest,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> FinalCVVersion:
        return await service.generate_final_cv(
            user_id=principal.user_id,
            request=request,
        )

    @router.get(
        "/api/v1/cv-versions/{cv_version_id}",
        response_model=CVVersionMetadata,
        tags=["CV Versions"],
    )
    async def get_final_cv(
        cv_version_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> CVVersionMetadata:
        return await service.get_final_cv(
            user_id=principal.user_id,
            cv_version_id=cv_version_id,
        )

    @router.get(
        "/api/v1/cv-versions/{cv_version_id}/artifacts/{artifact_format}",
        response_model=None,
        tags=["CV Versions"],
    )
    async def download_final_cv_artifact(
        cv_version_id: str,
        artifact_format: CVArtifactFormat,
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> Response:
        artifact = await service.download_final_cv_artifact(
            user_id=principal.user_id,
            cv_version_id=cv_version_id,
            artifact_format=artifact_format,
        )

        return Response(
            content=artifact.data,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": artifact.content_disposition,
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
