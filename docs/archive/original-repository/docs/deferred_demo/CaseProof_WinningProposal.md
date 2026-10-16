# CaseProof: Winning Proposal Draft (Judge-Ready)

> **Historical proposal draft.** Claims such as a fraud-intelligence layer, dual write-once reports, and reviewer/manager/executive controls do not match the shipped app. Use [ARCHITECTURE.md](../../../../ARCHITECTURE.md), [TESTING.md](../../../../TESTING.md), and [the current judge path](../../../../JUDGE_SCRIPT.md).

Date: 26 September 2026
Theme: BFSI (Banking, Financial Services, Insurance)

## 1) One-line thesis

CaseProof is an AI-assisted document discrepancy resolution copilot for trade-finance reviewers that adds assistive fraud intelligence, cuts review time and false escalations, and preserves full human control and auditability.

## 2) Problem and why it matters

In invoice financing and related trade-finance flows, reviewers must reconcile invoice data against proof-of-delivery and other records. Mismatches are common, but raw mismatch detection is not enough: reviewers still need to determine what evidence is missing, what was corrected, and what remains unresolved.

Current pain points:
- Too much time spent navigating multiple documents and repeated back-and-forth.
- Inconsistent reviewer requests that create avoidable customer friction.
- Weak traceability of issue lifecycle (detected -> requested -> resolved).

## 3) Users and success condition

Primary user:
- Trade-finance operations reviewer (document verification workflow owner).

Success condition:
- Reviewer closes high-quality cases faster, with fewer missed issues and fewer unnecessary requests.

## 4) What CaseProof does (V1)

For each case, CaseProof:
1. Extracts key fields and line items from invoice, proof-of-delivery, and purchase-order PDFs.
2. Aligns invoice lines to delivery lines across description variants and split shipments.
3. Compares quantities, totals, references, and entity identifiers using lender-policy tolerances.
4. Decides whether each mismatch is explained by the deal terms or lender checklist, or needs a request — citing the clause.
5. Verifies every AI quote against the source page before showing it.
6. Surfaces assistive fraud-risk signals (tamper/identity/duplicate invoice) with evidence links.
7. Drafts a targeted correction request the reviewer can edit and send.
8. Tracks issue lifecycle and request-item responses after customer reply (resolved/open/reopened).
9. On approval or rejection, issues two sealed reports: a full internal audit report (every issue, evidence, AI rationale, reviewer action, and audit event) and a client-facing decision report explaining the outcome and what would fix any remaining issue.

Phase 1.5 extension:
- Executive control-tower dashboard for portfolio status (live/paused/issue/escalated) and controlled intervention actions.

Scope boundaries (V1):
- English PDFs only
- One currency
- Up to 10 pages per case
- Missing/unreadable fields explicitly routed to manual review

## 5) Why this is differentiated (moat statement)

Most prototypes stop at mismatch detection + summary. CaseProof’s differentiator is **issue lifecycle intelligence with evidence-backed closure**:
- Every discrepancy is traceable from first detection to final resolution state.
- Every recommendation is attached to document quotes and page provenance.
- Every reviewer action is logged for audit and post-hoc quality analysis.
- Fraud-risk triage is integrated in the same reviewer workflow without auto-adjudication.

This shifts the system from “AI helper” to “auditable workflow acceleration layer.”

## 6) Technical design (Google Cloud aligned)

- **Gemini**: document understanding, discrepancy explanation, and request drafting.
- **Deterministic checks**: arithmetic and quantity consistency logic.
- **Fraud signal engine**: assistive tamper, identity inconsistency, and anomaly scoring.
- **Cloud Run**: application backend/API.
- **Cloud Storage**: document storage.
- **Structured datastore** (implementation choice): case state, issue lifecycle, and audit logs.

Design principle:
- AI proposes; deterministic checks verify; human reviewer decides.

## 7) Evaluation plan (baseline + delta proof)

### 7.1 Test dataset design

- 120 labeled synthetic case sets from a seeded generator (`CP_SYNTH_TRADE_V1`).
- Balanced composition:
  - 60 problematic cases (planted issues)
  - 60 valid/acceptable cases (including partial-delivery-valid scenarios)
- 60/20/20 dev/val/holdout split; holdout uses a separate seed and disjoint templates.
- Reviewer-time metrics measured on a 12-case timed holdout subset.
- Public datasets (DocILE/FUNSD/SROIE) used for extraction-accuracy credibility only.

### 7.2 Primary metrics

- Issue detection recall
- False alarm rate on valid cases
- Reviewer time per case
- Missed critical issues per 100 cases
- Unnecessary request rate
- Reopen rate after customer correction
- Fraud-signal precision/recall (high-severity tier)

### 7.3 Baseline-vs-CaseProof scoreboard (fill with measured results)

| Metric | Manual | Rules-only | LLM-only | CaseProof | Delta vs Manual | Delta vs Best Baseline |
|---|---:|---:|---:|---:|---:|---:|
| Issue detection recall | TBD | TBD | TBD | >= 90% | +X pts | +Y pts |
| False alarm rate (valid cases) | TBD | TBD | TBD | <= 10% | -X pts | -Y pts |
| Median reviewer time/case | TBD | TBD | TBD | <= 60% of manual | -X% | -Y% |
| Missed critical issues / 100 | TBD | TBD | TBD | <= 50% of manual | -X | -Y |
| Unnecessary requests | TBD | TBD | TBD | <= 70% of manual | -X% | -Y% |
| Reopen rate | TBD | TBD | TBD | <= 80% of manual | -X% | -Y% |
| Fraud-signal precision (high-severity) | TBD | TBD | TBD | >= 80% | +X pts | +Y pts |

Rule: proposal and demo must report **measured comparator deltas**, not only targets. Publish development and holdout values separately.

## 8) BFSI trust, risk, and compliance posture (prototype level)

Controls included in V1:
- Reviewer remains final decision-maker (no auto-approval path).
- Quote-backed findings with source-page references; every AI quote verified against the source before display.
- Action audit trail: who changed what and when.
- Access-controlled case views (authenticated reviewer access).
- Sensitive field minimization and redaction in generated summaries.
- Explicit unresolved-issue tracking to avoid silent closure.
- Write-once, hash-verified decision reports for audit and client; client report never discloses fraud signals.
- Role-permission matrix enforcement for reviewer/manager/executive interventions.

## 9) Rubric mapping (40/25/25/10)

- **Technical Merit & GenAI (40%)**:
  - Hybrid AI + deterministic validation: Gemini aligns line items and reasons over terms/policy; rules verify arithmetic; citation verifier blocks hallucinated evidence. Fraud signal layer, issue lifecycle engine, auditability.
- **Problem Alignment & Impact (25%)**:
  - Clear ops pain point + baseline-vs-delta proof.
- **Innovation & Creativity (25%)**:
  - Evidence-backed discrepancy lifecycle closure plus assistive fraud triage in one reviewer flow.
- **UX & Solution Design (10%)**:
  - Reviewer-centered queue, issue states, one-click evidence view, editable requests.
  - Executive control-tower view for operational oversight and bottleneck intervention.

## 10) What judges will see in 3 minutes

1. Realistic mismatch case appears in review queue.
2. CaseProof highlights issues with exact source evidence; a partial delivery is recognised as allowed by the PO terms (with cited clause) while a real shortfall is flagged.
3. Fraud-risk panel flags a high-severity identity inconsistency with evidence links.
4. Reviewer edits/sends drafted request.
5. Customer correction arrives; the fixed issue is re-checked and confirmed by the reviewer in one click, unrelated issue remains open.
6. Dashboard shows measurable time/quality improvement and full audit history.

## 11) Delivery checklist before submission

- Working deployed prototype on Cloud Run or Firebase.
- Public source code.
- Metric report with baseline-vs-delta table from holdout cases.
- PDF proposal and <=3-minute demo video.
- Clear statement of limitations and next-step roadmap.
