CASEPROOF | A CORRECTION CHANGES THE SALE

Reject a changed quantity even when its multiplication is correct.

Seller: Alder Trade Supplies Pte Ltd
Buyer: Cedar Commercial Services Pte Ltd
Invoice: AT-2026-0901
Flow: replacement_scope, authorised_follow_up

SETUP
Use the sample policy; optional document checks off unless specified.

START WITH
01-invoice.pdf
02-full-receipt.pdf

EXPECTED FIRST RESULT
The original amount is wrong. The later changed-quantity invoice is intentionally outside correction authority.

STEPS
1. Start with 01 and 02. Wait for the invoice-correction request.
2. Upload 03 as an invoice replacing version 1. This changes the quantity to 104, so it must not silently amend the financed sale.
3. Open the evidence decision and choose Authorise a further request. Reason: Keep the original 100-box sale; request an amount-only correction.
4. Add 04 as the invoice, replacing the original version 1 rather than the rejected copy. Wait for completion.

EXPECTED FINAL RESULT
Document review completes with a retained summary.

FILES
01-invoice.pdf: invoice
02-full-receipt.pdf: receipt
03-invalid-quantity-change-v2.pdf: invoice
04-amount-only-correction-v2.pdf: invoice

All companies, people, addresses and transactions are fictional.
The business PDFs are test records, not genuine invoices or evidence of real deliveries.
