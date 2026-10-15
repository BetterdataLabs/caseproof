# CaseProof Implementation Sequence (Coding Start Plan)

Date: 01 October 2026
Status: Execution Plan (Post Design Freeze)

## 1) Build strategy

Principle:
- Build in parallel tracks, but validate in end-to-end vertical slices.

Tracks:
1. Core reviewer workflow (`F1-F7`).
2. Trust and governance controls (`F8-F9` + RBAC/audit rules).
3. AI reasoning layer (`F11-F13`).
4. Fraud assist layer (`F10`).
5. Benchmark harness and evidence outputs (+ `P7`).
6. Demo access (`F14`).
7. Executive extension (`E1`, Phase 1.5 only).

## 2) Phase order

### Phase A — Foundation
Deliverables:
1. Project skeleton: one Cloud Run app with module boundaries per `docs/ARCHITECTURE_SPEC.md` §1 packaging note.
2. Auth + single RBAC policy function with the full `action_type` table from `docs/ROLE_PERMISSION_MATRIX.md` (including Phase 1.5 rows).
3. Schema and migrations for all entities in `docs/DATA_MODEL_STATE_MACHINE.md` §1, including append-only `audit_events` (INSERT/SELECT-only grant).
4. Transactional audit write helper used by every mutation.
5. Cloud Run deployment scaffold (primary target).
6. Reason-code config (`config/reason_codes.yaml`), lender policy config (`config/lender_policies/`), and dataset-register config loading.

Exit criteria:
- Can create/read case with authenticated role context.
- T1, T3, T4, T7 from `docs/SECURITY_TRUST_CONTROLS.md` §4 pass against the stub endpoints.

### Phase B — Reviewer MVP slice
Deliverables:
1. Intake + field and line-item extraction + discrepancy checks with unit normalization and policy tolerances.
2. Issue panel with side-by-side evidence viewer and region highlighting.
3. Reviewer issue resolution (verified/override), request drafting/editing/sending, case close with outcome + `DECISION_*` code + rationale.
4. Re-evaluation on new document version (recheck, reopen, "ready to confirm", request-item response status).
5. Synthetic case generator for `CP_SYNTH_TRADE_V1` (needed for dev testing from day one).

Exit criteria:
- Full workflow demo for one case from upload to reviewed decision.

### Phase B3 — Decision reports (F7b)
Deliverables:
1. Report snapshot builder (case state + audit events up to watermark) shared by both report types.
2. Internal audit report (PDF + JSON) and counterparty report (PDF) templates with redaction and disclosure allow-list.
3. Write-once storage, hash recording, verification endpoint, retry worker + sweeper job.

Exit criteria:
- Closing a generator case produces both reports within 5 minutes; T10 and T11 pass.

Note: B3 can start as soon as Phase B closes cases; it does not depend on B2. Its issue sections pick up F11–F13 data automatically once B2 lands.

### Phase B2 — AI reasoning layer
Deliverables:
1. Citation verifier (F13) — build first; every later LLM feature depends on it.
2. Line-item alignment with POD aggregation and reviewer correction (F12).
3. Terms/policy assessment with pre-filled terms-explained override (F11).
4. LLM fallbacks for each step.

Exit criteria:
- Partial-delivery-explained and split-shipment generator cases produce correct assessments end-to-end with verified citations.

### Phase C — Trust controls hardening
Deliverables:
1. Audit coverage verified for every mutation and blocked attempt.
2. Reason-code family enforcement for all reason-required actions.
3. Separation-of-duties enforcement, including the `system` actor.

Exit criteria:
- Trust tests T1–T11 pass in CI.

### Phase D — Fraud assist integration
Deliverables:
1. Tamper (metadata + font), identity (cross-doc + registry), and duplicate-invoice signal generation.
2. Reviewer acknowledge/dismiss actions with reasons.
3. Fraud signal observability and metrics hooks.

Exit criteria:
- Fraud panel integrated without breaking adjudication boundary.

### Phase E — Benchmark evidence pipeline
Deliverables:
1. Comparator run framework (manual/rules-only/LLM-only/hybrid).
2. Metric computation and scoreboard export.
3. Run artifact persistence in evidence paths.
4. In-app evidence page (P7).

Exit criteria:
- One complete development benchmark run reproducible by `run_id`.

### Phase E2 — Demo access (F14)
Deliverables:
1. `DEMO_MODE` flag, demo accounts, role switcher.
2. Guided case + coverage cases seeded; `clone_demo_case`.
3. Offline demo reset job.

Exit criteria:
- A new user reaches the guided case in under 60 seconds from the URL; T9 passes with the flag off.

### Phase F — Executive control tower (Phase 1.5)
Deliverables:
1. Portfolio dashboard counters/trends.
2. Prioritize/escalate/reassign (manager + executive) and pause/resume (manager) actions with reason-code and audit.
3. Role-guarded action affordances in UI.

Exit criteria:
- Executive interventions visible in case timeline and audit logs.

## 3) Definition of done per phase

A phase is done only if:
1. Feature acceptance criteria pass (`docs/FEATURE_SPEC.md`).
2. Trust checks pass (`docs/SECURITY_TRUST_CONTROLS.md`).
3. Benchmark instrumentation exists where relevant (`docs/BENCHMARK_EVIDENCE_PROTOCOL.md`).
4. Session continuity docs updated.

## 4) Parallelization guidance

Safe parallel tasks:
1. UI layout scaffolding and backend schema/migrations.
2. Rules engine development and audit-service pipeline.
3. Benchmark-runner development and trust test writing.

Tasks that should remain sequential:
1. State machine enforcement after schema freeze.
2. Final RBAC policy integration before executive actions.
3. Holdout benchmark execution after all comparator paths are stable.

## 5) Risk controls during implementation

1. Scope lock
- Do not introduce new personas or autonomous actions in MVP.

2. Evidence first
- Any major feature merge requires measurable output path.

3. Trust first
- Any role-boundary bug is a release blocker.

4. Cut order if schedule slips (cut from the top first)
1. Phase F / E1 (executive control tower).
2. P1–P6 polish features.
3. P7 evidence page (show scoreboard in the deck instead).
4. F12 multi-POD aggregation (keep single-POD line alignment).
5. F10 tamper font check (keep metadata check).
Never cut: F7b decision reports, F11, F13, F14, trust tests, or the holdout benchmark.
If pressed, F7b may drop the JSON export and page-region image crops (keep quote text) before anything above it.

## 6) Handoff rule

At each phase boundary:
1. Update `docs/PROJECT_CONTEXT.md` with current phase and risks.
2. Append `docs/SESSION_LOG.md` with decisions and next actions.
