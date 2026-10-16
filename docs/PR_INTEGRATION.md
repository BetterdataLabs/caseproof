# Contest feature integration

PR #1 was integrated and corrected on `dev` while preserving the submitted application’s review and research workflows. The reviewed changes are incorporated into `main` as one reversible commit.

## Preserved review behavior

- Uploaded documents use the existing Gemini review, source validation and exact calculation tools. PDFs, scans, images, DOCX, XLSX, CSV and text remain supported, including multiple items, decimal quantities, currencies, taxes and adjustments.
- Research remains available per case and on the Research page, with saved searches, citations, retry support and at least USD 1 of dedicated research allowance per enabled case.
- Document appearance checks, activity history, live queue progress, policy publication, corrections and reviewer decisions retain their existing behavior.
- Published policy records are not rewritten during initialization. The Evaluation page remains removed; the saved evaluation and model card are available as repository documents.

## Added contest features

- Set `CASEPROOF_DEMO_ACCESS_CODE` to use access-code login. Hosted demo personas require it; an empty value locally retains the existing loopback-only persona picker.
- The submitted three-account flow is preserved: Alex handles bank review and administration, Sam handles vendor submissions, and Aisha is read-only. Access-code login opens Alex’s bank workspace. Sign-out clears the session and access-code cookies; switching personas retains the access-code cookie.
- Initialization prepares an open example and a completed example with a client notice only in an empty workspace. Existing cases are left unchanged, and demo shortcuts select cases accessible to Sam. Case checklists show source quotations alongside results.
- A separate duplicate-invoice control compares identified seller invoices against other non-archived cases in the same organisation. It never substitutes the legacy single-line calculator for uploaded-document review, and the model cannot waive it. Different identified currencies do not count as the same amount. Unfamiliar amount formats retain their printed notation for comparison.
- Client PDF and JSON notices are available to the assigned vendor. Bank research, model traces, staff identities and internal reviewer dispositions remain in the bank record.

## Verification

The local regression suite covers document reading, calculations, evidence validation, policy changes, appearance checks, research budgets, vendor access, organisation isolation, agent execution and completion. Added integration checks cover duplicate invoices, currency boundaries, policy immutability, client-report redaction, showcase initialization, access-code login and throttling.

Browser checks use a separate database and confirm login, persona switching, summary links, PDF downloads, Research navigation, flexible upload instructions, duplicate holds, mobile layout, sign-out and retry after a temporary login failure. These isolated checks do not spend money on model calls or modify the running application’s case data.

The production web build and frontend/backend lint, formatting and type checks are also verified. Cloud deployment is not part of this integration.
