# CaseProof Proposal Revision Checklist (Must-Fix)

Date: 26 September 2026

Use this checklist to convert the current proposal into a high-scoring final version.

## A) Evidence and impact

- Add a baseline-vs-CaseProof table with measured values (not only targets).
- Add 4-way comparator scoreboard: manual vs rules-only vs LLM-only vs CaseProof.
- Include manual baseline methodology in one paragraph.
- Report holdout-set results separately from development-set results.
- Add at least one failure case and what was learned.
- Add fraud-signal precision/recall reporting for high-severity alerts.

## B) Differentiation

- Add explicit moat statement: issue lifecycle intelligence with evidence-backed closure.
- Show one judge-visible sequence: detected -> request sent -> correction received -> selective closure.
- Show assistive fraud-risk sequence in same flow: signal raised -> reviewer decision -> logged action.
- Explain why this is not equivalent to a generic document summarizer.

## C) Trust and BFSI readiness

- State reviewer remains final decision-maker.
- Add access-control and audit-trail statements.
- Add PII minimization/redaction behavior.
- Add limitations section (what V1 does not automate).
- Explicitly state: fraud signals are assistive only, no autonomous adjudication.
- Add role-permission matrix summary (reviewer vs manager vs executive controls).

## D) UX proof

- Include one screenshot/flow for reviewer queue and issue panel.
- Show evidence jump (finding -> source quote/page) in one click.
- Add one metric tied to usability (time-to-first-decision).
- Add one executive control-tower screenshot with live/paused/issue/escalated counters.

## E) Rubric mapping page

- Add one explicit page mapping each capability to 40/25/25/10 criteria.
- Ensure each rubric row has at least one measurable proof artifact.

## F) Polish features (if slide/demo time permits)

- Show SLA-aware queue prioritization and saved reviewer views.
- Demonstrate keyboard-first review actions for faster throughput.
- Include counterparty risk snapshot and reviewer feedback capture as roadmap.
- Include executive controls roadmap: prioritize/escalate/reassign with reason-coded audit trail.
