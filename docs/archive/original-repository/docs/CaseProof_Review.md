# CaseProof Proposal Review (Fact-Based, Critical)

Review scope: `docs/CaseProof.pdf` (2 pages, dated 24 September 2026)

## Verdict (blunt)

The proposal is coherent and credible for a **hackathon prototype**, but currently too light on proof and differentiation to reliably win against stronger teams. It is strongest on workflow clarity and weakest on evidence depth, defensibility, and judge-facing impact proof.

## What works (facts that support it)

1. **Clear user + workflow focus**
   - The proposal focuses on a concrete operational task: reconciling invoice and proof-of-delivery mismatches in financing reviews.
   - It defines a specific user responsibility boundary: reviewer remains decision-maker.

2. **Grounded problem narrative**
   - Uses concrete examples (100 invoiced vs 80 delivered) and real-world process conditions (documents must be in order for fast processing).
   - Includes citations to named institutions and a case-study data point (38% returns outside network vs 6% inside).

3. **Practical first-version scope**
   - V1 constraints are explicit: English PDFs, one currency, up to 10 pages.
   - Explicitly handles unreadable/missing fields with reviewer escalation.

4. **Reasonable technical stack fit**
   - Gemini for reading/summarizing/request drafting + deterministic checks for quantities/totals.
   - Cloud Run + Cloud Storage alignment with challenge platform constraints.

5. **Human-in-the-loop positioning**
   - Proposal correctly avoids “AI auto-approval” and keeps reviewer control.
   - Tracks unresolved vs resolved issues and case history, which supports auditability.

## What does not work yet (facts and likely judge objections)

1. **Evidence quality is currently weak for winning**
   - Test plan uses **60 fictional document sets only**.
   - No external or semi-real validation set is described.
   - Judges may interpret results as overfit to handcrafted scenarios.

2. **No baseline definition for impact claims**
   - Targets are listed (>=90% issue detection, <=10% false alarms), but there is no explicit baseline comparator or current manual benchmark value in proposal text.
   - Without baseline, impact cannot be quantified convincingly under “Problem Alignment & Impact.”

3. **Differentiation risk is high**
   - Many teams can build “document compare + AI summary + request draft.”
   - Proposal does not state a sharp moat (for example: policy-grounded reasoning quality, explainability depth, or measurable reviewer productivity uplift across edge cases).

4. **Compliance and security details are underdeveloped**
   - No explicit PII redaction strategy, access control model, data retention policy, or audit log schema is defined.
   - In BFSI, this weakens production credibility even for prototype judging.

5. **Evaluation framework misses failure-mode rigor**
   - No stratified error buckets (OCR errors, ambiguous terms, partial deliveries, unit mismatch, currency format drift).
   - No severity-weighted metrics (critical miss vs minor mismatch).

6. **Timeline is plausible but execution-risky**
   - Plan assumes two part-time builders and includes user walkthroughs, build, UX, testing, fixes, video, and submission in ~24 days.
   - Risk: demo polish and metric quality may both suffer if evaluation harness is not front-loaded.

7. **UX score risk (10%)**
   - Proposal says there is a review screen but gives little detail on information architecture, keyboard flow, or how quickly a reviewer can close a case.
   - Without observable UX speed advantage, judges may score this as technically okay but not experience-leading.

## Rubric-readiness estimate (current)

- **Technical Merit & GenAI (40%)**: Medium
  - Stack is sound, but proof depth and failure-mode validation are not yet strong.

- **Problem Alignment & Impact (25%)**: Medium
  - Problem fit is strong; quantified impact proof is currently weak.

- **Innovation & Creativity (25%)**: Medium-Low
  - Useful product idea, but differentiation thesis is not yet explicit.

- **UX & Solution Design (10%)**: Medium-Low
  - Workflow intent is good; interaction quality proof is missing.

## Non-negotiable fixes before final submission

1. **Add baseline + delta table**
   - Manual vs CaseProof on same case set: time/case, missed issues, unnecessary requests, reopen rate.

2. **Upgrade evaluation dataset design**
   - Keep 60 synthetic cases but add structured difficulty tiers and hidden holdout set.
   - Publish confusion matrix + critical error categories.

3. **Strengthen differentiation claim**
   - Define one “hero capability” competitors likely miss (e.g., issue lifecycle trace: detected -> requested -> resolved with quote-backed evidence).

4. **Make BFSI trust explicit**
   - Add minimal security posture section: access controls, audit logs, retention/deletion policy, redaction behavior.

5. **Script a judge-facing 3-minute proof narrative**
   - 30s problem pain -> 90s workflow demo -> 45s metric proof -> 15s architecture credibility.

## Addendum (01 October 2026): fraud-intelligence extension

To strengthen innovation without scope creep, add an assistive fraud-risk layer inside the same discrepancy workflow:
- Include tamper, identity inconsistency, and anomaly signals with evidence links.
- Keep reviewer-in-control posture unchanged (no auto-approval/rejection).
- Evaluate fraud-signal precision/recall separately from discrepancy metrics.
- Position this as triage acceleration, not autonomous fraud adjudication.

## Addendum (01 October 2026): executive control-tower extension

To improve operational credibility for leadership stakeholders, add a Phase 1.5 executive control tower:
- Portfolio-level case state counters (live, paused, issue-blocked, escalated, overdue).
- Limited intervention actions only: prioritize, escalate channel, reassign owner.
- Mandatory reason-code and immutable logging for each intervention.
- Preserve reviewer adjudication boundary (no executive auto-approve/reject/close).

## Bottom line

CaseProof is a good foundation. To become a likely winner, it must move from “sensible concept” to “measurably superior system” with hard benchmark evidence, clearer moat, and explicit BFSI trust controls.
