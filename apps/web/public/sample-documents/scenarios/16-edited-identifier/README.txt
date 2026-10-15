CASEPROOF | AN INVOICE NUMBER HAS BEEN OVERWRITTEN

Locate a covered identifier and keep the case on hold for issuer verification.

Seller: Alder Trade Supplies Pte Ltd
Buyer: Cedar Commercial Services Pte Ltd
Invoice: AT-2026-1601
Flow: possible_tampering, appearance_hold

SETUP
Enable Check for possible document tampering. The invoice is an intentionally altered fictional test fixture: its old header number remains under a covering patch.

START WITH
01-invoice.pdf
02-full-receipt.pdf

EXPECTED FIRST RESULT
The visible values can agree while PDF layers reveal an overwritten invoice number. Appearance findings must prevent completion.

STEPS
1. Upload 01 and 02, with possible tampering enabled. Do not use reference-invoice.pdf as additional evidence; it is available for visual comparison only.
2. Open the appearance task and click the finding to highlight the edited identifier. Inspect both the PDF-layer observation and any Gemini observation.
3. Choose Keep the case on hold. Reason: An overwritten identifier needs independent confirmation and a newly issued original from the seller.

EXPECTED FINAL RESULT
Paused on hold, with the suspect area and reviewer reason retained. The app must not declare the document authentic or approve financing.

FILES
01-invoice.pdf: invoice
02-full-receipt.pdf: receipt
reference-invoice.pdf: invoice_template

All companies, people, addresses and transactions are fictional.
The business PDFs are test records, not genuine invoices or evidence of real deliveries.
