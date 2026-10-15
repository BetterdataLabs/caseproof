# BFSI: Intelligent Risk, Fraud &amp; Financial Experiences
Link: https://aibuildercup.com/
## Problem Statement
Build an AI-powered solution that addresses meaningful challenges across banking, financial services, insurance, or related industries. Solutions may focus on detecting and mitigating fraud or risk, automating complex processes, improving customer interactions, or delivering more personalized and informed financial experiences.

## Suggested Solution Directions
Fraud detection, transaction anomaly analysis, document intelligence, financial assistance, personalized recommendations, compliance automation, risk assessment

## Current Project Direction

CaseProof is currently scoped as a trade-finance discrepancy-resolution copilot with an assistive fraud-intelligence layer:
- Core: invoice vs proof-of-delivery discrepancy detection and lifecycle resolution.
- AI reasoning: line-item alignment, terms/policy-aware assessment, and citation verification of every AI quote.
- Fraud assist: risk signals for tampering, identity inconsistencies, and duplicate invoices.
- Control model: AI proposes, rules verify, reviewer decides (no auto-adjudication).
- Executive extension (Phase 1.5): control-tower dashboard for portfolio status, escalation, and prioritization.

## Suggested Google Cloud Technologies
Gemini on Vertex AI for reasoning and conversational experiences, BigQuery for transaction and risk analytics, Vertex AI for predictive or classification models, Document AI for financial and non-traditional documents, Vertex AI Search / Agent Search for policy and knowledge retrieval, Cloud Run for application services, Cloud SQL or AlloyDB for application data, Pub/Sub for event-driven transaction processing

## Engineering Docs

- Deep challenge analysis: `docs/Problem.md`
- Operating rules: `docs/PrincipalEngineeringRules.md`
- Current app design plan: `docs/APP_DESIGN_PLAN.md`
- Feature specifications: `docs/FEATURE_SPEC.md`
- Architecture specification: `docs/ARCHITECTURE_SPEC.md`
- Data model and state machine: `docs/DATA_MODEL_STATE_MACHINE.md`
- Security and trust controls: `docs/SECURITY_TRUST_CONTROLS.md`
- Reason-code taxonomy: `docs/REASON_CODE_TAXONOMY.md`
- Dataset register: `docs/DATASET_REGISTER.md`
- Benchmark and evidence protocol: `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
- Role-permission matrix: `docs/ROLE_PERMISSION_MATRIX.md`
- Implementation sequence: `docs/IMPLEMENTATION_SEQUENCE.md`
- Full docs index: `docs/DOCS_INDEX.md`
- Docs freeze checklist: `docs/DOCS_FREEZE_CHECKLIST.md`
- Current project state: `docs/PROJECT_CONTEXT.md`
- Session continuity log: `docs/SESSION_LOG.md`
- Proposal critique: `docs/CaseProof_Review.md`

## Deferred Demo Docs

These are intentionally deferred until app design sign-off:

- `docs/deferred_demo/CaseProof_WinningProposal.md`
- `docs/deferred_demo/CaseProof_JudgeScript_3min.md`
- `docs/deferred_demo/CaseProof_RevisionChecklist.md`

## Continuity Rule

Every work session must end by updating `docs/PROJECT_CONTEXT.md` and appending `docs/SESSION_LOG.md`.
