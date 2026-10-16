"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, getJson, newKey, uploadCommand } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
import { Button, Callout, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { DocumentCheckFields } from "@/components/case/document-checks";
import { CreditResearchFields } from "@/components/case/credit-research";
import { VendorContactField } from "@/components/case/vendor-contact";

const fileStyle =
  "block w-full rounded-xl border border-dashed border-teal-300 bg-teal-50/40 p-4 text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2 file:text-sm file:font-semibold file:text-teal-800 focus-visible:outline-2 focus-visible:outline-teal-700";

export function DocumentIntakeForm({
  detail,
  onComplete,
}: {
  detail?: CaseDetail;
  onComplete: (result: { id: string; reference?: string }) => void;
}) {
  const qc = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const intent = useRef<{ key: string; body: FormData } | null>(null);
  const [validation, setValidation] = useState("");
  const [hasMessage, setHasMessage] = useState(false);
  const initial = !detail;
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: ({ signal }) =>
      getJson<{
        policies: { status: string; definition: { limits: Record<string, string | number> } }[];
      }>("/v1/policies", signal),
    enabled: initial,
  });
  const limits =
    detail?.case.policy.limits ??
    policies.data?.policies.find((p) => p.status === "published")?.definition.limits;
  const maxFileBytes = Number(limits?.max_bytes_per_original ?? 10 * 1024 * 1024);
  const maxFileMiB = maxFileBytes / (1024 * 1024);
  const maxPages = Number(limits?.max_pages_per_document ?? 20);
  const canRead = initial || detail.case.automation_mode === "autonomous";
  const active =
    detail?.documents.flatMap((d) =>
      d.versions
        .filter((v) => v.is_active && ["invoice", "delivery_receipt"].includes(v.role))
        .map((v) => ({ ...v, title: d.title })),
    ) ?? [];
  const upload = useMutation({
    mutationFn: (body: FormData) => {
      intent.current ??= { key: newKey("upload"), body };
      return uploadCommand<{ id: string; reference?: string }>(
        initial ? "/v1/cases/upload" : `/v1/cases/${detail.case.id}/inputs`,
        intent.current.body,
        intent.current.key,
      );
    },
    onSuccess: (result) => {
      intent.current = null;
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["case", detail?.case.id] });
      formRef.current?.reset();
      setHasMessage(false);
      toast.success(
        initial ? "Case created — reading your documents" : "Documents and reply saved",
      );
      onComplete(result);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status < 500) {
        intent.current = null;
        qc.invalidateQueries({ queryKey: ["case", detail?.case.id] });
      }
    },
  });

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidation("");
    const body = new FormData(event.currentTarget);
    // Browsers include an empty File for an unselected optional file input.
    for (const name of ["invoice", "receipts", "invoice_template", "receipt_template"]) {
      const files = body.getAll(name).filter((f): f is File => f instanceof File && f.name !== "");
      body.delete(name);
      files.forEach((f) => body.append(name, f));
    }
    const files = [...body.values()].filter((f): f is File => f instanceof File);
    if (files.some((f) => f.size > maxFileBytes)) {
      setValidation(`Choose files of at most ${maxFileMiB} MiB each under this policy.`);
      return;
    }
    const evidenceFiles = [...body.getAll("invoice"), ...body.getAll("receipts")];
    if (evidenceFiles.length > 5 || files.reduce((n, f) => n + f.size, 0) > 20 * 1024 * 1024) {
      setValidation(
        "Choose up to 5 evidence documents. All files, including references, must total at most 20 MiB.",
      );
      return;
    }
    if (!files.length && !String(body.get("message") ?? "").trim()) {
      setValidation("Add a document or write a reply.");
      return;
    }
    if (body.get("replaces") && files.length !== 1) {
      setValidation("Upload one correction at a time when replacing a document.");
      return;
    }
    if (detail) body.set("expected_revision", String(detail.case.revision));
    upload.mutate(body);
  }

  return (
    <form
      ref={formRef}
      onSubmit={submit}
      onChange={() => {
        intent.current = null;
        setValidation("");
        upload.reset();
      }}
      className="space-y-5"
    >
      <fieldset disabled={upload.isPending} className="space-y-5 disabled:opacity-60">
        <p className="text-sm leading-relaxed text-muted">
          {initial
            ? "Review one sale: the seller’s invoice shows what the buyer owes; the buyer’s delivery receipts confirm what arrived. The agent checks whether they agree."
            : "Add the documents requested in the checklist. A corrected invoice replaces the old invoice; a receipt for another delivery is new evidence. You can leave the written reply blank."}
        </p>
        {canRead ? (
          <>
            <Field
              label={initial ? "Invoice" : "Invoice (optional)"}
              htmlFor="intake-invoice"
              hint={
                initial
                  ? "The seller’s bill to the buyer, showing the goods, quantity, price and total. Example: 01-invoice.pdf from North Quay Supplies to Maple Retail."
                  : "Upload a corrected bill for this same sale, then select the earlier invoice below. Example: 03-corrected-invoice.pdf."
              }
            >
              <input
                id="intake-invoice"
                name="invoice"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.docx,.xlsx,.csv,.txt"
                required={initial}
                className={fileStyle}
              />
            </Field>
            <Field
              label="Delivery and supporting documents (optional)"
              htmlFor="intake-receipts"
              hint={
                initial
                  ? "The buyer’s confirmation of goods received for this invoice. Example: 02-first-receipt.pdf from Maple Retail confirms 60 boxes. You can add receipts later."
                  : "Proof that the buyer received goods for this invoice. A receipt for another delivery adds to the quantity already received. Example: 04-remaining-receipt.pdf adds 40 boxes."
              }
            >
              <input
                id="intake-receipts"
                name="receipts"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.docx,.xlsx,.csv,.txt"
                multiple
                className={fileStyle}
              />
            </Field>
            {!initial && active.length > 0 && (
              <Field
                label="Replacing an earlier document?"
                htmlFor="intake-replaces"
                hint="For another delivery, keep ‘No — adding new evidence’. For a correction, choose the earlier invoice or receipt it fixes and upload just that one file. The original stays in history. S1, S2, etc. identify files; version 1 is the first version."
              >
                <Select id="intake-replaces" name="replaces" defaultValue="">
                  <option value="">No — adding new evidence</option>
                  {active.map((v) => (
                    <option key={v.id} value={v.id}>
                      Replace {v.title} · version {v.version_no} ({v.label})
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <details className="text-xs leading-relaxed text-muted">
              <summary className="cursor-pointer font-semibold text-teal-700">
                Document formats and processing limits
              </summary>
              <p className="mt-2">
                Upload PDFs, scans, images, Word documents, spreadsheets, CSV or text files. The
                review supports multiple items, decimal quantities, currencies, taxes and other
                charges. Each file may contain up to {maxPages} pages or sheets and {maxFileMiB}{" "}
                MiB; each upload may include 5 documents totaling 20 MiB. Unreadable or incomplete
                content is identified for review. Appearance checks currently apply to PDFs.
              </p>
            </details>
          </>
        ) : (
          <Callout tone="amber">
            Turn on autonomous mode in Controls to read uploaded documents. You can still add a
            written reply.
          </Callout>
        )}
        {initial && <VendorContactField />}
        {initial && <CreditResearchFields />}
        {initial && (
          <details className="rounded-xl border border-line p-4">
            <summary className="cursor-pointer text-sm font-semibold text-teal-700">
              Optional document checks
            </summary>
            <div className="mt-4">
              <DocumentCheckFields />
            </div>
          </details>
        )}
        {!initial && detail.case.document_checks?.enabled && (
          <p className="text-xs text-muted">
            This case’s optional document checks also apply to these PDFs.
          </p>
        )}
        <Field
          label={initial ? "Written message (optional)" : "Written reply (optional)"}
          htmlFor="intake-message"
          hint="Leave blank if you are only uploading documents. Otherwise, paste a message from the seller or buyer. The agent compares it with the documents and opens a human review task, even if the message agrees with them."
        >
          <Textarea
            id="intake-message"
            name="message"
            maxLength={1200}
            rows={3}
            onChange={(e) => setHasMessage(Boolean(e.target.value.trim()))}
            placeholder="Only if you have a message, e.g. ‘We corrected the invoice total to SGD 2,500.’"
          />
        </Field>
        {hasMessage && (
          <Field
            label="Who wrote this message? (optional)"
            htmlFor="intake-sender"
            hint="Enter the original sender, even if you are pasting their words. For example: North Quay Supplies corrects its invoice; Maple Retail confirms goods received. If blank, the message is recorded under your signed-in name."
          >
            <Input
              id="intake-sender"
              name="sender"
              maxLength={200}
              placeholder="For example: North Quay Supplies — accounts team"
            />
          </Field>
        )}
        {initial && (
          <p className="text-xs leading-relaxed text-muted">
            Need files to try it?{" "}
            <a
              className="font-semibold text-teal-700 underline"
              href="/sample-documents/caseproof-upload-example.zip"
              download
            >
              Download the invoice example
            </a>{" "}
            or{" "}
            <a
              className="font-semibold text-teal-700 underline"
              href="/sample-documents/scenarios/index.html"
              target="_blank"
              rel="noopener"
            >
              Browse the scenario library
            </a>
            , with documents and step-by-step guides.
          </p>
        )}
      </fieldset>
      {(validation || upload.error) && (
        <div role="alert">
          <Callout tone="red" title="Could not save">
            {validation || upload.error?.message}
          </Callout>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-4">
        <p className="text-xs text-subtle">This saves evidence to the case. No email is sent.</p>
        <Button type="submit" loading={upload.isPending} icon={<FileUp className="size-4" />}>
          {initial ? "Start review" : "Add to case"}
        </Button>
      </div>
    </form>
  );
}
