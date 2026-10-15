CASEPROOF | MANUAL, SHADOW AND AUTONOMOUS MODES

The same case obeys its selected action authority.

Seller: Harbour Lane Trading Pte Ltd
Buyer: Meridian Foods Pte Ltd
Invoice: INV-101
Flow: off_mode, manual_fallback, shadow_mode, autonomous_mode, structured_dispatch_update, exact_replay

SETUP
Use New case > Demo scenarios > Packaging boxes - invoice INV-101. Select Off (manual) before creating the case. The included PDFs match this prepared sale.

START WITH
01-inv-101-v1.pdf
02-r1-d1.pdf

EXPECTED FIRST RESULT
Off mode queues no agent. Manual checks expose both gaps; shadow mode may draft but must not issue a request.

STEPS
1. Create INV-101 in Off (manual) mode. In Controls, run the manual checklist checks.
2. Switch to Shadow and run the agent if prompted. Inspect proposals: no request should be Issued and no review should complete.
3. Switch to Autonomous. The agent should issue the tracked request for both gaps.
4. In Customer exchange (demo), send the remaining-20-boxes dispatch update. It must not count as receipt.
5. Send Receipt R2 for D2, then its duplicate copy. The duplicate must not add another 20 boxes or reset allowances.
6. Send the amount-only invoice v2 correction. Wait for completion.

EXPECTED FINAL RESULT
Document review completes with a retained summary.

FILES
01-inv-101-v1.pdf: invoice
02-r1-d1.pdf: receipt
03-r2-d2.pdf: receipt
04-inv-101-v2.pdf: invoice

All companies, people, addresses and transactions are fictional.
The business PDFs are test records, not genuine invoices or evidence of real deliveries.
