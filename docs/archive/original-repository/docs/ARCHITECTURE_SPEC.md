# CaseProof Architecture Specification

Date: 01 October 2026
Updated: 05 October 2026 (alignment pass — deployment packaging, flows, events; F11–F14 modules — Session 013; report-service — Session 014)
Status: Frozen v1.1

## 1) Scope and intent

This document defines implementation-level architecture boundaries for:
- Reviewer workflow MVP (`F1-F14`),
- Executive control tower Phase 1.5 (`E1`),
- Benchmark/trust observability requirements.

Non-goal:
- UI pixel-level design details.

Deployment decision (frozen v1):
- Primary target: **Cloud Run** for backend/API and internal services.
- Firebase is out-of-scope for initial implementation and may be evaluated later.

Deployment packaging (v1):
- The services in §2 are **logical module boundaries**, not separately deployed services.
- v1 deploys as one Cloud Run service (`caseproof-app`: web UI + API + all modules) plus Cloud Run jobs for `benchmark-runner` and the retention purge.
- Modules communicate through in-process interfaces; the canonical events in §5 are written as audit events, not published to a broker. Pub/Sub is deferred.
- One Cloud SQL (Postgres) database holds application tables and the append-only `audit_events` table, so mutation + audit commit atomically.

## 2) System topology (logical)

1. `web-app`
- Reviewer + manager + executive UI.

2. `api-gateway`
- Authn/authz enforcement, request validation, rate limiting, routing.

3. `case-service`
- Case lifecycle, document metadata, assignment, prioritization, escalation.

4. `document-service`
- Upload ingestion, storage references, parser orchestration.

5. `extraction-service`
- Field and line-item extraction + provenance (page, bounding box) + confidence values.

6. `policy-module` (F11)
- Loads versioned lender policies from `config/lender_policies/`; supplies enabled rules, tolerances, severities, checklist items.

7. `rules-engine`
- Deterministic discrepancy checks (quantity/totals/IDs/references) with unit normalization and policy tolerances; line-level checks on aligned pairs, summed across PODs (F12).

8. `fraud-signal-service`
- Assistive fraud signals: tamper (PDF metadata + font checks), identity inconsistency (cross-doc + counterparty registry), duplicate invoice (exact + near-duplicate across cases).

9. `copilot-service`
- Gemini calls: line-item alignment (F12), terms/policy assessment (F11), issue explanation, request drafting. All prompts request structured JSON with citations.

10. `citation-verifier` (F13)
- Checks every quote from `copilot-service` against extracted page text before results are stored as displayable evidence.

11. `workflow-service`
- Issue state transitions, guard conditions, re-evaluation on new uploads.

12. `audit-service`
- Immutable audit event ingestion and query API.

13. `benchmark-runner` (internal/offline service)
- Comparator runs, metrics calculation, artifact exports.

15. `report-service` (F7b)
- Builds internal audit report (PDF + JSON) and counterparty report (PDF) from a case snapshot at the audit watermark; HTML templates rendered to PDF; writes to a dedicated Cloud Storage bucket with create-only precondition (`ifGenerationMatch=0`) and object versioning; app service account lacks delete permission on that bucket.
- Exposes a verification endpoint: recompute a stored report's SHA-256 and compare with the audit-recorded hash.

14. `demo-module` (F14; active only when `DEMO_MODE=true`)
- Demo accounts, role switcher, guided case seeding, `clone_demo_case`. Environment reset is an offline Cloud Run job.

## 3) Data stores

1. Object storage
- Raw documents and generated exports.

2. Relational database
- Cases, documents, issues, fraud signals, actions, assignments, reason codes.

3. Append-only audit store
- `audit_events` table in the same database, INSERT/SELECT-only for the app role (see `docs/DATA_MODEL_STATE_MACHINE.md` §8).

4. Benchmark artifact storage
- Run manifests, predictions, metrics, confusion matrices.

## 4) Primary request flows

### Flow A — Intake and first-pass analysis
1. User uploads invoice + delivery docs.
2. `document-service` stores files and emits `documents_uploaded` event.
3. `extraction-service` parses fields, line items, and evidence snippets.
4. `copilot-service` proposes line-item alignment; `citation-verifier` checks quoted descriptions.
5. `rules-engine` runs deterministic checks using the case's lender policy (tolerances, unit normalization, POD aggregation).
6. `workflow-service` opens issues and timeline entries.
7. `copilot-service` assesses each open issue against terms/checklist (F11) and drafts explanations + correction request; `citation-verifier` checks all quotes.
8. `fraud-signal-service` computes assistive signals (can run in parallel with steps 4–7).
9. `audit-service` records the full processing chain.

Low-confidence fields (below threshold) are marked `needs_review`; issues depending on them get `recheck_status = needs_review` and cannot be resolved as `verified`.

### Flow B — Reviewer adjudication
1. Reviewer opens case and evidence-linked issue panel.
2. Reviewer resolves issues (verified, or override with `REVIEW_OVERRIDE_*`), acknowledges/dismisses fraud signals, edits the drafted request, and sends it.
3. Sending a request moves the case `live -> issue_blocked`.
4. `workflow-service` validates role/guard conditions before state transitions.
5. `audit-service` logs every decision and reason code.

### Flow C — New response document re-evaluation
1. New document version uploaded; case moves `issue_blocked -> live`.
2. Extraction runs on the new document; only issues whose evidence came from that `document_type` are rechecked.
3. System updates `recheck_status`; a `resolved` issue whose recheck fails is reopened.
4. Open issues whose recheck now passes are shown as "ready to confirm"; the reviewer confirms resolution. The system never resolves issues.

### Flow E — Case decision and reports
1. Reviewer closes the case with outcome, `DECISION_*` reason code, and written rationale; guards checked; `case_closed` audit event commits with the status change (this event is the audit watermark).
2. Case `report_status = pending`; a report task is enqueued (in-process worker with retries + a sweeper Cloud Run job every 5 minutes for `pending`/`failed`).
3. `report-service` snapshots case data and audit events up to the watermark, renders both reports, applies redaction and the counterparty disclosure allow-list, stores them write-once, and records hashes in `decision_report_generated` events.
4. `report_status = generated`; reports become downloadable per `docs/ROLE_PERMISSION_MATRIX.md`.

### Flow D — Manager/executive intervention (Phase 1.5)
1. Manager/executive opens control tower dashboard.
2. Triggers allowed action: `prioritize_case | escalate_channel | reassign_owner` (both roles) or `pause_case | resume_case` (manager only).
3. Authorization + reason-code checks enforced by the policy layer.
4. Action and its audit event commit in the same transaction.

## 5) Service contracts (high-level)

Canonical internal events:
- `case_created`
- `documents_uploaded`
- `extraction_completed`
- `discrepancy_detected`
- `fraud_signal_generated`
- `reviewer_decision_recorded`
- `alignment_proposed`
- `alignment_corrected`
- `issue_assessed`
- `citation_verification_failed`
- `issue_recheck_completed`
- `request_item_status_changed`
- `issue_state_changed`
- `fraud_signal_status_changed`
- `correction_request_sent`
- `case_status_changed`
- `case_priority_changed`
- `case_escalated`
- `case_reassigned`
- `case_closed`
- `summary_exported`
- `action_blocked`
- `retention_purge_executed`
- `demo_case_cloned`
- `decision_report_generated`
- `decision_report_generation_failed`
- `decision_report_downloaded`

Every event is an `AuditEvent` row with the fields in `docs/DATA_MODEL_STATE_MACHINE.md` §1.15.

## 6) Reliability and fallback behavior

1. LLM unavailable
- Continue deterministic checks; issue explanations show "AI unavailable"; correction request falls back to a deterministic template (`draft_source = template_fallback`) the reviewer edits.
- F11 assessments default to `unclear` (`assessment_source = fallback`).
- F12 alignment falls back to exact/normalized description match plus line order; unmatched lines are `needs_review`.

1a. LLM returns malformed JSON or unverifiable citations
- One retry with a validation-error message; then treat as unavailable for that step (same fallbacks as above).

2. Low extraction confidence
- Block auto-progression and require reviewer verification.

3. Audit write failure
- Abort privileged mutation transaction.

3a. Decision report generation failure
- Case stays closed (decision is not rolled back); `report_status` remains `pending` and retries; after 3 failures `failed` + alert; sweeper job retries.

4. Fraud model uncertainty
- Show low-confidence label; do not escalate severity automatically.

## 7) Security and trust boundary points

1. RBAC enforcement in one policy layer called by every mutation endpoint.
2. Reason code mandatory per `docs/REASON_CODE_TAXONOMY.md` §3.
3. Reviewer-only adjudication actions (`resolve_issue`, fraud signal disposition, `close_case`).
4. Prompt/input redaction before model calls where needed.
5. Immutable audit logging for every privileged and adjudication action.

## 8) Performance targets (initial)

1. Case list load (P95): <= 2.0s for expected MVP dataset.
2. Case detail open (P95): <= 2.5s.
3. Initial extraction + checks + assessment completion (P95): <= 45s per MVP case size (raised from 30s for F11/F12 LLM calls; UI shows deterministic findings first and fills AI results progressively).
4. Dashboard counter refresh (P95): <= 5s.

## 9) Observability requirements

Required signals:
- Request success/error rates by endpoint and role.
- Processing latency by service stage.
- State transition counts and failure reasons.
- Fraud signal dismiss/accept distributions.
- Unauthorized action attempts and block outcomes.

## 10) Freeze dependencies

Before coding begins, freeze with sign-off:
1. `docs/FEATURE_SPEC.md`
2. `docs/DATA_MODEL_STATE_MACHINE.md`
3. `docs/ROLE_PERMISSION_MATRIX.md`
4. `docs/SECURITY_TRUST_CONTROLS.md`
5. `docs/REASON_CODE_TAXONOMY.md`
6. `docs/DATASET_REGISTER.md`
7. `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
