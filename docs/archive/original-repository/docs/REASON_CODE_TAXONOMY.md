# CaseProof Reason-Code Taxonomy (Frozen v1.1)

Date: 01 October 2026
Updated: 05 October 2026 (alignment pass — added HOLD/RESUME families, fixed format rule; REVIEW_OVERRIDE_TERMS_EXPLAINED for F11; DECISION_* family for case close)
Status: Frozen for coding start

Purpose:
- Standardize reason codes for privileged and decision-affecting actions.
- Ensure consistent audit analytics and governance reporting.

## 1) Format standard

Reason code format:
- `<FAMILY>_<DETAIL>` where `<FAMILY>` is one of the family prefixes in §2 and `<DETAIL>` is one or more uppercase `_`-separated tokens.
- Regex: `^(PRIORITY|ESCALATION|REASSIGNMENT|HOLD|RESUME|FRAUD_DISMISS|REVIEW_OVERRIDE|DECISION_APPROVED|DECISION_REJECTED)_[A-Z0-9_]+$`

Example:
- `ESCALATION_SLA_BREACH_HIGH`

## 2) Action families

Each family is valid only for the listed `action_type`. A code from the wrong family is rejected.

### A) `PRIORITY_*` — `prioritize_case`

1. `PRIORITY_SLA_BREACH`
2. `PRIORITY_HIGH_RISK_SIGNAL`
3. `PRIORITY_COUNTERPARTY_CRITICAL`
4. `PRIORITY_MANUAL_OVERRIDE_REVIEW`

### B) `ESCALATION_*` — `escalate_channel`

1. `ESCALATION_SLA_BREACH_HIGH`
2. `ESCALATION_COMPLIANCE_REVIEW_REQUIRED`
3. `ESCALATION_FRAUD_SIGNAL_HIGH`
4. `ESCALATION_CUSTOMER_BLOCKED_RESPONSE`

### C) `REASSIGNMENT_*` — `reassign_owner`

1. `REASSIGNMENT_WORKLOAD_BALANCING`
2. `REASSIGNMENT_SKILL_MISMATCH`
3. `REASSIGNMENT_ABSENCE_COVERAGE`
4. `REASSIGNMENT_MANAGER_DIRECTIVE`

### D) `HOLD_*` — `pause_case` (Phase 1.5)

1. `HOLD_AWAITING_INTERNAL_APPROVAL`
2. `HOLD_COMPLIANCE_INVESTIGATION`
3. `HOLD_COUNTERPARTY_REQUEST`

### E) `RESUME_*` — `resume_case` (Phase 1.5)

1. `RESUME_HOLD_CONDITION_CLEARED`
2. `RESUME_MANAGER_DIRECTIVE`

### F) `FRAUD_DISMISS_*` — `dismiss_fraud_signal`

1. `FRAUD_DISMISS_FALSE_POSITIVE`
2. `FRAUD_DISMISS_INSUFFICIENT_EVIDENCE`
3. `FRAUD_DISMISS_CONTEXT_RESOLVED`

### G) `REVIEW_OVERRIDE_*` — `resolve_issue` when `recheck_status != passing`

1. `REVIEW_OVERRIDE_POLICY_EXCEPTION` — mismatch is real but acceptable under lender policy (e.g. permitted partial delivery).
2. `REVIEW_OVERRIDE_EVIDENCE_CONFLICT` — rule finding is a false positive (e.g. extraction error).
3. `REVIEW_OVERRIDE_MANUAL_CONFIRMATION` — reviewer verified out-of-band (e.g. phone confirmation).
4. `REVIEW_OVERRIDE_TERMS_EXPLAINED` — mismatch is explained by deal terms or lender policy (pre-filled when the F11 assessment is `explained_by_terms` with a verified citation; reviewer must still submit).

### H) `DECISION_APPROVED_*` — `close_case` with outcome `approved`

1. `DECISION_APPROVED_ALL_VERIFIED` — every issue resolved as `verified` (or no issues).
2. `DECISION_APPROVED_WITH_EXCEPTIONS` — at least one issue resolved by override (validated: rejected if no override exists).

### I) `DECISION_REJECTED_*` — `close_case` with outcome `rejected`

1. `DECISION_REJECTED_UNRESOLVED_DISCREPANCY` — material discrepancies remain after correction requests.
2. `DECISION_REJECTED_NO_RESPONSE` — counterparty did not respond within the allowed time.
3. `DECISION_REJECTED_POLICY_INELIGIBLE` — transaction does not meet lender policy regardless of documents.
4. `DECISION_REJECTED_FRAUD_CONCERN` — fraud signals not cleared. **Never shown to the counterparty**; client report uses a generic ground.

Client-facing wording for each `DECISION_*` code lives alongside the codes in `config/reason_codes.yaml`.

## 3) Mandatory usage rules

1. Reason code is required for exactly these actions:
- `prioritize_case`, `escalate_channel`, `reassign_owner`, `pause_case`, `resume_case`,
- `dismiss_fraud_signal`,
- `resolve_issue` with `resolution_type = override`,
- `close_case` (plus mandatory `decision_rationale` text).

2. Not required for: `resolve_issue` (verified), `reopen_issue`, `acknowledge_fraud_signal`, `send_correction_request`, `add_note`, `export_summary`, `download_decision_report`.

3. Free-text `reason_note` is optional but encouraged.

4. Missing, unknown, or wrong-family codes are rejected at API validation and audited with `outcome = blocked`.

## 4) Audit mapping requirements

Each reasoned action must log:
- `reason_code`
- `reason_note` (nullable)
- `actor_role`
- `action_type`
- `case_id`
- `timestamp`

## 5) Implementation note

Ship this taxonomy as a single config file (e.g. `config/reason_codes.yaml`: family → action_type → codes) loaded at startup; API validation and UI dropdowns both read from it.

## 6) Change control

Any taxonomy change requires updates to:
1. `docs/ROLE_PERMISSION_MATRIX.md`
2. `docs/SECURITY_TRUST_CONTROLS.md`
3. `docs/DATA_MODEL_STATE_MACHINE.md`
4. `docs/SESSION_LOG.md`
