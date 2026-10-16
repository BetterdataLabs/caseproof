# CaseProof Feature Specification (Design Freeze Candidate)

> **Historical design freeze.** Several Must items here were not built: PO/multi-line alignment (F11–F12), a fraud-signal layer and cross-case duplicate engine (F10), dual internal/client reports (F7), and the executive control tower (E1). The shipped contract is [ARCHITECTURE.md](../../../ARCHITECTURE.md) and the [current judge path](../../../JUDGE_SCRIPT.md).

Date: 26 September 2026
Updated: 05 October 2026 (alignment pass; F11–F14 + P7 added in Session 013; F7 decision reports in Session 014)
Status: Frozen v1.1

Priority model:
- Must (design-freeze MVP): F1-F14
- Should (polish): P1-P3, P7
- Could (polish/extension): P4-P6
- Phase 1.5 (executive extension): E1

Frozen scope decisions:
- `E1` remains Phase 1.5 and is excluded from MVP build gates.
- MVP includes reviewer-first workflow only (`F1-F14`).
- Cut order if schedule slips is defined in `docs/IMPLEMENTATION_SEQUENCE.md` §5.

Measurement protocol reference:
- All feature-level KPI measurement and comparator reporting must follow `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`.

Design references:
- Service architecture constraints: `docs/ARCHITECTURE_SPEC.md`.
- Data and transition rules: `docs/DATA_MODEL_STATE_MACHINE.md`.
- Security and governance controls: `docs/SECURITY_TRUST_CONTROLS.md`.
- Reason-code dictionary: `docs/REASON_CODE_TAXONOMY.md`.
- Dataset freeze list: `docs/DATASET_REGISTER.md`.

## F1 — Case Intake

Goal:
- Create a case and upload required documents.

Acceptance criteria:
- Reviewer can create a case with invoice + delivery files.
- Missing required file type is flagged before processing starts.
- Files are versioned within the case timeline.

## F2 — Field Extraction + Evidence Mapping

Goal:
- Extract key fields and preserve source provenance.

Acceptance criteria:
- Extracted fields include quantity, totals, reference numbers, entity identifiers.
- Each extracted value links to source page/snippet and bounding box.
- Low-confidence extraction is marked for review.
- Reviewer UI shows source documents side by side; selecting an issue, field, or citation scrolls to and highlights the exact region on the page.

## F3 — Discrepancy Detection Engine

Goal:
- Identify deterministic mismatches across documents.

Acceptance criteria:
- Quantity, totals, reference, and identifier mismatches are detected.
- Quantities are normalized to a base unit before comparison (e.g. dozen -> pcs, g -> kg) using a fixed unit table; unknown units produce `needs_review`, not a mismatch.
- Rule thresholds (e.g. quantity tolerance %) are read from the case's lender policy (F11), not hardcoded.
- Each discrepancy has a severity level and rule ID.
- Findings are reproducible from stored inputs.

## F4 — AI-Assisted Request Drafting

Goal:
- Draft precise correction requests for reviewer editing.

Acceptance criteria:
- Draft references concrete unresolved issues only.
- Draft excludes issues already resolved.
- Reviewer can edit before send; sent version is logged.
- Request is stored as one request item per issue it covers.
- When a response document arrives, each request item is marked `addressed`, `partially_addressed`, or `outstanding` based on the recheck of its issue, and the reviewer sees which items are still open.
- If the LLM is unavailable, a deterministic template draft is produced instead.

## F5 — Issue Lifecycle State Machine

Goal:
- Track issue progression over time.

Acceptance criteria:
- States supported: open, resolved, reopened.
- New uploads trigger re-evaluation of only relevant issues.
- Re-evaluation may reopen a resolved issue, and marks open issues whose check now passes as "ready to confirm"; only the reviewer resolves.
- Case timeline shows who/what changed issue state.

## F6 — Reviewer Decision and Override

Goal:
- Keep human control explicit.

Acceptance criteria:
- Reviewer resolves each issue as `verified` (check passes) or `override` (check still fails or needs review, with `REVIEW_OVERRIDE_*` reason code). Rejecting a finding as a false positive is an override.
- Reviewer closes the case with outcome `approved` (no unresolved issues) or `rejected` (unresolved issues allowed); all fraud signals must be acknowledged or dismissed first.
- Closing requires a decision reason code (`DECISION_APPROVED_*` or `DECISION_REJECTED_*`) and a written decision rationale (minimum 30 characters); both appear in the decision reports (F7).
- Final case decision cannot be auto-completed by AI or the system.

## F7 — Case Summary and Decision Reports

Goal:
- Give every decided case a permanent, self-contained record that justifies the decision with evidence, usable later for internal review, audit, or dispute — and give the client a clear, fair explanation of the outcome.

### F7a — Interim case summary (any time before close)

Acceptance criteria:
- Summary includes resolved and unresolved issues separately, with evidence references and action history.
- Marked "interim — not a decision".
- Export action is logged.

### F7b — Decision reports (generated automatically on close)

When a case is closed as `approved` or `rejected`, the system generates two reports from the same snapshot of case state and audit trail:

**1. Internal audit report (bank)** — PDF + machine-readable JSON. Contents:
- Decision header: case ID, outcome, decision reason code, reviewer's written rationale, reviewer and timestamp, lender policy ID + version.
- Document inventory: every document and version considered, with upload time, uploader, and SHA-256 hash.
- Issue register: for each issue — rule ID, severity, what was compared (values from each document), AI assessment + rationale, verified citations (quote text, document, page) and cropped page-region images, recheck history, final resolution (`verified` or `override` + reason code + note), who resolved and when.
- Line-item alignment table with any reviewer corrections.
- Fraud signals: type, detector, severity, evidence, reviewer disposition (acknowledged / dismissed + reason code).
- Correction requests: draft vs sent text, request items, and response status per item, with the response documents that addressed them.
- Interventions (priority, escalation, reassignment, pause) with actor, role, and reason code.
- Full chronological audit trail up to the decision, including blocked attempts.
- AI provenance: model name/version, prompt template versions, and fallback usage per step.
- Integrity block: report SHA-256, audit watermark (last event ID included) and event count, generation time, template version.

**2. Counterparty decision report (client)** — PDF. Contents:
- Decision, date, and a client-facing explanation of the grounds.
- Documents received and considered (names, dates, versions).
- Each issue raised: what did not match, quoted evidence from the client's own documents, what was requested, and how it was resolved.
- If `rejected`: the unresolved items and what documents or corrections would address each one.
- Request and response history (dates and items).
- Reference ID and report hash so the client and bank can confirm they hold the same version.
- Must NOT contain: fraud signals or fraud-related reasons, internal notes, AI assessment internals, reviewer names (team/role only), interventions, blocked attempts, or other parties' sensitive data. When the decision reason code is `DECISION_REJECTED_FRAUD_CONCERN`, the client report states the generic ground "documents did not meet verification requirements".

Shared acceptance criteria:
- Both reports are generated within 5 minutes of close; until then the case shows "report pending". Failed generation retries automatically and alerts after 3 failures. The decision itself is never rolled back by a report failure.
- Reports are built only from stored state up to the audit watermark, so regenerating from the same data produces identical content.
- Reports are write-once: stored with a create-only precondition; any regeneration creates a new version and never overwrites. Each generation and download is audited.
- Report hash is recorded in the `decision_report_generated` audit event and printed in the report.
- Every issue in the internal report has at least one verified citation or an explicit "no verifiable citation — resolved by override" marker.
- Redaction (C5) applies to both; identifiers are partially masked (last 4) so mismatches stay visible.
- Reports remain readable after source documents are purged (self-contained evidence; see retention policy).

## F8 — Security and Access Control

Goal:
- Restrict data access to authorized reviewers.

Acceptance criteria:
- Authenticated access required for all case operations.
- User can view only authorized cases.
- Access and permission changes are auditable.

## F9 — Audit Logging

Goal:
- Preserve an immutable activity trail.

Acceptance criteria:
- Logs include upload, extraction, discrepancy detection, draft generation, edits, sends, and state changes.
- Each log entry includes timestamp, actor, action, and case ID.
- Logs are queryable for post-incident review.

## F10 — Assistive Fraud Risk Intelligence

Goal:
- Surface fraud risk cues within the same reviewer workflow without auto-adjudication.

Acceptance criteria:
- Fraud signals include exactly three types in v1, each with a concrete detection method:
  - `tamper`: PDF metadata checks (modification date after creation date, producer/creator in a known-editor list, incremental-update count) and font inconsistency on key fields (amount/quantity/ID set in a different font from surrounding text).
  - `identity_inconsistency`: company name / registration number differs across documents in the case, or differs from the seeded counterparty registry.
  - `duplicate_invoice` (the v1 pattern anomaly): same counterparty + invoice number already exists in another case (exact), or same buyer, amount within 1%, date within 7 days, and invoice number edit distance <= 2 (near-duplicate). Evidence links to the other case.
- Every fraud signal includes severity, reason text, and evidence/source reference.
- Reviewer can acknowledge each fraud signal, or dismiss it with a `FRAUD_DISMISS_*` reason code. Only reviewers change signal status.
- Fraud signals cannot auto-close, auto-reject, or auto-approve a case.
- Fraud signal actions are logged in the immutable audit trail.

## F11 — Terms- and Policy-Aware Discrepancy Assessment

Goal:
- Decide whether each deterministic mismatch is explained by the deal terms or lender policy, or needs a correction request. This is the core reasoning step the rules engine cannot do alone.

Acceptance criteria:
- Each case is linked to one lender policy (config file: required document types, enabled rules, per-rule tolerances and severities, checklist items with IDs and text).
- Mismatches inside a policy tolerance do not open an issue (deterministic).
- For every open issue, Gemini receives the issue, the relevant extracted fields, purchase order/terms text if present, and the lender checklist, and returns an assessment: `explained_by_terms`, `needs_request`, or `unclear`, with a rationale and at least one citation (quoted clause or checklist item ID).
- Assessment never changes issue status. `explained_by_terms` issues are grouped separately and offer a one-click resolve that pre-fills reason code `REVIEW_OVERRIDE_TERMS_EXPLAINED`; the reviewer still decides.
- Correction drafts (F4) include only `needs_request` and `unclear` issues by default and cite the checklist item for each request item.
- If the LLM is unavailable or citations fail verification (F13), assessment is `unclear`.

## F12 — Line-Item Alignment and Multi-Delivery Aggregation

Goal:
- Compare invoices and delivery notes at line level even when descriptions differ and deliveries are split.

Acceptance criteria:
- Line items are extracted from invoice, each proof of delivery, and purchase order (if present).
- Gemini proposes an alignment between invoice lines and delivery lines (handles description variants such as "Cotton T-shirt M" vs "T-SHIRT COTTON MED"), each pairing with a confidence and quoted descriptions.
- Deterministic rules then check aligned pairs: quantities summed across all proof-of-delivery documents per invoice line, unit-normalized (F3), compared within policy tolerance.
- Unaligned invoice lines open a "no delivery evidence" issue; unaligned delivery lines open an "undelivered/unbilled item" issue.
- Low-confidence alignments are marked `needs_review`; reviewer can correct a pairing, which triggers recheck and is audited.

## F13 — Citation Verification for AI Outputs

Goal:
- Guarantee that every quote shown to the reviewer actually exists in the source documents.

Acceptance criteria:
- Every quote in an AI explanation, assessment (F11), alignment (F12), or draft (F4) carries a `document_id` + page reference.
- Each quote is checked against the extracted page text after normalization (case, whitespace, punctuation). Match -> `verified`; otherwise `unverified`.
- Unverified quotes are never displayed as evidence; the output is flagged "unverified citation", and an F11 assessment that relies only on unverified quotes becomes `unclear`.
- Verification results are stored and reported as a benchmark metric.

## F14 — Judge and Demo Access Mode

Goal:
- Let judges use the deployed prototype in under a minute without setup, without breaking it for others.

Acceptance criteria:
- A `demo` deployment flag enables: one demo account per role and a role switcher on the sign-in page.
- Demo environment is pre-seeded with a guided "start here" case plus a set of cases covering each issue and fraud type.
- "Start fresh demo case" clones the guided case into a new case owned by the current user, so judges never mutate shared cases.
- The team can reset the whole demo environment via an offline job (recreate database + reseed); there is no in-app reset.
- Demo features are disabled when the flag is off; this is verified by a trust test.

## P1 — Priority Queue and SLA Timers (Should)

Goal:
- Help reviewers work highest-risk and oldest cases first.

Acceptance criteria:
- Case queue supports sorting by severity, fraud-risk band, and age.
- Each case displays SLA countdown and overdue status.
- Queue decisions are consistent across reloads and users with same role.

## P2 — Saved Views and Smart Filters (Should)

Goal:
- Reduce navigation time for repetitive review operations.

Acceptance criteria:
- Reviewer can save and reuse filter presets.
- Filters support issue status, severity, counterparty, and fraud-risk band.
- Default view loads in under 2 seconds on expected MVP dataset size.

## P3 — Keyboard-First Reviewer Actions (Should)

Goal:
- Improve throughput for high-volume reviewers.

Acceptance criteria:
- Keyboard shortcuts exist for next issue, open evidence, confirm resolution, and save.
- Shortcut actions are visible in help overlay.
- All shortcut-triggered actions are audit logged identically to mouse actions.

## P4 — Counterparty Risk Snapshot (Could)

Goal:
- Give reviewer quick historical context before final decision.

Acceptance criteria:
- Side panel shows recent discrepancy count, reopen rate, and fraud-signal frequency.
- Snapshot refreshes on case open without blocking core workflow.

## P5 — Reviewer Feedback Loop (Could)

Goal:
- Capture learning signals for future quality tuning.

Acceptance criteria:
- Reviewer can label false positive/false negative for discrepancy and fraud signal.
- Feedback records are exportable for offline evaluation.

## P6 — Collaboration Notes and Assignment (Could)

Goal:
- Support handoff between reviewers without context loss.

Acceptance criteria:
- Reviewer can leave timestamped notes tied to case or issue.
- Case owner/assignee changes are tracked and auditable.

## P7 — In-App Evidence Page (Should)

Goal:
- Show judges and stakeholders the proof without leaving the app.

Acceptance criteria:
- Read-only page shows the latest benchmark scoreboard (`metrics.json` from a selected `run_id`), comparator table, and trust-test T1–T11 pass/fail results.
- Each number links to its run ID and commit hash.

## E1 — Executive Control Tower Dashboard (Phase 1.5)

Goal:
- Provide high-level operational visibility and controlled intervention tools for executive/operations leadership.

Acceptance criteria:
- Dashboard shows counts and trends for live, paused, issue-blocked, escalated (attribute), and overdue cases.
- Dashboard supports drill-down by team, counterparty, risk band, and SLA breach state.
- Authorized executive can run three actions only: prioritize case, escalate to channel, reassign owner. Manager can additionally pause/resume a case.
- Every intervention requires reason code and is written to immutable audit logs.
- Executive actions cannot auto-approve, auto-reject, or close a case without reviewer decision.

Role and permission reference:
- Enforce action boundaries exactly as specified in `docs/ROLE_PERMISSION_MATRIX.md`.
