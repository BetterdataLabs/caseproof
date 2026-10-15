CASEPROOF | A SUPERVISOR EXTENDS THE RUN ALLOWANCE

Reaching an automation limit does not discard the case.

Seller: Alder Trade Supplies Pte Ltd
Buyer: Cedar Commercial Services Pte Ltd
Invoice: AT-2026-1901
Flow: budget_exhausted, supervisor_extension

SETUP
Use an isolated demo workspace. As supervisor, publish a temporary policy with Agent runs per case set to 1, retaining the other defaults. Create this case, then restore 12 runs in a new published version for subsequent cases. This case stays pinned to the one-run policy.

START WITH
01-invoice.pdf
02-full-receipt.pdf

EXPECTED FIRST RESULT
The first run reads the two PDFs. The next run hits the one-run allowance and pauses before completion.

STEPS
1. Start with 01 and 02 under the temporary one-run policy. Leave optional visual checks off.
2. When Budget exhausted appears, open the decision as Alex Chen or another supervisor.
3. Choose Grant an extension: 4 extra agent runs and USD 0.25. Reason: Allow the already-read documents to finish review.
4. Wait for completion. The extension and original policy version remain in history.

EXPECTED FINAL RESULT
Document review completes with a retained summary.

FILES
01-invoice.pdf: invoice
02-full-receipt.pdf: receipt

All companies, people, addresses and transactions are fictional.
The business PDFs are test records, not genuine invoices or evidence of real deliveries.
