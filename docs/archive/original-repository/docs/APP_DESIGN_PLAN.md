# CaseProof App Design Plan (Current Working Document)

Date: 26 September 2026
Updated: 01 October 2026
Status: Active
Phase: App planning and final design (demo artifacts deferred)

## 1) Phase objective

Finalize the production-grade app design before any demo-document work.

This phase is complete only when:
1. Product scope is frozen.
2. Feature set is prioritized and accepted.
3. System design is agreed.
4. Evaluation and reliability criteria are defined.
5. Security and audit model is specified.

## 2) Product definition

CaseProof is a reviewer copilot for trade-finance document discrepancy resolution with assistive fraud-risk intelligence.

Primary user:
- Trade-finance reviewer handling invoice + proof-of-delivery checks.

Secondary persona (Phase 1.5, non-MVP):
- Executive/operations leader monitoring portfolio flow, bottlenecks, and intervention actions.

Core job-to-be-done:
- Detect, explain, request, and close document discrepancies with full traceability.
- Surface evidence-linked fraud risk signals for reviewer triage without auto-decisioning.

## 3) Solution options with pros/cons

### Option A — Rules-only checker

Pros:
- Predictable behavior.
- Lower implementation complexity.
- Easier debugging.

Cons:
- Weak handling of messy document language.
- Limited usefulness for request drafting.
- Poor adaptability to varied document formats.

### Option B — LLM-only reasoning flow

Pros:
- Flexible handling of document variation.
- Strong natural-language summaries and request drafts.

Cons:
- Higher hallucination/consistency risk.
- Harder deterministic validation.
- Lower trust for high-stakes BFSI decisions.

### Option C — Hybrid design (recommended)

Pros:
- Combines deterministic checks with language reasoning.
- Better trust: AI proposes, rules verify, reviewer decides.
- Strong balance of quality, explainability, and control.
- Supports assistive fraud signals without breaking reviewer control.

Cons:
- More integration complexity.
- Requires careful orchestration and logging.

Decision:
- Choose Option C (Hybrid) as final app architecture direction.

Implementation lock:
- MVP excludes executive intervention controls; `E1` remains Phase 1.5.
- Primary deployment target is Cloud Run.

## 4) Final app design (target)

Workflow:
1. Upload case documents (invoice, one or more PODs, optional PO/terms) against a lender policy.
2. Extract structured fields, line items, and source snippets.
3. AI aligns invoice lines to delivery lines; deterministic checks run with unit normalization and policy tolerances.
4. AI assesses each issue against terms and lender checklist (explained / needs request / unclear); every quote is verified against the source page.
5. Run assistive fraud-risk signals (tamper, identity, duplicate invoice) with evidence links.
6. AI drafts a correction request covering only issues that need one; reviewer validates, edits, and sends.
7. New files arrive; issues rechecked, request items marked addressed/outstanding, reviewer confirms resolutions.
8. Reviewer approves or rejects with reason code and written rationale; system issues a write-once internal audit report (full evidence + audit trail) and a client-safe counterparty decision report.

Phase 1.5 control-tower flow:
1. Executive opens portfolio dashboard (live/paused/issue/escalated states).
2. Executive filters by SLA breach, risk band, counterparty, and backlog age.
3. Executive triggers intervention action (prioritize, escalate channel, reassign owner).
4. System enforces reason code + role check + immutable audit event.

System components:
- Ingestion and document storage.
- Extraction and normalization service.
- Rules engine for deterministic checks.
- Lender policy configuration (rules, tolerances, checklist).
- Fraud signal engine (tamper/identity/duplicate-invoice signals).
- AI reasoning service for line alignment, terms/policy assessment, explanation, and draft requests.
- Citation verifier for all AI quotes.
- Demo access mode for judges.
- Case state and issue lifecycle store.
- Reviewer UI with evidence-linked findings.
- Audit/event logger.
- Executive control-tower dashboard service (read-mostly + controlled interventions).

Core design references:
- Service boundaries: `docs/ARCHITECTURE_SPEC.md`
- Entity/state design: `docs/DATA_MODEL_STATE_MACHINE.md`
- Trust controls: `docs/SECURITY_TRUST_CONTROLS.md`

## 5) Required features (MVP)

1. Case creation and multi-file upload.
2. Field extraction with confidence and source references.
3. Discrepancy detection (quantity, totals, references, entity IDs).
4. Evidence-linked issue panel (quote + page reference).
5. Editable AI-generated correction request.
6. Issue lifecycle tracking after customer responses.
7. Manual override controls and reviewer decision capture.
8. Interim case summary, plus internal audit and counterparty decision reports generated on close (F7).
9. Authentication and role-based case access.
10. Immutable audit history for reviewer and system actions.
11. Assistive fraud-risk signal panel with reviewer acknowledgment.
12. Terms- and policy-aware assessment of each discrepancy (F11).
13. Line-item alignment across description variants and split deliveries (F12).
14. Citation verification for every AI quote (F13).
15. Judge/demo access mode (F14).

Fraud intelligence scope rule:
- Fraud signals are assistive triage only.
- No auto-reject, auto-block, or auto-approval paths.
- Every risk signal must include explanation and source evidence.

Executive control-tower scope rule (Phase 1.5):
- Dashboard is read-mostly by default.
- Intervention actions are limited to prioritize, escalate channel, and reassign owner.
- Every intervention requires reason code and is immutably logged.
- No executive action bypasses reviewer final decision controls.
- Role boundaries are defined in `docs/ROLE_PERMISSION_MATRIX.md`.

## 6) Out-of-scope for this phase

- Slide narrative optimization.
- Judge script writing.
- Demo video packaging and editing.
- Submission checklist polish.

These remain deferred until app design sign-off.

## 7) Design risks and mitigations

1. OCR/parse noise creates false discrepancies.
   - Mitigation: confidence thresholds + unresolved/manual-review status.
2. AI suggestions become overconfident.
   - Mitigation: force evidence links and reviewer confirmation.
3. Issue state confusion after new uploads.
   - Mitigation: explicit state machine (open/resolved/reopened).
4. Slow reviewer flow.
   - Mitigation: one-click jump from issue to source evidence.
5. Fraud false positives erode trust.
   - Mitigation: calibrated thresholds, reason codes, and reviewer dismiss-with-reason.
6. Executive interventions create inconsistent workflows.
   - Mitigation: strict role permissions, constrained action set, and explicit downstream ownership.

## 8) Additional polish features (post-MVP)

1. Priority queue scoring with SLA countdown and stale-case alerts.
2. Saved filter views (by severity, counterparty, unresolved days, fraud-risk band).
3. Keyboard-first review actions (next issue, confirm resolution, open evidence).
4. Counterparty profile sidecard with recent discrepancy/fraud history summary.
5. Reviewer feedback loop on false positives/false negatives for model tuning.
6. In-app collaboration notes and assignment handoff between reviewers.
7. Executive control-tower dashboard with process health KPIs and intervention controls.

## 9) Sign-off checklist (gate to demo-doc phase)

- Final architecture diagram agreed.
- MVP feature list frozen.
- Acceptance criteria written per feature.
- Architecture spec finalized (`docs/ARCHITECTURE_SPEC.md`).
- Data model and issue state machine finalized.
- Security/trust controls finalized (`docs/SECURITY_TRUST_CONTROLS.md`).
- Reason-code taxonomy finalized (`docs/REASON_CODE_TAXONOMY.md`).
- Dataset register finalized (`docs/DATASET_REGISTER.md`).
- Benchmark/evidence protocol finalized and approved (`docs/BENCHMARK_EVIDENCE_PROTOCOL.md`).
- Role-permission matrix finalized and approved (`docs/ROLE_PERMISSION_MATRIX.md`).
- Security and audit controls documented.
- Evaluation metrics and test protocol approved.

Only after all are complete do we resume demo documentation.
