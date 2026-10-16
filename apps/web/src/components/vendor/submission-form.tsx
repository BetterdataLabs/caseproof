"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Send } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, newKey, uploadCommand } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { VendorDetail } from "@/lib/vendor";
import { Button, Callout, Field, Select, Textarea } from "@/components/ui/primitives";
import { CreditResearchFields } from "@/components/case/credit-research";

const fileStyle =
  "block w-full rounded-xl border border-dashed border-teal-300 bg-teal-50/40 p-3 text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2 file:font-semibold file:text-teal-800";

export function SubmissionForm({
  detail,
  onComplete,
}: {
  detail?: VendorDetail;
  onComplete: (result: { id: string }) => void;
}) {
  const session = useSession();
  const qc = useQueryClient();
  const form = useRef<HTMLFormElement>(null);
  const intent = useRef<string | null>(null);
  const [attach, setAttach] = useState(false);
  const [kind, setKind] = useState("receipts");
  const [validation, setValidation] = useState("");
  const invoice = detail?.documents.find((d) => d.active && d.role === "invoice");
  const receipts = detail?.documents.filter((d) => d.active && d.role === "delivery_receipt") ?? [];
  const upload = useMutation({
    mutationFn: (body: FormData) =>
      uploadCommand<{ id: string }>(
        detail ? `/v1/vendor/cases/${detail.case.id}/inputs` : "/v1/vendor/cases",
        body,
        (intent.current ??= newKey("vendor")),
      ),
    onSuccess: (result) => {
      intent.current = null;
      form.current?.reset();
      setAttach(false);
      setKind("receipts");
      qc.invalidateQueries({ queryKey: ["vendor"] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      toast.success(
        detail
          ? "Your reply and documents have been sent to the bank"
          : "Submission received by the bank",
      );
      onComplete(result);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.isConflict) {
        intent.current = null;
        qc.invalidateQueries({ queryKey: ["vendor"] });
      }
    },
  });

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = new FormData(event.currentTarget);
    for (const key of ["invoice", "receipts"]) {
      const files = body.getAll(key).filter((v): v is File => v instanceof File && v.size > 0);
      body.delete(key);
      files.forEach((file) => body.append(key, file));
    }
    const files = [...body.getAll("invoice"), ...body.getAll("receipts")] as File[];
    if (
      files.length > 5 ||
      files.some((f) => f.size > 10 * 1024 * 1024) ||
      files.reduce((sum, f) => sum + f.size, 0) > 20 * 1024 * 1024
    ) {
      setValidation("Choose up to 5 documents, no more than 10 MiB each and 20 MiB in total.");
      return;
    }
    if (!files.length && !String(body.get("message") ?? "").trim()) {
      setValidation("Write a reply or attach a document before sending.");
      return;
    }
    if (detail) {
      body.set("expected_revision", String(detail.case.revision));
      if (attach && kind === "invoice" && invoice && files.length) body.set("replaces", invoice.id);
      if (!files.length) body.delete("replaces");
    }
    upload.mutate(body);
  }

  return (
    <form
      ref={form}
      onSubmit={submit}
      onChange={() => {
        intent.current = null;
        setValidation("");
        upload.reset();
      }}
      className="space-y-5"
    >
      <fieldset disabled={upload.isPending} className="space-y-5 disabled:opacity-60">
        {!detail && <CreditResearchFields vendor />}
        {!detail && (
          <>
            <p className="text-sm leading-relaxed text-muted">
              Submit one sale. The invoice shows what your customer owes; their delivery receipt
              confirms what arrived.
            </p>
            <Field
              label="Invoice"
              htmlFor="vendor-invoice"
              hint="Your company's invoice to the buyer."
            >
              <input
                id="vendor-invoice"
                name="invoice"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.docx,.xlsx,.csv,.txt"
                required
                className={fileStyle}
              />
            </Field>
            <Field
              label="Delivery and supporting documents (optional)"
              htmlFor="vendor-receipts"
              hint="Your buyer's acknowledgement of goods received for this invoice. You can add these later."
            >
              <input
                id="vendor-receipts"
                name="receipts"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.docx,.xlsx,.csv,.txt"
                multiple
                className={fileStyle}
              />
            </Field>
            <p className="text-xs leading-relaxed text-subtle">
              Upload PDFs, scans, images, Word documents, spreadsheets, CSV or text files. Multiple
              items, decimal quantities, currencies, taxes and charges are supported.
            </p>
          </>
        )}
        <Field
          label={detail ? "Your reply" : "Message to the bank (optional)"}
          htmlFor="vendor-message"
          hint={`Sent as ${session.user.name}. You can send documents without a written message.`}
        >
          <Textarea
            id="vendor-message"
            name="message"
            rows={3}
            maxLength={1200}
            placeholder={
              detail
                ? "Add the information requested by the bank…"
                : "Anything the bank should know about this submission…"
            }
          />
        </Field>
        {detail?.case.can_upload && (
          <>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<Paperclip className="size-4" />}
              onClick={() => {
                setAttach(!attach);
                intent.current = null;
              }}
            >
              {" "}
              {attach ? "Remove attachment fields" : "Attach documents"}
            </Button>
            {attach && (
              <div className="space-y-4 rounded-xl border border-line bg-canvas p-4">
                <Field label="What are you sending?" htmlFor="vendor-kind">
                  <Select id="vendor-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
                    <option value="receipts">Receipt for a delivery</option>
                    <option value="invoice">Updated invoice</option>
                    {receipts.length > 0 && (
                      <option value="receipt_correction">Correction to an earlier receipt</option>
                    )}
                  </Select>
                </Field>
                {kind === "invoice" && invoice && (
                  <p className="text-xs leading-relaxed text-muted">
                    This will replace invoice {invoice.number}, version {invoice.version}. The
                    original remains in the review history.
                  </p>
                )}
                {kind === "receipt_correction" && (
                  <Field
                    label="Which receipt does it correct?"
                    htmlFor="vendor-replaces"
                    hint="Choose the receipt this document corrects. Earlier versions stay in the record."
                  >
                    <Select id="vendor-replaces" name="replaces" required defaultValue="">
                      <option value="" disabled>
                        Choose the earlier receipt
                      </option>
                      {receipts.map((doc) => (
                        <option key={doc.id} value={doc.id}>
                          {doc.number} · version {doc.version}
                        </option>
                      ))}
                    </Select>
                  </Field>
                )}
                <Field
                  label="Documents"
                  htmlFor="vendor-attachment"
                  hint={
                    kind === "receipts"
                      ? "For a separate delivery, attach its receipt as new evidence."
                      : "Upload one corrected document."
                  }
                >
                  <input
                    key={kind}
                    id="vendor-attachment"
                    name={kind === "invoice" ? "invoice" : "receipts"}
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.docx,.xlsx,.csv,.txt"
                    multiple={kind === "receipts"}
                    required
                    className={fileStyle}
                  />
                </Field>
              </div>
            )}
          </>
        )}
        {(validation || upload.error) && (
          <Callout tone="red" title="Not sent yet">
            {validation ||
              (upload.error instanceof Error ? upload.error.message : "Please try again.")}
          </Callout>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <p className="max-w-xs text-xs text-subtle">
            Documents · 10 MiB per file · 20 MiB per submission
          </p>
          <Button type="submit" loading={upload.isPending} icon={<Send className="size-4" />}>
            {detail ? "Send to bank" : "Submit for review"}
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
