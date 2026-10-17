# CaseProof 3-Minute Judge Script (Proof-First)

Date: 26 September 2026
Target length: 2m45s to 3m00s

## 0:00-0:30 — Problem framing

"Trade-finance reviewers often receive invoice and delivery documents that disagree. Detecting mismatch is easy; deciding what to ask for, what got resolved, and what remains open is the expensive part. That creates delays, repeated requests, and avoidable operational cost."

"CaseProof is an AI-assisted discrepancy resolution copilot with an assistive fraud-risk layer that helps reviewers close clean cases faster without removing human control."

## 0:30-1:40 — Product walkthrough

"Here is a live case. The invoice states 100 units while proof of delivery shows 80."

"CaseProof extracts key fields, compares documents, and flags discrepancies. Each finding is linked to quote-backed evidence and source page references, so the reviewer can verify quickly. A second shipment line looks short too, but CaseProof reads the purchase order, sees partial delivery is permitted, and cites the clause — so it doesn't ask the customer for something they don't owe. Every quote you see has been checked against the actual page."

"In the same view, CaseProof shows fraud-risk signals, such as identity inconsistency between counterparty fields. These signals are assistive only and always reviewer-controlled."

"Next, CaseProof drafts a correction request. The reviewer edits and sends it."

"Now we simulate customer response. A revised invoice for 80 units arrives. CaseProof re-checks only the affected issues: the quantity check now passes and is marked ready to confirm, and the reviewer confirms it in one click. A separate registration-number mismatch stays open."

"At portfolio level, an operations leader can view live, blocked, paused, and escalated cases, then prioritize, escalate, or reassign bottlenecks with reason-coded actions that are fully logged."

"This issue lifecycle—detected, requested, resolved/open—is preserved in the case history. When the reviewer approves or rejects, CaseProof issues a sealed, hash-verified audit report for the bank and a clear decision letter for the client, so both sides hold the same record."

## 1:40-2:25 — Proof and impact

"We evaluate on labeled cases across four comparators: manual review, rules-only, LLM-only, and CaseProof hybrid."

"Key metrics are issue recall, false alarms on valid cases, median review time, missed critical issues, unnecessary requests, reopen rate, and high-severity fraud-signal precision."

"Our target is at least 90% issue recall, under 10% false alarms on valid cases, and at least 40% faster median review time, while keeping reviewers in full control."

"This is not just an AI summarizer; it is an auditable operations workflow accelerator with measurable quality and speed outcomes."

## 2:25-2:50 — Technical credibility

"Architecture is Gemini for document reasoning and request drafting, deterministic checks for quantity and arithmetic consistency, and an assistive fraud signal engine, deployed on Cloud Run with secure document storage and action logs."

"Design principle: AI proposes, rules verify, human decides."

## 2:50-3:00 — Close

"CaseProof turns document discrepancies from repetitive manual triage into evidence-backed, measurable resolution workflows. We reduce friction for both reviewers and businesses while maintaining BFSI-grade control and traceability."
