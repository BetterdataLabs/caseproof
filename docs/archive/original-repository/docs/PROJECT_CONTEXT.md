# Project Context (Single Source of Truth)

Last updated: 2026-10-05 (Asia/Singapore)
Updated by: Claude Code

## Current phase

Docs freeze approved (v1.1 alignment pass complete); implementation kickoff.
Submission deadline: 17 October 2026 (12 days). No application code exists yet.
Demo documentation remains deferred until implementation proof gates pass.

## Current mission

Build a BFSI AI prototype that wins the competition by combining:
- Strong technical depth,
- Measurable impact,
- Credible production readiness,
- Clean user experience.

## Current product thesis

CaseProof is a trade-finance document discrepancy resolution copilot with assistive fraud intelligence that:
- detects and explains invoice vs delivery mismatches,
- decides whether each mismatch is explained by deal terms/lender policy or needs a request, with verified citations,
- surfaces evidence-linked fraud risk signals (assistive only),
- drafts reviewer-editable correction requests,
- tracks issue lifecycle with auditable evidence.

## Current status

- Challenge requirements extracted and clarified.
- Critical gap analysis completed.
- Principal-engineering operating rules formalized.
- Continuity protocol established.
- Proposal quality review completed for `docs/CaseProof.pdf`.
- App planning docs created for pros/cons, design, and feature finalization.
- Demo-focused docs moved to `docs/deferred_demo/` pending design sign-off.
- Fraud-intelligence scope added as a thin layer inside the same reviewer workflow.
- Post-MVP polish feature backlog drafted for UX and operational readiness.
- Executive control-tower concept added as Phase 1.5 (non-MVP) for portfolio oversight and intervention.
- Role-permission matrix drafted for reviewer, manager, and executive actions.
- Benchmark and evidence protocol drafted for hard-comparator scoring and trust control proof.
- Architecture, data/state, security/trust, implementation sequence, and docs index added for coding readiness.
- Docs freeze blockers closed (dataset register, reason taxonomy, deployment target, redaction, retention).
- Docs freeze status approved for coding start.
- v1.1 alignment pass resolved 9 cross-doc inconsistencies (see `docs/DOCS_FREEZE_CHECKLIST.md` §B2).
- MVP extended to F1–F14: terms/policy assessment, line-item alignment, citation verification, demo access; F10 detectors made concrete (see §B3).
- F7 extended with decision reports on close: write-once internal audit report + client-safe counterparty report; outcomes are `approved | rejected` with `DECISION_*` code + rationale (see §B4).

## Decided constraints

- Must use Google AI stack (Gemini/Gemma/approved agentic platform).
- Primary deployment target is Cloud Run (Firebase deferred).
- Must align implementation and narrative to judging weights (40/25/25/10).
- Must not produce new demo docs before design gate completion.

## Open questions

No blocker-level open questions for coding start.
Non-blocking product question:
1. Which executive KPIs should be prioritized first when Phase 1.5 begins?

## Top risks

1. Scope creep beyond document discrepancy resolution.
2. Weak KPI evidence despite impressive UX.
3. AI seen as non-essential rather than core differentiator.
4. Fraud false positives could reduce reviewer trust if signal calibration is weak.
5. Comparator runs may drift if dataset manifests are not strictly versioned.
6. Schedule: 15 days to submission with no code and MVP now F1–F14; follow the cut order in `docs/IMPLEMENTATION_SEQUENCE.md` §5.4 if Phase B2 slips past ~10 Oct.
8. LLM latency for alignment + assessment may exceed the 45s P95 target; mitigate with progressive UI and batching issues per call.
7. Synthetic-only discrepancy evidence may be read as overfit; mitigated by separate-seed holdout with disjoint templates.

## Next 3 actions (priority ordered)

1. Phase A: scaffold single Cloud Run app, schema incl. append-only `audit_events`, policy table, lender policy config, transactional audit helper; pass T1/T3/T4/T7.
2. Build the `CP_SYNTH_TRADE_V1` seeded generator early, covering the scenario list in `docs/BENCHMARK_EVIDENCE_PROTOCOL.md` §3.
3. Phase B + B2 vertical slice: upload -> extract -> align -> check -> assess (verified citations) -> draft -> send -> re-upload -> confirm -> close.

## Resume instructions for next contributor

1. Read `docs/APP_DESIGN_PLAN.md` first.
2. Follow `docs/DOCS_INDEX.md` mandatory reading order without skipping.
3. Begin with `docs/IMPLEMENTATION_SEQUENCE.md` Phase A.
