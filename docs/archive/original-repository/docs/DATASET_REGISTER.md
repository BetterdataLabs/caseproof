# CaseProof Dataset Register (Frozen v1)

Date: 01 October 2026
Updated: 02 October 2026 (alignment pass — metric scope column, licence verification gate)
Status: Frozen v1.1 for coding start

Purpose:
- Freeze dataset names, versions, and license classes before implementation.
- Provide one source of truth for what can be used in benchmark and demo evidence.

## 1) License model classes

1. `INTERNAL_PROPRIETARY`
- Internal synthetic or internal test assets. No external redistribution.

2. `PERMISSIVE_ATTRIBUTION`
- Public datasets allowed for benchmark usage with attribution.

3. `RESEARCH_RESTRICTED`
- Public datasets with restricted/research-style terms; benchmark-only usage and no raw redistribution.

## 2) Frozen dataset list

| Dataset ID | Name | Version | License class | Usage scope | Metric scope | Notes |
|---|---|---|---|---|---|---|
| `CP_SYNTH_TRADE_V1` | CaseProof Synthetic Trade Docs | `1.0.0` | `INTERNAL_PROPRIETARY` | Dev/Val/Holdout | Discrepancy, fraud, workflow metrics | Seeded generator output: invoice + POD(s) (+ optional PO/terms) PDFs, response documents, and label manifest. 120 cases; scenario coverage in `docs/BENCHMARK_EVIDENCE_PROTOCOL.md` §3. Ships with seeded counterparty registry, lender policy, and prior cases for duplicate detection. |
| `CP_TRUST_ATTACK_V1` | CaseProof Trust-Control Attack Set | `1.0.0` | `INTERNAL_PROPRIETARY` | Trust tests only | Trust metrics (T1–T11) | Scripted API scenarios: role abuse, scope abuse, bad reason codes, audit-failure injection, system auto-adjudication, fabricated-citation injection, demo-flag-off access, counterparty-report disclosure scan, report overwrite/tamper. |
| `PUB_DOCILE_V1` | DocILE public benchmark pack | `2023.1` | `PERMISSIVE_ATTRIBUTION`* | Dev/Val benchmark | Extraction accuracy only | Single invoices; no POD pairs. External credibility for field extraction. |
| `PUB_FUNSD_V1` | FUNSD public benchmark pack | `1.0` | `RESEARCH_RESTRICTED`* | Dev benchmark only | Extraction accuracy only | Form-structure stress; no raw redistribution. |
| `PUB_SROIE_V1` | SROIE receipt benchmark pack | `2019.3` | `RESEARCH_RESTRICTED`* | Dev benchmark only | Extraction accuracy only | Noisy OCR stress. |

\* Licence class for public datasets is provisional until the terms snapshot (§3) is captured and reviewed. If the actual terms are stricter than the class shown, reclassify before ingestion; if a dataset's terms prohibit this use, drop it — the core metrics depend only on `CP_*` datasets.

Public datasets are optional for Gate C. They strengthen extraction credibility but are not on the critical path.

## 3) Required compliance artifacts per dataset

Before ingestion for implementation/benchmark runs, each dataset must include:
1. `source_url`
2. `terms_snapshot_path`
3. `license_class`
4. `approved_by`
5. `approved_at`

Required storage path convention:
- `evidence/datasets/<dataset_id>/metadata.json`
- `evidence/datasets/<dataset_id>/TERMS.txt`

## 4) Usage policy

1. `PERMISSIVE_ATTRIBUTION` and `RESEARCH_RESTRICTED` datasets are benchmark inputs only.
2. Raw external files are not redistributed in public repo deliverables.
3. Published evidence uses aggregated metrics and anonymized examples.
4. Holdout evidence must include dataset ID list and versions.

## 5) Change control

Any dataset change requires updates to:
1. `docs/BENCHMARK_EVIDENCE_PROTOCOL.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/SESSION_LOG.md`

