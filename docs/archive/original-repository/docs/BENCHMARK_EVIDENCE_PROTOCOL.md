# CaseProof Benchmark & Evidence Protocol

Date: 01 October 2026
Updated: 05 October 2026 (alignment pass — dataset roles, trust test IDs; F11–F13 metrics and generator coverage — Session 013; decision report metrics — Session 014)
Status: Frozen v1.1

Purpose:
- Produce hard, reproducible benchmark evidence that CaseProof is measurably superior.
- Prove differentiation via lifecycle closure outcomes, not feature claims.
- Prove BFSI trust readiness with explicit control and governance tests.

## 1) Evaluation principles

1. Compare against clear baselines on the same cases.
2. Measure quality, speed, trust, and operational impact together.
3. Report holdout results separately from development results.
4. Fail closed: if confidence is low, system routes to manual review.
5. No metric accepted without reproducible run artifacts.

## 2) Comparator systems (required)

All comparator runs must use identical case splits and labeling rules.

1. Manual baseline
- Reviewer performs process without CaseProof assistance.

2. Rules-only baseline
- Deterministic discrepancy checks only, no LLM assistance.

3. LLM-only baseline
- LLM reasoning/drafting without deterministic validation layer and without citation verification (F13).

4. CaseProof hybrid (target)
- Deterministic checks + AI alignment and terms/policy assessment + citation verification + fraud signals + reviewer control.

## 3) Dataset design and splits

Minimum evaluation corpus:
- 120 labeled discrepancy cases total, all from `CP_SYNTH_TRADE_V1` (60 with planted issues, 60 valid including partial-delivery-valid).
- Cases are produced by a seeded generator that renders invoice + proof-of-delivery PDFs and emits the label manifest in the same run; the seed and generator commit are recorded in the dataset manifest.
- Public datasets do **not** contain invoice/POD pairs, so they are used only for extraction-robustness metrics (field-level accuracy), never for discrepancy or fraud metrics. See `docs/DATASET_REGISTER.md` metric scope.

Generator scenario coverage (each scenario labeled in the manifest; every split contains every scenario):
- Clean valid cases.
- Partial delivery explained by PO/terms (label: `explained_by_terms`) and partial delivery not explained (label: `needs_request`).
- Within-tolerance differences (label: no issue).
- Line-item description variants requiring semantic alignment.
- Split shipments across 2–3 proof-of-delivery documents.
- Unit variants (dozen/pcs, g/kg).
- Total/arithmetic errors, reference and registration-number mismatches.
- Tamper artifacts (edited metadata, mismatched fonts on key fields).
- Identity mismatches vs the seeded counterparty registry.
- Exact and near-duplicate invoices across cases (requires seeded prior cases).
- Response documents for lifecycle tests (fixes one issue, leaves another).

Frozen dataset register:
- Dataset IDs, versions, and license classes are fixed in `docs/DATASET_REGISTER.md`.
- Only registered datasets may be used in benchmark evidence.

Required buckets:
1. Public benchmark documents (extraction robustness only; external credibility).
2. Synthetic trade-finance discrepancy cases (controlled scenario coverage).
3. Adversarial cases (OCR noise, tamper artifacts, unit/currency ambiguity, partial deliveries).
4. Trust-control cases (permission abuse attempts, invalid overrides, missing reason-code actions).

Recommended split:
- 60% development set
- 20% validation set
- 20% hidden holdout set

Holdout rule:
- Holdout labels and expected outcomes are hidden from builders until final report generation.
- Holdout is generated with a separate seed and a disjoint set of templates/counterparty names from dev/val, to reduce overfitting to generator patterns.

Human-timed subset:
- Manual-baseline and reviewer-time metrics (§4.3) require people, so they are measured on a fixed 12-case timed subset drawn from the holdout split (6 problematic, 6 valid), each case worked once manually and once with CaseProof by different reviewers.
- Automated comparators (rules-only, LLM-only, hybrid detection) run on the full split.

Mandatory run manifest fields:
- `dataset_ids[]`
- `dataset_versions[]`
- `dataset_license_classes[]`

## 4) Metric definitions (required scoreboard)

### 4.1 Discrepancy quality metrics

1. Issue recall
- Formula: `TP / (TP + FN)` for labeled discrepancy issues.

2. Issue precision
- Formula: `TP / (TP + FP)`.

3. False alarm rate on valid cases
- Formula: `valid_cases_with_any_false_alert / total_valid_cases`.

4. Critical miss rate
- Formula: `critical_FN / total_critical_issues`.

5. Assessment accuracy (F11)
- Formula: `correct_assessments / assessed_issues` against labels `explained_by_terms | needs_request`; report the confusion matrix. `unclear` counts as incorrect but is reported separately.
- Flagged-issue definition for metrics 1–4: an issue counts as an alert only if its assessment is `needs_request` or `unclear`. Issues assessed `explained_by_terms` are not alerts; if such an issue is labeled `needs_request`, it counts as a false negative.

6. Line-item alignment accuracy (F12)
- Formula: `correct_pairings / labeled_pairings`.

7. Citation verification rate (F13)
- Formula: `verified_quotes / total_quotes_emitted` (measures LLM grounding quality).
- Hard requirement: `unverified_quotes_displayed_as_evidence = 0` (trust test T8).

### 4.2 Fraud signal metrics

1. High-severity fraud precision
- Formula: `high_severity_TP / (high_severity_TP + high_severity_FP)`.

2. High-severity fraud recall
- Formula: `high_severity_TP / (high_severity_TP + high_severity_FN)`.

3. Fraud dismissal rate by reviewer
- Formula: `dismissed_fraud_signals / total_fraud_signals`.

4. Per-type precision/recall
- Report metrics 1–2 separately for `tamper`, `identity_inconsistency`, and `duplicate_invoice`.

### 4.3 Workflow and productivity metrics

1. Median reviewer time per case
- Measured from first open to final case decision.

2. Unnecessary request rate
- Formula: `requests_sent_without_true_unresolved_issue / total_requests_sent`.

3. Reopen rate
- Formula: `reopened_cases / closed_cases`.

4. Time-to-first-decision
- Time from case open to first reviewer action.

5. Draft edit distance
- Median normalized edit distance between `draft_text` and `sent_text` (lower = drafts more usable as-is). Hybrid vs LLM-only only.

6. Response tracking accuracy
- Formula: `correct_request_item_statuses / labeled_request_items` after response documents are applied.

### 4.4 Trust and governance metrics

1. Unauthorized action block rate
- Formula: `blocked_unauthorized_attempts / total_unauthorized_attempts` (attempts from T1, T2, T6, T7, T9).
- Target expectation: `100%`.

2. Reason-code compliance rate
- Formula: `privileged_actions_with_reason_code / total_privileged_actions`.
- Target expectation: `100%`.
- Reason code values must come from `docs/REASON_CODE_TAXONOMY.md`.

3. Audit completeness rate
- Formula: `events_with_required_audit_fields / total_events`.
- Target expectation: `100%`.

4. Reviewer adjudication integrity
- Formula: `cases_closed_by_reviewer_role / total_closed_cases`.
- Target expectation: `100%`.

5. Decision report completeness
- Formula: `closed_cases_with_both_reports_generated / total_closed_cases`.
- Target expectation: `100%`.

6. Decision report fidelity
- Internal report audit-trail event count and IDs equal the audit store up to the watermark; every issue has a verified citation or explicit override marker.
- Target expectation: `100%` of reports.

7. Counterparty disclosure compliance
- Formula: `counterparty_reports_with_zero_disallowed_fields / total_counterparty_reports` (automated scan, T10).
- Target expectation: `100%`.

## 5) Scoreboard format (publish in deck/demo)

Required table columns:
- Metric
- Manual baseline
- Rules-only
- LLM-only
- CaseProof hybrid
- Delta vs manual
- Delta vs best baseline

Reporting rules:
1. Separate development vs holdout result rows.
2. Include sample size (`n`) for each row.
3. Include 95% confidence interval where applicable.
4. Flag unmet targets in red and explain failure mode.

## 6) Evidence artifacts (must store per run)

For each benchmark run, store:
1. Run manifest (`run_id`, commit hash, config hash, model version).
2. Dataset manifest (split IDs, case IDs, label version).
3. Prediction outputs (discrepancy, fraud, decisions).
4. Timing/event logs for workflow metrics.
5. Audit event export for trust metrics.
5a. Decision reports for a sample of closed benchmark cases (counterparty PDFs only if they contain synthetic data).
6. Scoreboard output and confusion matrices.

Minimum path convention:
- `evidence/runs/<run_id>/manifest.json`
- `evidence/runs/<run_id>/predictions.jsonl`
- `evidence/runs/<run_id>/metrics.json`
- `evidence/runs/<run_id>/audit_extract.jsonl`

## 7) Moat-proof requirements (differentiation)

A run is only accepted as moat evidence if it includes:
1. Full lifecycle trace: detected -> request drafted -> response received -> selective closure/reopen -> decision -> decision reports.
2. Evidence linkage for every high-severity discrepancy/fraud signal.
3. Lower reopen/unnecessary-request rates than at least two baselines.

## 8) BFSI trust-control test suite (required)

Trust tests are defined once, as T1–T11 in `docs/SECURITY_TRUST_CONTROLS.md` §4. This protocol runs all of them; scenarios are sourced from `CP_TRUST_ATTACK_V1`.

Pass criteria:
- All trust tests pass on holdout environment before demo lock.

## 9) Release gates

### Gate A — Design freeze
- Metric formulas finalized.
- Split strategy finalized.
- Comparator definitions frozen.

### Gate B — Implementation readiness
- Benchmark harness produces run artifacts end-to-end.
- Trust-control tests integrated in CI checks.

### Gate C — Demo/proposal lock
- Holdout scoreboard completed.
- Moat-proof lifecycle trace captured.
- Trust metrics show zero critical control failures.

## 10) Ownership and cadence

Owners:
- Benchmark owner: responsible for dataset integrity and run reproducibility.
- Product owner: responsible for KPI relevance and target definitions.
- Trust owner: responsible for RBAC/audit control test coverage.

Cadence:
- Daily quick benchmark on development split.
- Twice-weekly full benchmark including trust tests.
- Final holdout run only at Gate C.
