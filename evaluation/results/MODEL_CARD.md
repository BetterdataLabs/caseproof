# CaseProof model card

Companion to the saved evaluation report (`latest.json`). Intended use, provider data boundaries, and evaluation limits for the shipped Gemini / Vertex build.

## Intended use

Invoice-financing **document review** for a bank operations team. Gemini reads supported documents, interprets invoice and delivery evidence, and proposes source-grounded calculation plans. Python performs exact arithmetic and enforces evidence validation, duplicate-invoice holds, tool authority, and completion. A person records exceptions. The bank still decides whether to finance.

Personas on this build: Alex reviews cases, publishes policy and manages budgets; Sam submits evidence and replies to bank requests; Aisha inspects with read-only access.

## Out of scope

- Financing approval, pricing, limits, or payment
- Formal sanctions, PEP, or adverse-media screening as a control
- Document authentication, forgery proof, or legal identity verification
- A credit score, probability of default, or continuous monitoring
- Purchase-order alignment, a fraud-signal engine, or an executive control tower (those remain in archived drafts only)

## What is sent to Vertex (Gemini)

Configured model: `gemini-3.8-flash` on Vertex AI (`global`). Every call goes through the bounded gateway (case and daily cost reserves; per-wakeup model and tool caps).

- Reading: requested document role and extracted content from PDFs, DOCX, XLSX, CSV and text files. Scans and image files send rendered page images for visual transcription. Supported uploads retain multiple items, decimal quantities, currencies, taxes and other adjustments. Raw PDF bytes are not sent; limits are 20 pages or sheets and 10 MiB per file.
- Agent and policy review: checklist state, quoted evidence, policy criteria, and tool observations.
- Optional appearance checks: rendered page images of the upload and, if supplied, a reference template.
- Optional research synthesis: company identity plus grounded passages already returned by Search.

Invoice files, messages, and internal case identifiers are not sent to Google Search.

## What is sent to Google Search

Only when public company research is explicitly enabled on that case. Each grounded call receives only:

- company name
- country of registration
- registration number / UEN, when supplied
- current date
- a generic research angle (identity, filings, or sector)

No invoice amounts, line items, documents, messages, reviewer names, or case identifiers.

Research retains the existing dedicated allowance of at least USD 1 per case in addition to the document-review budget. Reports and their saved evidence are available on the Research page.

## Evaluation limits

The saved report is 60 constructed cases across 12 families, run on 12 October 2026 with Gemini 3.8 Flash.

- The headline result is **0 incorrect completions** on both the agent and the fixed-rule baseline.
- Staff minutes (110 vs 100) are a **time model**, not a user study or ROI claim.
- The set is not a production error-rate, extraction-accuracy, or forgery-detection benchmark.
- Expected outcomes live outside the running app and are compared only after each case finishes.
- Zero failures on this set does not establish a bank-grade error rate.
