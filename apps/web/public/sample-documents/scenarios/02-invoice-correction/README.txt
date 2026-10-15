CASEPROOF | THE INVOICE TOTAL IS WRONG

Fix the amount while retaining the original invoice in history.

Seller: Meridian Office Supply Pte Ltd
Buyer: Juniper Business Centre Pte Ltd
Invoice: MO-2026-2201
Flow: invoice_correction

SETUP
Use the sample policy; optional document checks off unless specified.

START WITH
01-invoice-incorrect.pdf
02-full-receipt.pdf

EXPECTED FIRST RESULT
Delivery is complete. The invoice states SGD 2,680.00, but 80 x SGD 32.50 = SGD 2,600.00. Expect a request for an invoice correction.

STEPS
1. Start with 01 as the invoice and 02 as the receipt. Leave Written message blank.
2. After the correction request appears, choose Add documents or reply. Put 03 in Invoice PDF.
3. Under Replacing an earlier document?, select Invoice MO-2026-2201, version 1. Upload only this one correction. Leave Written reply blank.
4. Wait for the agent. The earlier invoice should remain visible as Superseded.

EXPECTED FINAL RESULT
The current invoice total is SGD 2,600.00, both checks pass, and the document review should complete.

FILES
01-invoice-incorrect.pdf: invoice
02-full-receipt.pdf: receipt
03-invoice-corrected-v2.pdf: invoice

All companies, people, addresses and transactions are fictional.
The business PDFs are test records, not genuine invoices or evidence of real deliveries.
