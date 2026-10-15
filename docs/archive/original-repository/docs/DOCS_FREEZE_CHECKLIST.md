# CaseProof Docs Freeze Walkthrough Checklist

Date: 01 October 2026
Status: Final freeze approved

Decision summary:
- Documentation is **coding-ready**.
- Final freeze status: **Approved (all blockers closed)**.

## A) Approved (ready)

| Area | Status | Evidence |
|---|---|---|
| Mandatory reading order defined | Approved | `docs/DOCS_INDEX.md` |
| MVP/Phase scope clearly defined | Approved | `docs/FEATURE_SPEC.md` |
| Architecture boundaries and failure handling | Approved | `docs/ARCHITECTURE_SPEC.md` |
| Data model and state transitions | Approved | `docs/DATA_MODEL_STATE_MACHINE.md` |
| RBAC and separation of duties | Approved | `docs/ROLE_PERMISSION_MATRIX.md` |
| Trust-control framework and tests | Approved | `docs/SECURITY_TRUST_CONTROLS.md` |
| Benchmark protocol and comparator standard | Approved | `docs/BENCHMARK_EVIDENCE_PROTOCOL.md` |
| Build sequence and phase gates | Approved | `docs/IMPLEMENTATION_SEQUENCE.md` |
| Continuity discipline and handoff rules | Approved | `docs/PrincipalEngineeringRules.md`, `docs/SESSION_LOG.md` |

## B) Blocker closure record

| # | Blocker | Resolution | Status |
|---|---|---|---|
| 1 | Public benchmark dataset list not frozen | Frozen in `docs/DATASET_REGISTER.md` and referenced in benchmark protocol | Closed |
| 2 | Reason-code taxonomy not frozen | Frozen in `docs/REASON_CODE_TAXONOMY.md` and linked to trust/RBAC docs | Closed |
| 3 | Executive controls scope ambiguity (MVP vs Phase 1.5) | Locked to Phase 1.5 in `docs/FEATURE_SPEC.md` and `docs/APP_DESIGN_PLAN.md` | Closed |
| 4 | Deployment target choice not frozen (Cloud Run vs Firebase) | Primary target locked to Cloud Run in `docs/ARCHITECTURE_SPEC.md` | Closed |
| 5 | Redaction field policy not explicit | Field-level redaction policy added in `docs/SECURITY_TRUST_CONTROLS.md` | Closed |
| 6 | Retention/deletion durations unspecified | Retention/deletion windows added in `docs/SECURITY_TRUST_CONTROLS.md` | Closed |

## B2) Post-freeze alignment amendments (02 October 2026, v1.1)

Cross-document inconsistencies found in the pre-coding review were resolved. No scope was added to the MVP.

| # | Inconsistency | Resolution | Docs |
|---|---|---|---|
| 1 | Demo script had issues "closing automatically"; state machine says reviewer-only | System rechecks/reopens and marks "ready to confirm"; reviewer resolves | DATA_MODEL §3, FEATURE_SPEC F5, ARCHITECTURE Flow C, judge script, proposal |
| 2 | No entry into `issue_blocked`; no exit from `escalated`; `pause` had no permission/reason codes | `issue_blocked` is system-driven (request sent / response uploaded); escalation is an attribute; pause/resume are manager-only Phase 1.5 actions with `HOLD_*`/`RESUME_*` codes | DATA_MODEL §2, ROLE matrix, REASON_CODE §2 |
| 3 | Fraud signal actors differed (reviewer vs all roles) | Reviewer-only acknowledge/dismiss | DATA_MODEL §4, ROLE matrix, FEATURE_SPEC F10 |
| 4 | `Y*` reason-code scope differed from taxonomy; "override" undefined; format rule didn't match codes | Exact reason-required action list; override = resolving with failing/needs-review recheck; family-prefix format + regex | REASON_CODE §1/§3, ROLE matrix, FEATURE_SPEC F6 |
| 5 | Trust test lists differed (6 vs 5, different T1) | Single canonical T1–T7 in SECURITY §4; benchmark references IDs | SECURITY §4, BENCHMARK §8 |
| 6 | Audit/data fields missing (`correlation_id`, `action_type`, `outcome`, request→issue link, `closed_at`, etc.) | Added; audit write is same-transaction, append-only by DB grant | DATA_MODEL §1/§8, SECURITY §5, ARCHITECTURE §3 |
| 7 | Public datasets can't measure discrepancy metrics | Metric-scope column; public sets are extraction-only and optional; licence classes provisional until terms captured | DATASET_REGISTER, BENCHMARK §3 |
| 8 | 60 vs 120 cases, no production plan, manual baseline unscoped | 120 cases from seeded generator; 12-case human-timed subset | BENCHMARK §3, proposal §7.1 |
| 9 | 11 separately deployed services is unrealistic for v1 | Logical modules in one Cloud Run service + jobs; Pub/Sub deferred | ARCHITECTURE §1 |

## B3) MVP scope additions (02 October 2026, Session 013)

Added to close gaps between the original proposal (`docs/CaseProof.pdf`) and the spec, and to make GenAI load-bearing for the 40% technical criterion.

| Addition | Why | Docs |
|---|---|---|
| F11 terms/policy-aware assessment + lender policy config | Proposal: "terms of the sale explain the difference", "each lender's checklist will determine what needs attention" | FEATURE_SPEC, DATA_MODEL, ARCHITECTURE, REASON_CODE (`REVIEW_OVERRIDE_TERMS_EXPLAINED`) |
| F12 line-item alignment + multi-POD aggregation | Real documents have line items and split shipments | FEATURE_SPEC, DATA_MODEL, ARCHITECTURE |
| F13 citation verification | Proposal: "quoted text will be checked against the original pages" | FEATURE_SPEC, SECURITY (C6, T8), BENCHMARK |
| F14 judge/demo access mode | Judges may use the deployed prototype | FEATURE_SPEC, SECURITY (C7, T9), ROLE matrix |
| F10 concrete detectors; anomaly = duplicate invoice | "Pattern anomaly" was untestable without history | FEATURE_SPEC, DATA_MODEL, BENCHMARK |
| F2 evidence viewer, F3 unit normalization, F4 request-item response tracking | UX score; adversarial bucket; proposal's "check whether they answer the original request" | FEATURE_SPEC, DATA_MODEL, BENCHMARK |
| P7 in-app evidence page | Proof visible to judges | FEATURE_SPEC, IMPLEMENTATION_SEQUENCE |

Cut order under schedule pressure: `docs/IMPLEMENTATION_SEQUENCE.md` §5.4.

## B4) Decision reports (05 October 2026, Session 014)

| Addition | Why | Docs |
|---|---|---|
| F7b internal audit report + counterparty decision report on close | Decided cases need a permanent, evidence-backed record for audit/review, and both bank and client need a satisfactory document | FEATURE_SPEC F7, DATA_MODEL (`DecisionReport`, §2a), ARCHITECTURE (`report-service`, Flow E) |
| Outcomes renamed `approved | rejected`; close requires `DECISION_*` code + rationale | Decision must be justified, not just recorded | FEATURE_SPEC F6, REASON_CODE §H/§I, ROLE matrix |
| C8 + T10/T11: write-once reports, hash verification, counterparty disclosure allow-list | Integrity for audit; no fraud tipping-off | SECURITY, BENCHMARK §4.4 |
| Report retention 730 / 365 days | Reports outlive source documents (180 days) | SECURITY §7 |

## C) Final freeze gate (go/no-go)

Go for coding (approved) when all are true:
1. All 6 blockers above are closed.
2. `docs/PROJECT_CONTEXT.md` reflects freeze-approved state.
3. `docs/SESSION_LOG.md` includes freeze approval entry.
4. Team confirms start at `docs/IMPLEMENTATION_SEQUENCE.md` Phase A.

## D) Recommended owners

1. Product owner
- Blockers 2 and 3.

2. Trust/security owner
- Blockers 5 and 6.

3. Benchmark owner
- Blocker 1.

4. Platform owner
- Blocker 4.
