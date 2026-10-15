# Demo verification and evaluation

Use the [README](../README.md#run-locally) to start the app, then follow the [review workflow](../README.md#review-workflow). The downloadable examples, walkthroughs and saved evaluation report are included in the repository. Automated tests, evaluation runners and CI workflows are maintained locally and are not required to run the demo.

## Verify the interactive workflow

1. As **Sam**, submit the invoice and first receipt from the sample pack. Confirm that the new case appears in both the vendor and bank workspaces.
2. As **Alex**, inspect the source documents, extracted facts, checklist and issued request.
3. As **Sam**, supply the corrected invoice and remaining receipt. Wait for each upload to finish processing.
4. As **Alex**, inspect the completed review and download both the PDF and JSON summaries.
5. Send a written receipt dispute. Confirm that review reopens and a decision task refers to the message and affected evidence. Record a decision with a reason.
6. As **Aisha**, inspect the same case and its documents. Case-changing controls should be unavailable.

For the other features, use the [scenario library guide](../apps/web/public/sample-documents/scenarios/START-HERE.pdf), also available under **New case → Your documents → Browse the scenario library**. It contains **21 scenarios and 62 business PDFs**, with prerequisites, actions and expected results. Reference forms are labelled separately from transaction evidence.

| Scenarios | Flow exercised                                                                                                                      |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 01–04     | Clean completion, invoice correction, partial delivery and duplicate receipts                                                       |
| 05–09     | Buyer dispute and reopening, dispatch versus receipt, two gaps in one request, cumulative quantities and rejected replacement scope |
| 10–13     | Consistent, unrelated and instruction-like messages; an invoice outside the automatic checklist                                     |
| 14–16     | Matching reference forms, a changed supplier layout, and a covered invoice identifier requiring review                              |
| 17–19     | Reminder and no-response escalation, service recovery and a supervisor's budget extension                                           |
| 20–21     | Receipt withdrawal and summary supersession; manual, shadow and autonomous modes, progress and replay suppression                   |

Some scenarios deliberately remain open: scenario 13 includes tax and another goods line; scenario 16 holds a document for possible tampering. Scenario 08 needs a published policy permitting the quantity-basis change. The service-failure and budget scenarios include their own setup instructions.

## Check configurable features

**Policy criteria:** under **Policy → Edit policy**, add an invoice criterion titled **Payment terms are stated** with the text **The invoice must state when payment is due, either as a due date or a number of days.** Publish the version, then create a case or apply it to an existing case. Inspect the finding and source quotation under **Checklist → Review criteria and evidence**. Missing evidence should prompt a request; an uncertain assessment requires a reviewer interpretation.

**Appearance checks:** upload the corrected invoice and both receipts, using the original invoice as the invoice reference. To exercise a mismatch, use a receipt as the invoice reference on a separate case. A mismatch prompts review; it does not by itself establish forgery.

**Company research:** enable research for an authorised invoice naming an identifiable public company and select the correct registration country. Inspect **Company credit research → Sources and search record**. The fictional samples exercise insufficient-information handling. See [the research guide](CREDIT_RESEARCH.md) for interpretation.

## Saved comparison report

The app's **Evaluation** page reads [evaluation/results/latest.json](../evaluation/results/latest.json). It records 60 constructed cases across 12 scenario families, run on **12 October 2026** with Gemini 3.8 Flash through Vertex AI's global endpoint.

| Agent result                                     | Recorded value |
| ------------------------------------------------ | -------------- |
| Incorrect / missed completions                   | 0 / 0          |
| False / missed escalations                       | 0 / 0          |
| Repeated requests                                | 0              |
| Routine cases completed without a staff decision | 20 / 20        |
| Message classifications matching expectations    | 15 / 15        |
| Instruction-injection cases flagged              | 5 / 5          |
| Model calls                                      | 342            |
| Model cost                                       | USD 0.8316     |

The fixed-rule baseline also had no incorrect or missed completions. Estimated staff time was 100 minutes for the baseline and 110 for the agent. Those estimates come from the report's time model, not a user study, and do not establish a staff-time advantage. The comparison does not measure arbitrary uploaded-PDF extraction accuracy.

The current report uses corrected receipt timestamps. The [superseded report](archive/evaluation/gemini-3.8-flash-original-fixtures.json) remains available as a historical artifact.

## Saved PDF scenario results

The [manual scenario report](archive/evaluation/manual-pdf-scenarios.json) records live checks with Gemini 3.8 Flash on **13 October 2026**: **21/21 scenarios passed across 57 checkpoints**. The run submitted the downloadable PDFs through the API and worker, carried out the documented replies and decisions, and retrieved completed summaries. Each result retains the scenario and PDF hashes, model, checks and cost.

These are functional checks of constructed cases. They are not a production error-rate estimate or a forgery-detection benchmark. Cloud deployment and load capacity have not been validated; use the [hosted verification steps](DEPLOYMENT.md#8-start-reconciliation-and-verify-the-app) after deployment.
