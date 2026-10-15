"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileSearch } from "lucide-react";
import { useRef, useState } from "react";
import { ApiError, newKey, uploadCommand } from "@/lib/api";
import type { CaseDetail, VisualReview } from "@/lib/types";
import { Badge, Button, Callout, Card, Dialog, Field } from "@/components/ui/primitives";

export const REVIEW_LABEL: Record<VisualReview["status"], string> = {
  pending: "Check pending",
  review_required: "Needs appearance review",
  no_findings: "No obvious issues found",
  reviewed: "Reviewed by a person",
};

export function DocumentCheckFields() {
  return (
    <div className="space-y-4">
      <label className="flex items-start gap-3 text-sm text-ink">
        <input
          type="checkbox"
          name="tampering"
          value="true"
          className="mt-1 size-4 accent-teal-700"
        />
        <span>
          <span className="font-semibold">Check for possible document tampering</span>
          <span className="mt-1 block text-xs leading-relaxed text-muted">
            Inspect page images and PDF layers for covered text, inconsistent lettering and pasted
            regions.
          </span>
        </span>
      </label>
      <div className="rounded-xl border border-line bg-canvas p-4">
        <p className="text-sm font-semibold text-ink">Compare against a reference template</p>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Optional. Supply a trusted blank form or example from the bank or issuer. Layout and field
          placement are compared; transaction values may differ.
        </p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field
            label="Invoice reference PDF"
            htmlFor="invoice-template"
            hint="Leave blank to skip invoice template comparison."
          >
            <input
              id="invoice-template"
              name="invoice_template"
              type="file"
              accept="application/pdf,.pdf"
              className="w-full min-w-0 text-xs text-muted file:mr-2 file:rounded-md file:border-0 file:bg-white file:px-2 file:py-2 file:font-semibold file:text-teal-700"
            />
          </Field>
          <Field
            label="Receipt reference PDF"
            htmlFor="receipt-template"
            hint="Leave blank to skip receipt template comparison."
          >
            <input
              id="receipt-template"
              name="receipt_template"
              type="file"
              accept="application/pdf,.pdf"
              className="w-full min-w-0 text-xs text-muted file:mr-2 file:rounded-md file:border-0 file:bg-white file:px-2 file:py-2 file:font-semibold file:text-teal-700"
            />
          </Field>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-muted">
        References: up to 3 pages and 10 MiB each. Selections are fixed for this case and apply to
        later uploads. Suspicious or inconclusive results need a human decision. Visual checks can
        miss well-made alterations and do not certify authenticity. Longer documents require manual
        appearance review.
      </p>
    </div>
  );
}

export function DocumentChecksPanel({
  detail,
  onSource,
}: {
  detail: CaseDetail;
  onSource: (label: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [validation, setValidation] = useState("");
  const intent = useRef<{ key: string; body: FormData } | null>(null);
  const qc = useQueryClient();
  const config = detail.case.document_checks;
  const versions = detail.documents
    .flatMap((d) => d.versions)
    .filter(
      (v) =>
        v.visual_review &&
        v.state !== "superseded" &&
        v.state !== "withdrawn" &&
        v.coverage !== "not_required" &&
        !v.duplicate_of,
    );
  const enable = useMutation({
    mutationFn: (body: FormData) => {
      intent.current ??= { key: newKey("document-checks"), body };
      return uploadCommand(
        `/v1/cases/${detail.case.id}/document-checks`,
        intent.current.body,
        intent.current.key,
      );
    },
    onSuccess: () => {
      intent.current = null;
      qc.invalidateQueries({ queryKey: ["case", detail.case.id] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      setOpen(false);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status < 500) intent.current = null;
    },
  });
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = new FormData(event.currentTarget);
    for (const name of ["invoice_template", "receipt_template"]) {
      const value = body.get(name);
      if (value instanceof File && !value.name) body.delete(name);
    }
    const files = [...body.values()].filter((value): value is File => value instanceof File);
    if (!files.length && body.get("tampering") !== "true") {
      setValidation("Select a check or provide a reference PDF.");
      return;
    }
    if (files.some((f) => !f.name.toLowerCase().endsWith(".pdf") || f.size > 10 * 1024 * 1024)) {
      setValidation("Choose reference PDFs of at most 10 MiB each.");
      return;
    }
    body.set("expected_revision", String(detail.case.revision));
    enable.mutate(body);
  }
  return (
    <Card className="px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Optional document checks</h2>
          <p className="mt-1 text-xs text-muted">
            {config?.enabled
              ? `Selected by ${config.enabled_by} · applies to later uploads`
              : "Compare reference layouts and look for possible alterations."}
          </p>
        </div>
        {!config?.enabled &&
          detail.permissions.decide &&
          detail.case.automation_mode === "autonomous" &&
          detail.case.lifecycle !== "archived" && (
            <Button
              variant="secondary"
              size="sm"
              icon={<FileSearch className="size-4" />}
              onClick={() => setOpen(true)}
            >
              Enable document checks
            </Button>
          )}
      </div>
      {config?.enabled && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            {config.tampering && <Badge>Possible tampering</Badge>}
            {Object.entries(config.references).map(([role, ref]) => (
              <a
                key={role}
                className="text-xs font-medium text-teal-700 underline"
                href={`/api/v1/cases/${detail.case.id}/document-checks/templates/${role}/original`}
              >
                {role === "invoice" ? "Invoice" : "Receipt"} reference: {ref.name}
              </a>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {versions.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => onSource(v.label)}
                className="text-left"
              >
                <Badge tone={v.visual_review!.status === "review_required" ? "amber" : "neutral"}>
                  {v.label} · {REVIEW_LABEL[v.visual_review!.status]}
                </Badge>
              </button>
            ))}
          </div>
          <p className="text-xs text-muted">
            Results describe document appearance, not proof of authenticity.
          </p>
        </div>
      )}
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Enable document checks"
        description="Existing PDFs and future uploads on this case will be checked. A completed review will reopen."
        wide
      >
        <form
          onSubmit={submit}
          onChange={() => {
            setValidation("");
            intent.current = null;
            enable.reset();
          }}
          className="space-y-5"
        >
          <fieldset disabled={enable.isPending}>
            <DocumentCheckFields />
          </fieldset>
          {(validation || enable.error) && (
            <div role="alert">
              <Callout tone="red">{validation || enable.error?.message}</Callout>
            </div>
          )}
          <div className="flex justify-end">
            <Button type="submit" loading={enable.isPending}>
              Enable and check documents
            </Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}
