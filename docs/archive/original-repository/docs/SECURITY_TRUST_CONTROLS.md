# CaseProof Security and BFSI Trust Controls

Date: 01 October 2026
Updated: 05 October 2026 (alignment pass — canonical trust tests T1–T7; T8–T9 for F13/F14; C8 + T10–T11 for decision reports)
Status: Frozen v1.1

## 1) Objective

Define explicit, testable trust controls so BFSI readiness is proven by evidence, not narrative.

## 2) Control framework

### C1 — Role-based access control (RBAC)
- Enforce action permissions by role (`reviewer`, `manager`, `executive`).
- Must follow `docs/ROLE_PERMISSION_MATRIX.md` exactly.

### C2 — Separation of duties
- Reviewer is sole adjudication authority: resolve issue, acknowledge/dismiss fraud signal, close case.
- Manager/Executive may only intervene via prioritize/escalate/reassign; manager may also pause/resume (Phase 1.5).
- The `system` actor may detect, recheck, suggest, and reopen, but never adjudicate.

### C3 — Reason-code governance
- Actions listed in `docs/REASON_CODE_TAXONOMY.md` §3 must include a reason code from the matching family.
- Missing, unknown, or wrong-family reason code results in blocked action.
- Allowed reason codes are frozen in `docs/REASON_CODE_TAXONOMY.md`.

### C4 — Immutable audit trail
- Every mutation and every blocked attempt is append-only audited.
- Audit insert is in the same DB transaction as the mutation; audit write failure aborts the mutation.
- Implementation detail: `docs/DATA_MODEL_STATE_MACHINE.md` §8.

### C5 — Data minimization and redaction
- Only required fields sent to model services.
- Sensitive data redacted in exports and logs where possible.

Field-level redaction policy (frozen v1):
1. Always redact from model prompts and exported summaries:
   - bank account numbers,
   - tax IDs and national IDs,
   - personal phone/email values,
   - full addresses (retain city/country only),
   - document signatures/images.
2. Partially mask in operational UI/logs:
   - invoice/reference numbers (show last 4 chars only in list views).
3. Never store full sensitive fields in benchmark artifacts.
4. Audit events store action metadata, not raw sensitive payloads.

### C6 — Controlled AI behavior
- AI outputs are assistive and cannot auto-adjudicate.
- Low-confidence outputs must route to manual review.
- Every quote in an AI output is verified against source page text before display (F13); unverified quotes are never shown as evidence.
- AI assessments (F11) and alignments (F12) never change issue or case status.

### C7 — Secure service posture (prototype baseline)
- Encrypted transport and storage.
- Secret management for API keys and service credentials.
- Least-privilege service account permissions.
- Demo mode (F14) is a deployment flag; demo accounts, role switcher, and `clone_demo_case` do not exist when it is off.

### C8 — Decision record integrity and disclosure (F7b)
- Every closed case gets an internal audit report and a counterparty report, built from a fixed audit watermark.
- Reports are write-once objects (create-only precondition; app service account has no delete/overwrite permission); SHA-256 recorded in the audit trail and printed in the report.
- Counterparty report follows a disclosure allow-list: no fraud signals or fraud reasons, internal notes, AI internals, reviewer names, interventions, or blocked attempts (prevents tipping off and protects staff).

## 3) Control-to-evidence mapping

| Control | Evidence metric/test | Source |
|---|---|---|
| C1 RBAC | Unauthorized action block rate = 100% | `BENCHMARK_EVIDENCE_PROTOCOL` §4.4 |
| C2 SoD | Reviewer adjudication integrity = 100% | `BENCHMARK_EVIDENCE_PROTOCOL` §4.4 |
| C3 Reason codes | Reason-code compliance = 100% | `BENCHMARK_EVIDENCE_PROTOCOL` §4.4 |
| C4 Audit immutability | Audit completeness = 100% + audit-write-failure test pass | `BENCHMARK_EVIDENCE_PROTOCOL` §4.4/§8 |
| C5 Redaction | No prohibited fields in exported artifacts (spot-check + test) | Internal QA checklist |
| C6 Assistive-only AI | No auto-approve/reject/close events in logs; 0 unverified quotes displayed as evidence | Audit query; T6, T8 |
| C7 Service security | Secrets not hardcoded + scoped service identities; demo features off in non-demo env | Deployment review; T9 |
| C8 Decision records | 100% of closed cases have both reports; report hash matches audit event; 0 disallowed fields in counterparty reports | T10, T11; benchmark §4.4 |

## 4) Required trust test cases (canonical list)

This is the single source of truth for trust tests. `docs/BENCHMARK_EVIDENCE_PROTOCOL.md` §8 references these IDs. All tests run as automated API tests in CI.

| ID | Scenario | Expected result | Control |
|---|---|---|---|
| T1 | Reviewer attempts an intervention action (`reassign_owner`, `prioritize_case`) | 403 + `blocked` audit event | C1 |
| T2 | Manager or executive attempts adjudication (`resolve_issue`, `close_case`, `dismiss_fraud_signal`) | 403 + `blocked` audit event | C1, C2 |
| T3 | Reason-required action with missing, unknown, or wrong-family reason code | 400 + `blocked` audit event | C3 |
| T4 | Audit insert fails during a mutation (fault injection) | Mutation rolled back; state unchanged | C4 |
| T5 | Low-confidence extraction field or signal | Issue `recheck_status = needs_review`; `verified` resolution not allowed; correction draft not auto-generated for that field | C6 |
| T6 | `system` actor attempts `resolve_issue` or `close_case` (e.g. after a passing recheck) | Blocked + audited; issue stays unresolved until reviewer confirms | C2, C6 |
| T7 | User accesses or mutates a case outside `allowed_case_scopes` | 403 + `blocked` audit event | C1 |
| T8 | AI output contains a quote not present in the source page (injected via mocked LLM response) | Quote stored `unverified`, not rendered as evidence; F11 assessment downgraded to `unclear` | C6 |
| T9 | Demo login, role switch, or `clone_demo_case` attempted with demo flag off | Rejected; `clone_demo_case` audited as `blocked` | C7 |
| T10 | Close a case rejected with `DECISION_REJECTED_FRAUD_CONCERN` and active-then-dismissed fraud signals, internal notes, and interventions | Counterparty report contains none of: fraud terms, signal data, notes, reviewer names, interventions, unmasked identifiers (automated scan of extracted PDF text) | C5, C8 |
| T11 | Attempt to overwrite a stored decision report; tamper with report bytes | Overwrite rejected by storage precondition; recomputed hash ≠ audit-recorded hash is detected by verification endpoint | C4, C8 |

## 5) Audit schema minimum

Required fields (matches `AuditEvent` in `docs/DATA_MODEL_STATE_MACHINE.md` §1):
- `event_id`, `case_id`, `event_type`, `action_type`, `outcome`, `actor_id`, `actor_role`, `timestamp`.
- `reason_code` (+ optional `reason_note`) where required.
- `before_json`, `after_json`, `correlation_id`.

Required query scenarios:
1. All actions for one case ordered by timestamp.
2. All privileged actions by role/date range.
3. All blocked authorization attempts.

## 6) Operational guardrails

1. Trust controls are release-blocking.
2. Any critical control failure blocks demo/proposal lock.
3. Exceptions are not allowed for adjudication boundary rules.

## 7) Retention and deletion policy (frozen v1)

1. Case documents
- Retain 180 days from `Case.closed_at`, then purge object files.

2. Case metadata (non-sensitive operational records)
- Retain 365 days from `Case.closed_at`.

3. Audit events
- Retain 730 days from `AuditEvent.timestamp` (append-only store).

4. Benchmark artifacts
- Retain 365 days from `run_timestamp`.

4a. Decision reports
- Internal audit report: retain 730 days from `Case.closed_at` (matches audit events; outlives source documents, so it embeds evidence snippets).
- Counterparty report: retain 365 days from `Case.closed_at`.

5. Deletion execution
- Daily retention job enforces purge windows.
- Every purge action emits immutable `retention_purge_executed` audit event.

## 8) Ownership

1. Security/trust owner
- Maintains control suite and pass/fail dashboard.

2. Platform owner
- Ensures enforcement in gateway/workflow services.

3. QA owner
- Verifies trust tests and artifact completeness per release.

## 9) Links

- `docs/ROLE_PERMISSION_MATRIX.md`
- `docs/DATA_MODEL_STATE_MACHINE.md`
- `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
- `docs/REASON_CODE_TAXONOMY.md`
- `docs/PrincipalEngineeringRules.md`
