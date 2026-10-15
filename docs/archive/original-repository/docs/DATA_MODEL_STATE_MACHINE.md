# CaseProof Data Model and State Machine

Date: 01 October 2026
Updated: 05 October 2026 (alignment pass — Session 012; F11–F14 entities — Session 013; decision reports — Session 014)
Status: Frozen v1.1

## 1) Canonical entities

1. `User`
- `user_id`, `role` (`reviewer | manager | executive`), `team_id`, `status`, `is_demo`.

2. `Case`
- `case_id`, `case_status`, `case_outcome` (nullable until closed: `approved | rejected`), `decision_reason_code`, `decision_rationale`, `decided_by`, `report_status` (`not_applicable | pending | generated | failed`), `priority`, `owner_user_id`, `team_id`, `counterparty_id`, `lender_policy_id`, `lender_policy_version`.
- `invoice_number`, `invoice_amount`, `invoice_date` (denormalized from latest invoice extraction; used for duplicate detection, F10).
- `cloned_from_case_id` (nullable; demo clones, F14).
- `escalation_channel` (nullable), `escalated_at` (nullable) — escalation is an attribute, not a status (see §2).
- `status_before_pause` (nullable; set only while `paused`).
- `created_at`, `updated_at`, `closed_at` (nullable; drives retention windows).

3. `Document`
- `document_id`, `case_id`, `document_type` (`invoice | proof_of_delivery | purchase_order`), `version_no` (per `case_id` + `document_type`), `storage_uri`, `uploaded_by`, `uploaded_at`.

4. `ExtractionField`
- `field_id`, `case_id`, `document_id`, `field_name`, `field_value`, `confidence`, `source_ref` (page + bounding box/snippet).
- `needs_review` (true when `confidence` is below the configured threshold).

5. `LineItem` (F12)
- `line_item_id`, `case_id`, `document_id`, `line_no`, `description`, `quantity`, `unit`, `quantity_base` (unit-normalized), `unit_price`, `amount`, `confidence`, `source_ref`.

6. `LineAlignment` (F12)
- `alignment_id`, `case_id`, `invoice_line_item_id`, `delivery_line_item_ids[]` (one invoice line may map to lines across several PODs), `confidence`, `source` (`llm | reviewer`), `needs_review`.

7. `Issue`
- `issue_id`, `case_id`, `issue_type` (`quantity_mismatch | total_mismatch | reference_mismatch | identifier_mismatch | no_delivery_evidence | unbilled_delivery | missing_document`), `severity` (`high | medium | low`), `rule_id`, `status`.
- `alignment_id` (nullable; line-level issues).
- `assessment` (`explained_by_terms | needs_request | unclear`), `assessment_rationale`, `assessment_source` (`llm | fallback`) — F11; never changes `status`.
- `evidence_field_ids[]` — the `ExtractionField` rows the rule compared.
- `recheck_status` (`failing | passing | needs_review`) — latest deterministic re-evaluation result.
- `resolution_type` (nullable: `verified | override`), `resolution_reason_code` (required when `override`).
- `opened_at`, `resolved_at` (nullable), `resolved_by` (nullable).

8. `FraudSignal`
- `signal_id`, `case_id`, `signal_type` (`tamper | identity_inconsistency | duplicate_invoice`), `detector_id` (e.g. `tamper.metadata_moddate`, `dup.near_match`), `severity`, `confidence`, `status`, `reason_text`, `evidence_ref`.
- `related_case_id` (nullable; duplicate_invoice).
- `actioned_by` (nullable), `reason_code` (required when `dismissed`).

9. `CorrectionRequest`
- `request_id`, `case_id`, `draft_text`, `sent_text`, `draft_source` (`llm | template_fallback`), `draft_edit_distance` (normalized edit distance draft -> sent; benchmark metric), `sent_by`, `sent_at`.

10. `RequestItem` (F4 response tracking)
- `request_item_id`, `request_id`, `issue_id`, `checklist_item_id` (nullable), `item_text`, `response_status` (`outstanding | partially_addressed | addressed`), `updated_at`.

11. `Citation` (F13)
- `citation_id`, `owner_type` (`issue_explanation | assessment | alignment | draft`), `owner_id`, `document_id`, `page_no`, `quote_text`, `verification_status` (`verified | unverified`), `checked_at`.
- Checklist-item citations reference `checklist_item_id` instead of a document and are verified by ID lookup.

12. `LenderPolicy` (F11; config-backed)
- `lender_policy_id`, `version`, `content_hash`, `loaded_at`. Content (required doc types, enabled rules, tolerances, severities, checklist items) lives in `config/lender_policies/<id>.yaml`; cases pin the version they were evaluated with.

13. `Counterparty` (F10 identity registry; seeded)
- `counterparty_id`, `legal_name`, `registration_number`, `country`, `aliases[]`.

13a. `DecisionReport` (F7b)
- `report_id`, `case_id`, `report_type` (`internal_audit | counterparty`), `format` (`pdf | json`), `version_no`, `storage_uri`, `sha256`.
- `audit_watermark_event_id`, `audit_event_count`, `lender_policy_version`, `template_version`, `model_versions_json`.
- `status` (`pending | generated | failed`), `attempts`, `generated_at`.

14. `InterventionAction` (Phase 1.5)
- `action_id`, `case_id`, `action_type`, `actor_id`, `actor_role`, `reason_code`, `reason_note` (nullable), `created_at`.

15. `AuditEvent`
- `event_id`, `case_id` (nullable only for non-case events, e.g. login or retention summary), `event_type`, `action_type`, `outcome` (`committed | blocked`), `actor_id`, `actor_role`, `reason_code` (nullable), `reason_note` (nullable), `before_json`, `after_json`, `correlation_id`, `timestamp`.

System-originated events use `actor_role = system` and a fixed service `actor_id`.

## 2) Case state model

Allowed `case_status` values:
1. `live` — active; reviewer is working the case.
2. `issue_blocked` — correction request sent; waiting on counterparty response.
3. `paused` — operational hold placed by a manager (Phase 1.5).
4. `closed` — terminal; reviewer decision recorded in `case_outcome`.

Escalation is **not** a status. `escalation_channel` is set by an escalation action and a case can be escalated in any non-closed status. Dashboards count escalated cases as `escalation_channel IS NOT NULL AND case_status != closed`.

Allowed transitions:

| From | To | Actor | Trigger / guard |
|---|---|---|---|
| (new) | `live` | reviewer, manager | Case created with ≥1 invoice and ≥1 proof of delivery. |
| `live` | `issue_blocked` | system | Correction request sent referencing ≥1 unresolved issue. |
| `issue_blocked` | `live` | system | New document version uploaded to the case. |
| `live`, `issue_blocked` | `paused` | manager (Phase 1.5) | Reason code `HOLD_*` required; stores `status_before_pause`. |
| `paused` | `status_before_pause` | manager (Phase 1.5) | Reason code `RESUME_*` required; clears `status_before_pause`. |
| `live`, `issue_blocked` | `closed` | reviewer only | Close guard below. |

Close guard:
- No `FraudSignal` in `active` status (each must be acknowledged or dismissed).
- `case_outcome = approved` additionally requires zero issues in `open` or `reopened`, and `decision_reason_code` from `DECISION_APPROVED_*`.
- `case_outcome = rejected` may close with unresolved issues; requires `decision_reason_code` from `DECISION_REJECTED_*`. Unresolved issues are listed as rejection grounds in the decision reports (F7b).
- `decision_rationale` is required (min 30 characters).
- On commit, `report_status` becomes `pending` and decision report generation is queued (§2a).
- `paused` cases cannot be closed; resume first.
- Uploads to a `closed` case are rejected (v1 has no case reopen).

## 2a) Decision report lifecycle

| From | To | Actor | Trigger / guard |
|---|---|---|---|
| `not_applicable` | `pending` | system | Case closed. |
| `pending` | `generated` | system | Both reports (internal PDF+JSON, counterparty PDF) stored and hashes recorded. |
| `pending` | `failed` | system | 3 failed attempts; alert raised; retry job may move back to `pending`. |

Rules:
- Report content is derived only from rows and `AuditEvent`s up to `audit_watermark_event_id` (the `case_closed` event).
- Report objects are write-once; regeneration creates `version_no + 1` and is audited.
- Report generation never changes `case_status` or `case_outcome`.

## 3) Issue state model

Allowed `issue.status` values:
1. `open`
2. `resolved`
3. `reopened`

Allowed transitions:

| From | To | Actor | Guard |
|---|---|---|---|
| (new) | `open` | system | Rules engine finding. |
| `open`, `reopened` | `resolved` (`verified`) | reviewer only | `recheck_status = passing`. No reason code. |
| `open`, `reopened` | `resolved` (`override`) | reviewer only | `recheck_status` is `failing` or `needs_review`; reason code `REVIEW_OVERRIDE_*` required. |
| `resolved` | `reopened` | system | New document version in scope of the issue AND recheck returns `failing`. |
| `resolved` | `reopened` | reviewer | Any time before case close; no reason code. |

Re-evaluation behaviour (Flow C):
- On a new document version, only issues whose `evidence_field_ids` came from that `document_type` are rechecked.
- The system only updates `recheck_status` and may reopen. **It never resolves an issue.** When an open issue's recheck turns `passing`, the UI shows it as "ready to confirm" and the reviewer confirms with one action (bulk confirm allowed).
- Rejecting a rule finding as a false positive is a `resolved (override)` with `REVIEW_OVERRIDE_EVIDENCE_CONFLICT`.
- An issue assessed `explained_by_terms` (F11) is resolved by the reviewer as `override` with `REVIEW_OVERRIDE_TERMS_EXPLAINED` (pre-filled in the UI). The assessment alone never resolves it.
- After each recheck, `RequestItem.response_status` for that issue is updated: `addressed` if the issue's recheck passes, `partially_addressed` if the mismatch shrank but still fails, else `outstanding`.

## 4) Fraud signal lifecycle

Allowed `fraud_signal.status` values:
1. `active`
2. `acknowledged`
3. `dismissed`

Allowed transitions:
- `active -> acknowledged` (reviewer only; no reason code)
- `active -> dismissed` (reviewer only; reason code `FRAUD_DISMISS_*` required)

Guard conditions:
- Fraud signal status changes never change issue or case status.
- Manager/executive may view signals and cite them in escalation reasons, but cannot change signal status.

## 5) Action types

Reviewer action types (MVP):
- `create_case`, `upload_document`, `resolve_issue`, `reopen_issue`, `correct_alignment`, `send_correction_request`, `acknowledge_fraud_signal`, `dismiss_fraud_signal`, `close_case`, `export_summary`, `download_decision_report`, `add_note`.

Demo-only action type (F14; rejected when demo flag is off):
- `clone_demo_case` — reviewer, manager.

Intervention action types (`InterventionAction.action_type`, Phase 1.5):
1. `prioritize_case` — manager, executive
2. `escalate_channel` — manager, executive
3. `reassign_owner` — manager, executive
4. `pause_case` — manager only
5. `resume_case` — manager only

Forbidden for manager/executive/system:
- `resolve_issue`, `close_case`, `dismiss_fraud_signal`, `acknowledge_fraud_signal`.

## 6) Referential integrity rules

1. Every `Document`, `Issue`, `FraudSignal`, `CorrectionRequest` belongs to exactly one `Case`.
2. Every `RequestItem` references a `CorrectionRequest` and an `Issue` in the same case.
3. Every `LineAlignment` references line items from documents in the same case.
4. Every `Citation` with a `document_id` references a document in the owner's case.
5. Every `AuditEvent` references one actor; it references one `Case` unless it is a non-case event.
6. Every `InterventionAction` has an `AuditEvent` with the same `correlation_id`.

## 7) Index and query requirements

Minimum indexes:
1. `Case(case_status, priority, updated_at)` for queue views.
2. `Issue(case_id, status, severity)` for issue panels.
3. `FraudSignal(case_id, severity, status)` for risk panels.
4. `AuditEvent(case_id, timestamp)` for timeline rendering.
5. `AuditEvent(outcome, timestamp)` for blocked-attempt queries.
6. `InterventionAction(case_id, created_at)` for governance review.
7. `Case(counterparty_id, invoice_number)` and `Case(invoice_amount, invoice_date)` for duplicate-invoice detection.
8. `Citation(owner_type, owner_id)` for evidence rendering.
9. `DecisionReport(case_id, report_type, version_no)` unique.

## 8) Audit write rules (non-negotiable)

- Every mutation (system or human) writes one `AuditEvent` with all fields in §1.15.
- The audit insert runs **in the same database transaction** as the mutation; if it fails, the mutation rolls back (C4).
- Blocked attempts (authorization or guard failure) write an `AuditEvent` with `outcome = blocked`. If that write fails, the request still fails closed.
- `audit_events` is append-only: the application DB role has INSERT/SELECT only (no UPDATE/DELETE); retention purge uses a separate role.
- `reason_code` is non-null whenever `docs/REASON_CODE_TAXONOMY.md` §3 requires one.

## 9) Data retention (prototype baseline)

1. Retention windows follow `docs/SECURITY_TRUST_CONTROLS.md` §7, keyed on `Case.closed_at` and `AuditEvent.timestamp`. Decision reports outlive source documents and therefore embed their evidence.
2. Benchmark artifacts retained per run for reproducibility.
3. Redaction policy applies to exported summaries and model-bound payloads.

## 10) Source-of-truth links

- Feature behavior: `docs/FEATURE_SPEC.md`
- Role boundaries: `docs/ROLE_PERMISSION_MATRIX.md`
- Trust controls: `docs/SECURITY_TRUST_CONTROLS.md`
- Evidence metrics: `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
- Reason code dictionary: `docs/REASON_CODE_TAXONOMY.md`
