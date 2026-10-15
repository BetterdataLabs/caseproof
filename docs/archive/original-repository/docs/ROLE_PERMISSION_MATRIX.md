# CaseProof Role Permission Matrix

Date: 01 October 2026
Updated: 02 October 2026 (alignment pass — see `docs/SESSION_LOG.md` Session 012)
Status: Frozen v1.1

Purpose:
- Define clear action boundaries across reviewer, manager, and executive personas.
- Prevent governance drift while enabling operational intervention.
- Ensure all privileged actions remain explainable and auditable.

## Personas

1. Reviewer
- Primary case adjudicator and workflow owner.

2. Manager (Operations Lead)
- Team-level queue oversight and workload balancing.

3. Executive (Control Tower)
- Portfolio-level visibility and intervention for bottlenecks/SLA risk.

## Permission matrix

Legend:
- `Y`: allowed (audited like every mutation)
- `Y*`: allowed, reason code required (from `docs/REASON_CODE_TAXONOMY.md`)
- `Y*?`: allowed; reason code required only in the override case noted
- `N`: not allowed — attempt is blocked and audited with `outcome = blocked`

Every mutation is audited regardless of legend value (see `docs/DATA_MODEL_STATE_MACHINE.md` §8).

| Capability / Action | action_type | Reviewer | Manager | Executive | Phase | Notes |
|---|---|---:|---:|---:|---|---|
| Create case and upload documents | `create_case`, `upload_document` | Y | Y | N | MVP | Executive is non-operational on intake. |
| View case details (in scope) | — | Y | Y | Y | MVP | Subject to `allowed_case_scopes`. |
| View team/portfolio queue metrics | — | N | Y | Y | 1.5 | Reviewer queue is scoped to assigned/authorized cases. |
| View discrepancy findings and evidence | — | Y | Y | Y | MVP | Checks run automatically on upload; no manual "run" action. |
| View fraud-risk signals | — | Y | Y | Y | MVP | Signals are assistive only for all roles. |
| Acknowledge fraud signal | `acknowledge_fraud_signal` | Y | N | N | MVP | Reviewer-only. |
| Dismiss fraud signal | `dismiss_fraud_signal` | Y* | N | N | MVP | `FRAUD_DISMISS_*`. |
| Resolve issue | `resolve_issue` | Y*? | N | N | MVP | Code required only for override (`recheck_status != passing`): `REVIEW_OVERRIDE_*`. Terms-explained issues (F11) are an override with a pre-filled code. |
| Reopen issue | `reopen_issue` | Y | N | N | MVP | System may also reopen on failing recheck. |
| Correct line-item alignment | `correct_alignment` | Y | N | N | MVP | Triggers recheck of affected issues (F12). |
| Send correction request | `send_correction_request` | Y | N | N | MVP | Sent text is audited. |
| Add case/issue note | `add_note` | Y | Y | Y | Could (P6) | Actor-attributed and timestamped. |
| Export interim case summary | `export_summary` | Y | Y | Y | MVP | Redaction applied (F7a). |
| Download internal audit report | `download_decision_report` | Y | Y | Y | MVP | Closed cases in scope; download audited (F7b). |
| Download counterparty decision report | `download_decision_report` | Y | Y | Y | MVP | Reviewer sends it to the client outside the system in v1; download audited. |
| Regenerate or edit a decision report | — | N | N | N | MVP | System-only retry; reports are write-once. |
| Change case priority | `prioritize_case` | N | Y* | Y* | 1.5 | `PRIORITY_*`. |
| Escalate to channel | `escalate_channel` | N | Y* | Y* | 1.5 | `ESCALATION_*`. |
| Reassign case owner | `reassign_owner` | N | Y* | Y* | 1.5 | `REASSIGNMENT_*`. |
| Pause case | `pause_case` | N | Y* | N | 1.5 | `HOLD_*`. Executive keeps exactly three actions. |
| Resume case | `resume_case` | N | Y* | N | 1.5 | `RESUME_*`. |
| Close case (final decision) | `close_case` | Y* | N | N | MVP | Outcome `approved | rejected` + `DECISION_*` code + written rationale; triggers decision reports. |
| Clone guided demo case | `clone_demo_case` | Y | Y | N | MVP (demo env only) | Rejected when demo flag is off (F14, T9). |
| Any adjudication by `system` actor | — | N | N | N | MVP | Non-negotiable: no auto-resolve / auto-close / auto-dismiss. |

## Governance controls (non-negotiable)

1. Reason code required
- Exactly the `Y*` cells and the override case of `resolve_issue`.
- Codes must be in the action's family in `docs/REASON_CODE_TAXONOMY.md`; unknown or wrong-family codes are rejected.

2. Immutable audit trail
- Every mutation logs: timestamp, actor, role, case ID, prior value, new value, reason code (when required), correlation ID, outcome.

3. Separation of duties
- Reviewer adjudicates (issue resolution, fraud signal disposition, case close).
- Manager/Executive can reprioritize/escalate/reassign (and manager can pause/resume) but cannot adjudicate.

4. Read-mostly executive mode
- Executive defaults to observability plus three intervention actions only.

## Implementation notes

Minimum RBAC claims in auth token/session:
- `role`: `reviewer | manager | executive`
- `team_id`
- `allowed_case_scopes`

Authorization check order (single policy function, one table lookup keyed by `action_type`):
1. Verify role allows `action_type` (this table).
2. Verify case is in `allowed_case_scopes`.
3. Verify reason code presence and family where required.
4. Verify state-machine guard.
5. Commit mutation + audit event in one transaction; on any failure at steps 1–4, write a `blocked` audit event and return 403/409.

MVP note: Phase 1.5 intervention endpoints may not exist yet, but their `action_type` rows are in the policy table from Phase A so trust tests T1/T2 can exercise them.

## Alignment to current feature set

- Reviewer actions align with `F1-F14` in `docs/FEATURE_SPEC.md`.
- Manager/Executive interventions align with `E1` in `docs/FEATURE_SPEC.md`.
- Governance and audit boundaries align with `docs/PrincipalEngineeringRules.md`.
