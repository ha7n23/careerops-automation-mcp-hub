# CareerOps Module 2 Gateway Contract — v1

[← Back to README](../README.md) · [Architecture](ARCHITECTURE.md)

Status: **frozen for Module 3 integration as of 2026-09-28**.

This document defines the stable Module 3-facing boundary of the CareerOps
Automation & MCP Hub. Generated OpenAPI at `/openapi.json` remains the
canonical field-level REST schema. This document freezes endpoint inventory,
identity propagation, lifecycle, recovery, artifact, and error semantics.

## 1. Compatibility policy

- Existing `/api/v1` paths, request fields, response fields, enum values, and
  behaviours must not be removed or reinterpreted.
- Optional response fields and new endpoints may be added compatibly.
- Breaking changes require a new versioned route or a coordinated migration
  across Modules 1, 2, and 3.
- Opaque identifiers are strings; callers must not derive meaning from their
  prefixes.
- Module 2 validates Module 1 JSON before returning it to Module 3.

## 2. Trust and authentication boundary

Local HTTP base URL: `http://127.0.0.1:8001`.

Every `/api/v1` route requires a bearer access token containing:

- a non-empty subject used as the authoritative CareerOps user identifier;
- the configured `careerops:applications` scope;
- a valid signature, issuer, audience, algorithm, and expiry according to the
  configured token verifier.

Missing or invalid credentials return `401`; insufficient scope returns `403`.
Module 3 never supplies `X-User-ID` or the Module 1 service key. Module 2
derives the user from the verified token and adds both trusted service headers
only on its private call to Module 1.

Unknown identifiers and resources owned by another user share the same opaque
`404` behaviour. Cross-user presence must not be disclosed.

## 3. REST endpoint inventory

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/cv-documents` | List evidence-source history |
| `POST` | `/api/v1/cv-documents` | Upload a bounded PDF or DOCX source |
| `POST` | `/api/v1/cv-documents/text` | Create a pasted-text source |
| `POST` | `/api/v1/cv-documents/{document_id}/evidence-review` | Start or recover evidence extraction |
| `GET` | `/api/v1/cv-evidence-reviews` | List evidence-review history |
| `GET` | `/api/v1/cv-evidence-reviews/{review_run_id}` | Recover an evidence review |
| `POST` | `/api/v1/cv-evidence-reviews/{review_run_id}/review` | Submit a complete evidence decision |
| `GET` | `/api/v1/evidence` | Search/filter/page approved evidence |
| `GET` | `/api/v1/evidence/{evidence_id}` | Retrieve approved evidence |
| `PATCH` | `/api/v1/evidence/{evidence_id}` | Edit grounded evidence fields |
| `POST` | `/api/v1/evidence/{evidence_id}/archive` | Archive evidence idempotently |
| `POST` | `/api/v1/evidence/{evidence_id}/restore` | Restore evidence idempotently |
| `POST` | `/api/v1/job-analysis` | Start durable job analysis |
| `GET` | `/api/v1/job-analysis/{thread_id}` | Recover durable job analysis |
| `POST` | `/api/v1/job-analysis/{thread_id}/review` | Submit a CV-proposal decision |
| `POST` | `/api/v1/cv-versions` | Generate or recover a final CV |
| `GET` | `/api/v1/cv-versions/{cv_version_id}` | Retrieve final-CV metadata |
| `GET` | `/api/v1/cv-versions/{cv_version_id}/artifacts/{artifact_format}` | Download verified DOCX/PDF bytes |

`GET /health` is process liveness. `GET /ready` verifies Module 2's database
dependency. The MCP Streamable HTTP application is mounted at `/mcp` by the
configured deployment/client boundary.

## 4. Evidence workflow semantics

PDF/DOCX uploads are read with a 5 MiB default bound before proxying. Pasted
text is limited to 30,000 characters. Ingestion creates a source only; it does
not approve evidence.

Evidence extraction is durable. Starting the same source again recovers the
existing review run. Before a decision, clients should retrieve the current
review and then classify every proposal exactly once as approved, rejected, or
edited. Every reported overlap requires one explicit resolution using only the
targets and actions returned by the review.

The approved Evidence Registry defaults to active records. Search supports
`q`, `category`, `lifecycle_status`, `offset`, and `limit`, with the same bounds
and stable pagination metadata as Module 1.

Edits may replace only category, title, technologies, capabilities, and
approved claims, and must remain grounded in trusted source content. Archive
and restore are recoverable and idempotent. Archived evidence remains
auditable but is excluded from default queries and downstream job grounding;
restored evidence becomes eligible again immediately.

## 5. Job analysis and final-CV semantics

Job analysis returns the full Module 1 contract: requirements, evidence
matches, fit score, proposals, claim-verification reports, reviewable/blocked
identifiers, and audit events. A run is either `awaiting_review` or
`completed`.

Review actions are `approve`, `edit`, `reject`, and `regenerate`. A caller must
recover current state before review, use only identifiers exposed by that run,
and never treat blocked proposals as safely approvable.

Final-CV generation requires a completed analysis with an approved or edited
review outcome plus its source document. Retrying the same accepted
analysis/document pair returns the existing version with
`reused_existing_version=true`.

Artifact metadata never contains storage paths. Downloads accept only `docx`
or `pdf`, require verified non-empty content, validate the upstream media type
and attachment metadata, and return `X-Content-Type-Options: nosniff`.

## 6. MCP and OpenClaw capability surface

The full MCP server exposes application tracking plus evidence, registry, job,
and final-CV operations. File upload and binary artifact download remain REST
operations because binary transfer is not an appropriate conversational tool
payload.

OpenClaw is allowlisted to 23 business tools. They cover:

- application creation, preparation, recovery, review, listing, and pending
  actions;
- evidence-source creation/history and evidence-review recovery/decision;
- registry search, detail, edit, archive, and restore;
- standalone job-analysis start/recovery/review;
- final-CV generation and metadata recovery.

The full server's `update_application_status` tool remains excluded from
OpenClaw. No employer-submission, arbitrary shell, filesystem, process, web,
or direct database capability is provided.

## 7. Recovery and retry rules

- Read operations are safe recovery primitives.
- Application creation and tracked application review use Module 2
  idempotency keys.
- Evidence review submission must be recovered before an uncertain retry.
- Direct job-analysis start/review must not be blindly repeated after an
  ambiguous outcome; recover by thread identifier.
- Evidence archive/restore and final-CV generation for the same accepted
  analysis/document pair are idempotent.
- A client must never infer success solely from a timeout or disconnected
  conversation.

## 8. Error contract

| Status | Meaning |
|---:|---|
| `401` | Bearer token missing or invalid |
| `403` | Required CareerOps scope missing |
| `404` | Resource absent or unavailable to this user |
| `409` | Operation conflicts with durable workflow state |
| `413` | Evidence upload exceeds the Module 2 bound |
| `422` | Request or human decision violates the frozen contract |
| `502` | Module 1 authentication/contract response is invalid |
| `503` | Module 1 or Module 2's required dependency is unavailable |

Module 1 `5xx` bodies and internal storage details are not exposed to clients.

## 9. Contract proof

The repository freezes all 18 authenticated gateway operations in an OpenAPI
inventory test. Unit and MCP tests cover typed response validation, principal
propagation, decisions, lifecycle operations, safe artifact handling, and the
exact OpenClaw allowlist.

The opt-in `scripts/prove_module1_gateway.py` proof is provided to exercise the
real Module 2 → Module 1 boundary with a fresh user and deterministic pasted
evidence:

1. upload and evidence review;
2. registry visibility;
3. archive exclusion from registry defaults and job grounding;
4. restore and renewed job grounding;
5. human CV review when Module 1 returns reviewable proposals, or safe direct
   completion when it does not;
6. final-CV generation, retry reuse, and DOCX/PDF download when proposals are
   reviewable, or proof that unsupported proposals are safely blocked;
7. cross-user isolation for every resource created by the run.

This live proof is intentionally excluded from ordinary CI because it requires
the real Module 1 database and configured LLM provider. Module 1 separately
proves its live DOCX/PDF document pipeline.
