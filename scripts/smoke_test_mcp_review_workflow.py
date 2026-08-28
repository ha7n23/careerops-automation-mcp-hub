"""Live MCP -> Module 2 -> Module 1 preparation and review smoke."""

import asyncio
from uuid import uuid4

from mcp import Client

from careerops_automation_mcp_hub.bootstrap import (
    create_runtime,
)

USER_ID = "USER-DEMO-001"
ACTOR_ID = "M2-LIVE-MCP-SMOKE"


async def main() -> None:
    runtime = create_runtime()

    suffix = uuid4().hex[:8].upper()

    try:
        await runtime.check_database_ready()

        server = runtime.build_mcp_server_for_principal(
            user_id=USER_ID,
            actor_id=ACTOR_ID,
        )

        async with Client(
            server,
            raise_exceptions=True,
        ) as client:
            print("1. Creating application...")

            created = await client.call_tool(
                "create_application",
                {
                    "company_name": "CareerOps Live Smoke",
                    "role_title": "Junior AI Engineer",
                    "idempotency_key": (f"live-create-{suffix}"),
                },
            )

            if created.structured_content is None:
                raise RuntimeError("create_application returned no structured content.")

            application_id = created.structured_content["application_id"]

            print(f"   application_id={application_id}")

            print("2. Preparing application through Module 1...")

            prepared = await client.call_tool(
                "prepare_application",
                {
                    "application_id": application_id,
                    "job_description": (
                        "Junior AI Engineer. "
                        "Strong Python software engineering is essential. "
                        "Hands-on experience building APIs with FastAPI "
                        "is essential. "
                        "Experience with LangGraph or agentic AI workflows "
                        "is highly desirable. "
                        "Docker and AWS deployment experience are desirable."
                    ),
                },
            )

            if prepared.structured_content is None:
                raise RuntimeError(
                    "prepare_application returned no structured content."
                )

            preparation_content = prepared.structured_content

            preparation_status = preparation_content["preparation"]["status"]

            print(f"   preparation_status={preparation_status}")

            analysis = preparation_content["analysis"]

            if analysis is None:
                raise RuntimeError("Expected a fresh Agent Engine analysis.")

            print(f"   analysis_status={analysis['status']}")
            print(f"   thread_id={analysis['thread_id']}")
            print(f"   fit_score={analysis['fit_score']}")
            print(f"   reviewable_proposals={analysis['reviewable_proposal_ids']}")

            if analysis["status"] != "awaiting_review":
                raise RuntimeError(
                    "Live workflow did not reach human review. "
                    "The smoke specifically requires an "
                    "awaiting_review result."
                )

            reviewable_ids = analysis["reviewable_proposal_ids"]

            if not reviewable_ids:
                raise RuntimeError(
                    "Agent Engine paused for review without reviewable proposals."
                )

            print("3. Approving the generated CV proposals...")

            review_arguments = {
                "application_id": application_id,
                "idempotency_key": (f"live-review-{suffix}"),
                "action": "approve",
                "approved_proposal_ids": reviewable_ids,
            }

            reviewed = await client.call_tool(
                "review_application",
                review_arguments,
            )

            if reviewed.structured_content is None:
                raise RuntimeError("review_application returned no structured content.")

            review_content = reviewed.structured_content

            print(f"   submission_status={review_content['submission']['status']}")
            print(f"   review_outcome={review_content['submission']['outcome']}")
            print(f"   preparation_status={review_content['preparation']['status']}")
            print(f"   application_status={review_content['application']['status']}")

            if review_content["submission"]["status"] != "completed":
                raise RuntimeError("Durable review submission did not complete.")

            if review_content["preparation"]["status"] != "completed":
                raise RuntimeError("Application preparation did not complete.")

            if review_content["application"]["status"] != "ready_to_apply":
                raise RuntimeError("Application did not advance to ready_to_apply.")

            print("4. Replaying the same review safely...")

            replay = await client.call_tool(
                "review_application",
                review_arguments,
            )

            if replay.structured_content is None:
                raise RuntimeError("Review replay returned no structured content.")

            if replay.structured_content["started_new_review"]:
                raise RuntimeError("Review replay incorrectly started another review.")

            if replay.structured_content["analysis"] is not None:
                raise RuntimeError(
                    "Durable replay unexpectedly returned a fresh remote analysis."
                )

            print("   started_new_review=False")
            print()
            print("LIVE MCP REVIEW WORKFLOW PASSED")

    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
