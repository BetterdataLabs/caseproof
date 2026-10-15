# BFSI Challenge: Principal-Engineer Deep Read

Source links:
- Main challenge: https://aibuildercup.com/
- Themes page: https://aibuildercup.com/themes.html

## 1) What the prompt actually requires (non-negotiable)

From the challenge text, we must submit:
- A **working prototype** (not only a pitch deck/mockup).
- Built with **Google AI models** (Gemini/Gemma) or approved Google agentic platforms.
- Deployed on **Google Cloud** via **Cloud Run** or **Firebase**.
- A **clear proposal deck** (PDF) with problem, impact, feasibility, scalability.
- A **public demo video** (YouTube/Vimeo/public Drive), ~3 minutes.

Judging weights:
- **Technical Merit & Gen AI Implementation**: 40%
- **Problem Alignment & Impact**: 25%
- **Innovation & Creativity**: 25%
- **User Experience & Solution Design**: 10%

## 2) Critical reading (ruthless gaps)

The current problem framing is too broad to win as-is. Main issues:
1. **No sharp user persona**: “BFSI” is a sector, not a user/problem boundary.
2. **No measurable outcome**: no KPI targets (issue recall, false alarm rate, review SLA, reopen rate).
3. **No evaluation contract**: no offline + online quality bars for model behavior.
4. **No risk/compliance posture**: missing auditability, explainability, PII controls.
5. **No differentiation thesis**: many teams can build “AI assistant + dashboard.”
6. **No failure-mode strategy**: model hallucinations, false positives, alert fatigue, drift.

If we submit with these gaps, we will likely lose on Technical Merit (40%) and Impact (25%).

## 3) Winning strategy (focused wedge)

Pick a **single high-value, narrow battlefield** and dominate it.

Recommended wedge:
- **Trade-finance document discrepancy resolution copilot (CaseProof)**
- Why: clear operational pain, measurable workflow impact, strong auditability story, and natural extension to assistive fraud triage.

Scope rule:
- Keep one core workflow (discrepancy resolution), then add a thin fraud-intelligence layer inside the same reviewer screen.
- Keep executive/CEO dashboard as Phase 1.5 read-mostly control tower with strictly bounded interventions.

Target outcomes (set explicit bars):
- Detect planted discrepancy issues with **>= 90% recall**.
- Keep false alarms on valid cases at **<= 10%**.
- Cut reviewer case handling time by **>= 40%**.
- Maintain evidence-backed rationale for **100%** of flagged issues.
- Keep high-severity fraud-signal precision at **>= 80%** on holdout cases.

## 4) Architecture pattern likely to score highly

Minimum architecture with demonstrable depth:
1. **Ingestion + feature pipeline**
   - Document upload/events -> parsing/extraction -> normalization.
2. **Hybrid risk scoring**
   - Deterministic discrepancy checks + Gemini reasoning over context.
3. **Assistive fraud signal layer**
   - Tamper, identity mismatch, and anomaly signals with evidence-linked explanations.
4. **Analyst copilot**
   - Natural-language issue explanation, correction request drafting, case summary.
5. **Knowledge grounding**
   - Policy/checklist grounding for request quality and consistency.
6. **Decision logging + audit trail**
   - Every model output tied to features, prompts, retrieved evidence, final action.
7. **Deployable demo app**
   - Cloud Run service + simple UI with case queue and explainability pane.
8. **Executive control tower (Phase 1.5)**
   - Portfolio visibility (live/paused/issue/escalated) with reason-coded prioritize/escalate/reassign actions.

## 5) “Principal Engineer” build rules for this project

We optimize for correctness, clarity, and continuity over flashy demos.

Non-negotiable rules:
1. **Every claim must be measurable** (metric + baseline + target).
2. **Every model decision must be auditable** (inputs, prompt context, output, reviewer action).
3. **Every feature must map to judging criteria** (40/25/25/10 coverage).
4. **Every work session must end with context handoff update** (`docs/PROJECT_CONTEXT.md`).
5. **No silent assumptions**: unknowns go to risk register with owner/date.
6. **App-first reliability**: graceful fallback if GenAI call fails.
7. **Security by default**: redact sensitive fields, least privilege, access logging.
8. **Ship vertical slices**: thin end-to-end increments over isolated components.

## 6) Submission risk register (top items)

- **Risk:** Great narrative, weak proof of app impact.
  - **Mitigation:** publish before/after KPI table with scenario methodology.

- **Risk:** AI feels decorative, not core.
  - **Mitigation:** make Gemini central to discrepancy explanation + request drafting + reviewer action support.

- **Risk:** Judges doubt production realism.
  - **Mitigation:** include audit logs, policy grounding, and human-in-the-loop controls.

- **Risk:** Scope explosion.
  - **Mitigation:** one user persona, one workflow, one hero metric set.

- **Risk:** Fraud-signal false positives reduce reviewer trust.
  - **Mitigation:** assistive-only controls, calibrated thresholds, and mandatory evidence links.

- **Risk:** Executive escalation actions create governance drift.
  - **Mitigation:** role-based permissions, immutable action logs, and reviewer decision boundary protection.

## 7) Immediate execution plan (next 5 deliverables)

1. Finalize app pros/cons decisions and architecture direction.
2. Finalize MVP feature list and acceptance criteria.
3. Define dataset strategy (synthetic + optional public benchmark).
4. Freeze fraud-signal MVP (tamper + identity + anomaly) and associated metrics.
5. Implement vertical slice: upload -> extract -> detect -> fraud signal -> draft -> resolve -> audit log.

Phase 1.5 add-on after MVP freeze:
- Add executive control tower with status portfolio, escalation workflow, and action-governance logging.

## 8) Repository deep links for continuity

- Problem deep read: `docs/Problem.md`
- Engineering operating rules: `docs/PrincipalEngineeringRules.md`
- Architecture spec: `docs/ARCHITECTURE_SPEC.md`
- Data/state model: `docs/DATA_MODEL_STATE_MACHINE.md`
- Security/trust controls: `docs/SECURITY_TRUST_CONTROLS.md`
- Reason-code taxonomy: `docs/REASON_CODE_TAXONOMY.md`
- Dataset register: `docs/DATASET_REGISTER.md`
- Benchmark and evidence protocol: `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
- Implementation sequence: `docs/IMPLEMENTATION_SEQUENCE.md`
- Continuity + handoff state: `docs/PROJECT_CONTEXT.md`
- Chronological session log: `docs/SESSION_LOG.md`
