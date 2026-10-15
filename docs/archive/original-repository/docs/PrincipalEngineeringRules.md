# Principal Engineering Rules (Winning Mode)

This repository follows strict operating principles to maximize competition outcomes.

## Objective hierarchy

1. Win on judging rubric (40/25/25/10) with evidence, not claims.
2. Build a credible, auditable, production-minded prototype.
3. Maintain perfect continuity so any contributor can resume instantly.

## Non-negotiable execution rules

1. **Criteria mapping first**
   - Every planned feature must map to one or more judging criteria.
2. **Metrics before implementation**
   - No feature is “done” without baseline, target, and measurement method.
   - Metric definitions and comparator reporting must follow `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`.
3. **Auditability by default**
   - Log model inputs, retrieved context, outputs, confidence/signal traces, and human decisions.
4. **Grounded AI only**
   - High-impact recommendations must be grounded in policy/rules/context, not free-form generation.
5. **Human override always**
   - Any risk decision path must include explicit reviewer control and action trace.
6. **Fraud intelligence is assistive only**
   - Fraud signals can prioritize review, but cannot auto-approve, auto-reject, or auto-block cases.
7. **Reliability over novelty**
   - Favor deterministic fallbacks and robust flows over flashy but fragile behavior.
8. **Security & privacy baseline**
   - Minimize PII, redact sensitive fields, least-privilege access, and access logs.
9. **Vertical slices only**
   - Ship end-to-end thin slices that can be validated and measured.
10. **Ruthless scope control**
   - One persona, one core workflow, one hero story per milestone.
11. **Context preservation mandatory**
   - End every session by updating `docs/PROJECT_CONTEXT.md` and appending `docs/SESSION_LOG.md`.
12. **Role-bounded interventions only**
   - Manager/executive controls may reprioritize/escalate/reassign workflows, but must not override reviewer adjudication.
   - Action permissions must follow `docs/ROLE_PERMISSION_MATRIX.md`.
13. **Frozen control dictionaries only**
   - Reason codes must follow `docs/REASON_CODE_TAXONOMY.md`.
   - Benchmark datasets must follow `docs/DATASET_REGISTER.md`.

## Definition of done (feature level)

A feature is complete only if all are true:
- Clear owner and reason for existence.
- Direct rubric mapping documented.
- Measurable KPI impact with before/after evidence.
- Failure modes identified with fallback behavior.
- Logs and traces sufficient for post-hoc review.
- Core reviewer workflow is stable and understandable in under 60 seconds.

## Critic checklist (use before every milestone)

- Is this solving a painful real user problem or showing generic AI?
- Can stakeholders see measurable impact in one glance?
- If GenAI is removed, does solution collapse (it should materially degrade)?
- Is any claim unsupported by data, logs, or reproducible test steps?
- Are we hiding complexity that will fail live?
- Can every fraud signal be explained, evidence-linked, and overridden by reviewer?
- Are executive interventions reason-coded, permissioned, and fully audit-logged?

## Handoff protocol (mandatory)

At end of each session:
1. Update `docs/PROJECT_CONTEXT.md` current state sections.
2. Append a new timestamped entry to `docs/SESSION_LOG.md`.
3. Ensure next 3 actions are explicit, testable, and prioritized.
4. Record open risks with owner and mitigation.
5. If scope/design changed, sync `docs/ARCHITECTURE_SPEC.md`, `docs/DATA_MODEL_STATE_MACHINE.md`, and `docs/SECURITY_TRUST_CONTROLS.md`.

If a session ends without this protocol, the session is considered incomplete.
