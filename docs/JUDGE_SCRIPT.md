# Live finale path

Use this only if the team is in the room with a judge. The scoring-round film is [docs/VIDEO_SCRIPT.md](VIDEO_SCRIPT.md). The deck is [docs/submission/CaseProof-AI-Builder-Cup.pptx](submission/CaseProof-AI-Builder-Cup.pptx).

This walkthrough matches the **shipped** app. It does not describe purchase-order alignment, a fraud-signal engine, dual sealed reports, or an executive control tower. Those remain in [historical drafts](archive/original-repository/docs/deferred_demo/CaseProof_JudgeScript_3min.md) only.

Target length: 2m45s to 3m00s. Prefer the hosted URL. Compose and Cloud Run ask for the same access code, from the form and the uploaded PDF. It is not in this repository. After the code, the reviewer lands on the case that is already read. **Client notice** on that case opens the completed example. Locally: `http://localhost:3400` after `docker compose up --build --detach --wait`.

Do not quote 110 versus 100 staff minutes. If a judge asks, the answer is in the deck: zero incorrect completions on a 60-case constructed set, and those minutes are a time model.

## 0:00–0:15 — What this is

"Invoice packs disagree. Reviewers lose the file in the back-and-forth. CaseProof is the review copilot for sales-invoice financing. Gemini reads and plans. The bank still decides financing."

## 0:15–1:20 — Upload, quotes, one request, correction

1. Sign in as **Sam Lim**. Create a submission with **01-invoice.pdf** and **02-first-receipt.pdf** from the [sample pack](../apps/web/public/sample-documents/caseproof-upload-example.zip).
2. Switch to **Alex Chen**. Open the case. Show one extracted field beside its source quote and page. Show the checklist: wrong total and missing delivery. Show the single request that names both gaps.
3. "Gemini proposed these values from the page. It raised both gaps in a single request."
4. Switch to **Sam**. Upload **03-corrected-invoice.pdf**, then **04-remaining-receipt.pdf**. Return to **Alex**. The checklist is green.

"The correction landed in the checklist. The arithmetic is committed in code."

## 1:20–2:15 — A bank decision and read-only access

5. As **Sam**, send a written reply that disputes a receipt, or open scenario **12-untrusted-instructions**.
6. As **Alex**, claim the task and record the decision. Alex handles the bank review and administration. An instruction inside the document does not become a tool call.
7. Use **Alex** to show policy publication or budget controls if asked. Switch to **Aisha Tan** to show the same case with read-only access.
8. If you have twenty seconds: create a **second case** with the same seller invoice number and amount. The new case stays open. The checklist holds `duplicate_invoice`. That is a book-level hold, separate from a copied file on one case.

## 2:15–2:40 — The two documents

9. On a completed case, open the bank PDF and the client PDF. The client notice has no reviewer names and no model traces. The footer on the bank file: document review is complete; financing stays with the bank.
10. Optional, one sentence, if the judge asks about evidence: "Sixty constructed cases, zero incorrect completions, on both the agent and the fixed-rule baseline." Then stop. Do not open the chart.

## 2:40–3:00 — Close

"Gemini on Vertex, Google ADK, quote-grounded extraction. Search runs only when research is opted in, and that call receives the company name, country, and registration number. Tool scope comes from the worker. Designed for Cloud Run. The agent cannot approve a facility."
