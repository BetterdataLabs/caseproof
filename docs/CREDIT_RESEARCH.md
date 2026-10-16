# Public company credit research

Enable **Include company credit research** when Alex starts an uploaded case or Sam submits documents. Choose the buyer (default: the company owing the invoice) or seller, enter its country of registration, and optionally a registration number. The company name comes from the invoice; the option applies to that case only. Prepared demo cases are fictional and do not offer this option.

Alex and Aisha can browse all saved reports on the **Research** page, search by company, case or invoice, and filter by research status. Select a case to read its findings, cited sources, search queries and supporting passages. Pending, failed and archived cases remain available, and new results appear automatically. Each report is also available in the bank case view. Sam sees progress on their own submission, without the bank’s analysis. The completed document review’s PDF and JSON include the research result, including failures or insufficient evidence. Research does not approve financing or change the document checklist.

## What runs

The worker first extracts the invoice, then performs three separate Google Search grounding calls: identity and adverse information; financial reports; business and market conditions. A final Gemini call synthesizes only the returned grounded passages into six areas:

| Area                   | Evidence sought                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| Identity and ownership | Legal name, registration, jurisdiction and ownership; distinguish namesakes and subsidiaries                 |
| Repayment capacity     | Dated operating cash flow, repayment source and debt service information                                     |
| Financial strength     | Liquidity, leverage, capital, debt maturities and going-concern disclosures                                  |
| Conduct                | Public insolvency, enforcement, litigation and payment concerns; distinguish allegations and resolved events |
| Sector                 | Industry and country pressures relevant to the company                                                       |
| Concentration          | Customer, supplier and operating dependencies                                                                |

The search prompt receives only the company name, country, registration number, research angle and current date. Invoice amounts, documents, messages and internal case identifiers are not supplied to Search. The synthesis receives the identity and grounded search passages. Both stages use the existing Vertex Gemini model and bounded gateway.

The worker saves each step before queuing the next one. Searches are not repeated after successful settlement. Revision and lease checks prevent stale workers from changing a case. A failed step is visible and can be retried by a bank reviewer from saved progress. Retry preserves earlier frozen exports and supersedes them when a completed review is reopened. Pending research postpones the final summary; a failed or inconclusive result does not prevent completion of the document checklist.

## Interpretation

Each area has one of four signals: concern, mixed evidence, no concern identified in cited evidence, or insufficient evidence. These are model judgments for review, not verified credit grades.

Only provider-returned HTTPS grounding sources are accepted. Each assessment citation must reference a saved passage and reproduce text from it. These quotations are **Google-grounded model passages, not independently fetched quotations from the original websites**. Reviewers can open the original source links. Citation validation checks provenance and matching text, not whether every interpretation is correct.

Entity matching requires cited passages containing the supplied legal name, country and registration number when provided. This conservative text check can miss legitimate naming variants. It does not replace authoritative identity verification. Unconfirmed identity forces an inconclusive assessment. Unsupported citations make the affected area unknown.

The summary reports **Bank review needed**, **Insufficient information**, or **No material flags identified**. The last result requires usable evidence in all six areas and does not mean low credit risk. Evidence coverage is a count of supported areas, not a credit score. Dates, allegation status, source quality and financial reporting scope are evaluated by the model; this version has no independently calibrated freshness threshold or source-quality scoring engine.

A 0–100 credit score or probability of default would require a defined credit population, historical outcomes, verified financial inputs, calibration and validation against the bank’s policy. Public search alone does not supply these. The report instead identifies the additional financial statements, forecasts, payment history, facility terms and bank checks needed for an actual credit decision. It is a point-in-time brief; it does not continuously monitor the company.

## Google setup and costs

Uses `google-genai` with `Tool(google_search=GoogleSearch())` on the configured Vertex model, currently `gemini-3.8-flash`. Existing Application Default Credentials and Vertex project configuration apply. The rule controller does not simulate live search results; an unavailable provider produces a visible failed research result.

Google’s Gemini 3 pricing page, checked 13 October 2026, lists 5,000 search queries per month at no charge across Gemini 3 models and USD 14 per 1,000 additional queries. Model token charges apply separately. Availability and pricing depend on the project and current Google terms; no free allowance is assumed by the app.

Enabling research adds a one-time **USD 1.00 allowance** to the case's document-review budget (USD 1.50 total with the default USD 0.50 policy). `CASEPROOF_RESEARCH_BUDGET_USD` controls this additional allowance, with a minimum of USD 1.00. Older failed research requests receive the allowance on retry; repeated retries do not add it again. The allocation is recorded in case history. Search and synthesis calls can take up to 45 seconds within the existing invocation deadline.

`CASEPROOF_SEARCH_PRICE_PER_QUERY` defaults to `0.014`. `CASEPROOF_SEARCH_RESERVE_QUERIES` defaults to `10` per grounded call. The gateway reserves this allowance plus model tokens against case and daily budgets, then estimates search spend from returned query metadata. Missing metadata retains the query allowance. Unknown model usage retains the full reservation. The UI identifies the combined figure as estimated AI and search spend. Google does not expose a per-call query cap here: this allowance is not a hard bound on provider billing, and returned query metadata is not a billing statement. Set project quotas and billing controls for production use.

Grounded sources and queries are retained with the case and frozen exports. Google’s search suggestions are displayed in an isolated, script-disabled frame. Existing case retention applies; scheduled cleanup is not implemented. Review applicable provider retention and grounding terms before production deployment.

## Verification

For a manual check, use an authorised invoice naming an identifiable public company, choose that party and its correct registration country, then inspect **Company credit research → Sources and search record**. The fictional North Quay/Maple samples are useful for the insufficient-information path, not a meaningful assessment of a real company.

## Method references

- [Basel Committee: Principles for the management of credit risk, April 2025](https://www.bis.org/bcbs/publ/d595.htm): a sound credit-granting process, measurement, monitoring and controls. The six-area prototype is not a Basel rating model.
- [OCC: Commercial Loans, examination procedures 9–11](https://www.occ.gov/publications-and-resources/publications/comptrollers-handbook/files/commercial-loans/pub-ch-commercial-loans.pdf): credit-file evidence, current and preceding financial statements, cash flow, debt service, liquidity and collateral. This legacy handbook provides analytical context, not this app’s governing bank policy.
- [Google: Grounding with Google Search](https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search): supported models, grounding metadata and search suggestions.
- [Google: Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing): search allowances and query-based charges.
