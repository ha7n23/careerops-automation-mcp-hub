from typing import Any, cast

from fastapi import FastAPI
from mcp.server.auth.provider import AccessToken

from careerops_automation_mcp_hub.api.evidence import build_evidence_router
from careerops_automation_mcp_hub.api.job_cv import build_job_cv_router


class _TokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        return None


EXPECTED_MODULE_1_GATEWAY_OPERATIONS = {
    ("GET", "/api/v1/cv-documents"),
    ("POST", "/api/v1/cv-documents"),
    ("POST", "/api/v1/cv-documents/text"),
    ("POST", "/api/v1/cv-documents/{document_id}/evidence-review"),
    ("GET", "/api/v1/cv-evidence-reviews"),
    ("GET", "/api/v1/cv-evidence-reviews/{review_run_id}"),
    ("POST", "/api/v1/cv-evidence-reviews/{review_run_id}/review"),
    ("GET", "/api/v1/evidence"),
    ("GET", "/api/v1/evidence/{evidence_id}"),
    ("PATCH", "/api/v1/evidence/{evidence_id}"),
    ("POST", "/api/v1/evidence/{evidence_id}/archive"),
    ("POST", "/api/v1/evidence/{evidence_id}/restore"),
    ("POST", "/api/v1/job-analysis"),
    ("GET", "/api/v1/job-analysis/{thread_id}"),
    ("POST", "/api/v1/job-analysis/{thread_id}/review"),
    ("POST", "/api/v1/cv-versions"),
    ("GET", "/api/v1/cv-versions/{cv_version_id}"),
    (
        "GET",
        "/api/v1/cv-versions/{cv_version_id}/artifacts/{artifact_format}",
    ),
}


def test_module1_gateway_openapi_contract_is_frozen_and_authenticated() -> None:
    verifier = cast(Any, _TokenVerifier())
    app = FastAPI()
    app.include_router(
        build_evidence_router(
            service=cast(Any, object()),
            registry_service=cast(Any, object()),
            token_verifier=verifier,
            required_scope="careerops:applications",
        )
    )
    app.include_router(
        build_job_cv_router(
            service=cast(Any, object()),
            token_verifier=verifier,
            required_scope="careerops:applications",
        )
    )

    schema = app.openapi()
    operations = {
        (method.upper(), path)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method.upper() in {"GET", "POST", "PATCH"}
    }

    assert operations == EXPECTED_MODULE_1_GATEWAY_OPERATIONS
    assert schema["components"]["securitySchemes"] == {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
        }
    }

    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method.upper() in {"GET", "POST", "PATCH"}:
                assert operation["security"] == [{"HTTPBearer": []}]
