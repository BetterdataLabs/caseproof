# Submission video — under 3 minutes

This is the film for the scoring round. Remote judges watch it once, then open the deployed link and the deck. Record it on the **Cloud Run URL**, with that host visible in the address bar. Rehearse on `http://localhost:3400` if the host is not up yet, and re-record before you upload.

A judge who opens the link enters the access code from the form and the uploaded PDF, then lands on a case that is already read, with the quote and checklist on screen. The film does not ask them to switch persona. Switch persona stays in the app.

Cast: **Sam Lim** (vendor) and **Alex Chen** (reviewer). Two people, one case.

Leave out policy publish, the second-case duplicate hold, the model card, and the staff-minute chart. Those are for the [live finale](JUDGE_SCRIPT.md) and the deck appendix.

Files, from the [sample pack](../apps/web/public/sample-documents/caseproof-upload-example.zip): `01-invoice.pdf`, `02-first-receipt.pdf`, `03-corrected-invoice.pdf`, `04-remaining-receipt.pdf`.

Have a completed case already on the org, with the bank PDF and the client PDF one click away, in case the live correction is still processing when you reach 2:10.

Target length: **2:45–2:55**. Hard stop at 3:00.

## 0:00–0:15 — What this is

Address bar shows the hosted app.

"Invoice packs disagree. Reviewers lose the file in the back-and-forth. CaseProof is the review copilot for sales-invoice financing, under the BFSI theme. Gemini reads and plans. The bank still decides financing."

## 0:15–1:05 — Gemini, on the page

1. Sign in as **Sam**. Create a submission with **01-invoice.pdf** and **02-first-receipt.pdf**.
2. Cut the processing wait. Sign in as **Alex** and open that case.
3. Show one extracted field beside its source quote and page. Show the checklist: wrong total, missing delivery. Show the single request that names both gaps.

"Gemini proposed these values from the page. It raised both gaps in a single request."

## 1:05–1:40 — The correction lands in the checklist

4. As **Sam**, upload **03-corrected-invoice.pdf**, then **04-remaining-receipt.pdf**. Cut the spinner.
5. As **Alex**, show the checklist green.

"The correction landed in the checklist. The arithmetic is committed in code."

## 1:40–2:10 — An exception stays with a person

6. As **Sam**, send one sentence that disputes a receipt, or open scenario **12-untrusted-instructions** if it is already on the host.
7. As **Alex**, show the task and that the instruction did not become a tool call. Optional, five seconds: scenario **13** or **16** still open.

"An instruction inside the document does not become a tool call. Exceptions stay with the reviewer."

## 2:10–2:35 — What the vendor receives

8. Open the bank PDF and the client PDF for the completed case. Show the client header: it is a document-review notice. Show the bank footer: financing stays with the bank.

"The vendor receives the document-review notice. Staff names and model traces stay in the bank file. Financing stays with the bank."

## 2:35–2:55 — Close on a card, not a dashboard

Static card, full screen:

- Vertex Gemini and Google ADK
- Tools scoped by the worker
- Google Search receives the company name, country, and registration number only
- Deployed on Cloud Run

"Designed for Cloud Run. The agent cannot approve a facility."

## If the worker is slow

The landing case already shows the quote and the checklist. **Client notice** on that case opens the completed example, with the bank PDF and the client PDF on screen. Say "this is the same case, after the correction."

## Do not say

- "The model did not beat the checklist."
- Any staff-minute or ROI figure.
- Purchase-order alignment, a fraud-signal engine, or an executive control tower.

## Export

Public YouTube, Vimeo, or a public Google Drive link. English. Under 3:00. The submission cut shows the hosted host, not localhost.
