CASEPROOF | RESUME AFTER A MODEL OUTAGE

A temporary model failure preserves work and opens a recovery task.

Seller: Alder Trade Supplies Pte Ltd
Buyer: Cedar Commercial Services Pte Ltd
Invoice: AT-2026-1801
Flow: service_failure, resume_saved_work

SETUP
Run this in an isolated demo workspace with no other active cases. In Operations, simulate a timeout for the next 10 model calls; this affects the organisation, so clear it immediately after the pause.

START WITH
01-invoice.pdf
02-full-receipt.pdf

EXPECTED FIRST RESULT
The case pauses on a simulated model timeout. Its originals and queued work remain saved.

STEPS
1. Set the timeout simulation, then start a new upload case with 01 and 02.
2. Wait for Paused and a Service failure task. Open Evidence to confirm the originals remain accessible.
3. In Operations, clear the simulated failure. Return to the case and choose Resume automation on its recovery task, recording that the service is available.
4. Wait for completion. Do not upload the same documents again.

EXPECTED FINAL RESULT
Document review completes with a retained summary.

FILES
01-invoice.pdf: invoice
02-full-receipt.pdf: receipt

All companies, people, addresses and transactions are fictional.
The business PDFs are test records, not genuine invoices or evidence of real deliveries.
