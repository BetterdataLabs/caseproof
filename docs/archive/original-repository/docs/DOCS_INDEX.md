# CaseProof Documentation Index (Coding-Ready)

Date: 01 October 2026
Status: Active

Purpose:
- Provide a complete and unambiguous reading order before implementation starts.
- Reduce onboarding time for any contributor to under 30 minutes.

## 1) Mandatory reading order (before coding)

1. `docs/PROJECT_CONTEXT.md`
- Current phase, risks, and immediate priorities.

2. `docs/PrincipalEngineeringRules.md`
- Non-negotiable operating and quality rules.

3. `docs/APP_DESIGN_PLAN.md`
- Final product direction, scope, architecture decisions, and sign-off checks.

4. `docs/FEATURE_SPEC.md`
- Feature-level goals and acceptance criteria (MVP + Phase 1.5).

5. `docs/ARCHITECTURE_SPEC.md`
- Service boundaries, interfaces, data flows, and failure handling.

6. `docs/DATA_MODEL_STATE_MACHINE.md`
- Canonical entities, state transitions, and guard conditions.

7. `docs/ROLE_PERMISSION_MATRIX.md`
- RBAC and separation-of-duties boundaries.

8. `docs/SECURITY_TRUST_CONTROLS.md`
- BFSI trust controls and implementation evidence requirements.

9. `docs/REASON_CODE_TAXONOMY.md`
- Canonical reason codes for privileged and override actions.

10. `docs/DATASET_REGISTER.md`
- Frozen dataset names, versions, and license classes.

11. `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
- Comparator benchmark protocol and hard evidence expectations.

12. `docs/IMPLEMENTATION_SEQUENCE.md`
- Track-based build order and delivery gates.

## 2) Optional but useful context

- `docs/Problem.md` for challenge framing and strategic rationale.
- `docs/CaseProof_Review.md` for critical gaps and quality bar.
- `docs/DOCS_FREEZE_CHECKLIST.md` for latest approved vs fix-needed readiness status.
- `docs/deferred_demo/*` for proposal/video narrative after design gate.

## 3) Definition of “docs complete” for coding start

Docs are considered coding-ready when all are true:
1. MVP scope is frozen in `docs/FEATURE_SPEC.md`.
2. Service boundaries are frozen in `docs/ARCHITECTURE_SPEC.md`.
3. State machines and transition guards are frozen in `docs/DATA_MODEL_STATE_MACHINE.md`.
4. RBAC boundaries are frozen in `docs/ROLE_PERMISSION_MATRIX.md`.
5. Trust controls and evidence tests are frozen in `docs/SECURITY_TRUST_CONTROLS.md`.
6. Reason-code taxonomy is frozen in `docs/REASON_CODE_TAXONOMY.md`.
7. Dataset register is frozen in `docs/DATASET_REGISTER.md`.
8. Benchmark protocol and comparator setup are frozen in `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`.

## 4) Change control rule

Any change to one of the following must trigger updates in all linked docs:
- Feature scope (`FEATURE_SPEC`) -> update `ARCHITECTURE_SPEC`, `DATA_MODEL_STATE_MACHINE`, `BENCHMARK_EVIDENCE_PROTOCOL`.
- Role permissions (`ROLE_PERMISSION_MATRIX`) -> update `SECURITY_TRUST_CONTROLS`, `FEATURE_SPEC`.
- Reason codes (`REASON_CODE_TAXONOMY`) -> update `SECURITY_TRUST_CONTROLS`, `DATA_MODEL_STATE_MACHINE`, `ROLE_PERMISSION_MATRIX`.
- Dataset register (`DATASET_REGISTER`) -> update `BENCHMARK_EVIDENCE_PROTOCOL`, `PROJECT_CONTEXT`.
- Metrics (`BENCHMARK_EVIDENCE_PROTOCOL`) -> update `FEATURE_SPEC` and deferred proposal docs.
