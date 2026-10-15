"use client";

import {
  Bot,
  Calculator,
  CheckCircle2,
  Clock3,
  PackageCheck,
  FileCheck2,
  UserRound,
  XCircle,
} from "lucide-react";
import { sgd, humanize } from "@/lib/format";
import type { CaseDetail, Question } from "@/lib/types";
import { Card, CardHeader, Tip, cx } from "@/components/ui/primitives";
import { QuestionStateChip } from "@/components/ui/status";

export function Checklist({
  detail,
  onSource,
}: {
  detail: CaseDetail;
  onSource: (label: string) => void;
}) {
  const resolved = detail.questions.filter((q) => q.state === "resolved").length;
  return (
    <Card>
      <CardHeader
        title="Checklist"
        description={`Checks and review criteria from policy v${detail.case.policy.version}. Open the evidence to inspect each finding.`}
        actions={
          <span className="text-[13px] font-semibold text-muted tabular">
            {resolved} of {detail.questions.length} resolved
          </span>
        }
      />
      <ul className="divide-y divide-line-soft">
        {detail.questions.map((q) => (
          <QuestionRow key={q.id} q={q} detail={detail} onSource={onSource} />
        ))}
      </ul>
    </Card>
  );
}

function QuestionRow({
  q,
  detail,
  onSource,
}: {
  q: Question;
  detail: CaseDetail;
  onSource: (label: string) => void;
}) {
  const pass = q.check_result === "pass";
  const result =
    (
      {
        pass: "Passed",
        fail: "Needs correction",
        missing: "Evidence missing",
        blocked: "Needs review",
        pending: "Not checked yet",
      } as Record<string, string>
    )[q.check_result] ?? humanize(q.check_result);
  const outstanding = detail.requests.flatMap((r) =>
    r.state === "issued"
      ? r.items
          .filter((i) => i.question_key === q.key && ["outstanding", "progress"].includes(i.status))
          .map((i) => ({ ...i, round: r.round }))
      : [],
  );
  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={cx(
              "mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg",
              q.state === "resolved" ? "bg-teal-100 text-teal-800" : "bg-[#f1f4f3] text-muted",
            )}
          >
            {q.key === "invoice_total" ? (
              <Calculator className="size-4" aria-hidden />
            ) : q.key === "delivery_receipts" ? (
              <PackageCheck className="size-4" aria-hidden />
            ) : (
              <FileCheck2 className="size-4" aria-hidden />
            )}
          </span>
          <div className="min-w-0">
            <p className="text-[14.5px] font-semibold text-ink">{q.label}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[12px] text-muted">
              {pass ? (
                <CheckCircle2 className="size-3.5 text-teal-600" aria-hidden />
              ) : q.check_result === "pending" ? (
                <Clock3 className="size-3.5" aria-hidden />
              ) : (
                <XCircle className="size-3.5 text-amber-600" aria-hidden />
              )}
              Document check: {result} · {humanize(q.reason_code)}
            </p>
          </div>
        </div>
        <QuestionStateChip state={q.state} />
      </div>
      <div className="ml-11 mt-3 space-y-3">
        <QuestionVisual q={q} />
        <p className="text-[13.5px] leading-relaxed text-ink/90">{q.detail}</p>
        {Boolean(q.metrics.policy_assessment) && <PolicyEvidence q={q} onSource={onSource} />}
        <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
          {q.evidence.length > 0 && <span className="text-subtle">Evidence</span>}
          {q.evidence.map((label) => (
            <button
              key={label}
              aria-label={`View source document ${label}`}
              onClick={() => onSource(label)}
              className="rounded-md border border-line bg-white px-1.5 py-0.5 font-semibold text-teal-700 hover:border-teal-300 hover:bg-teal-50"
            >
              {label}
            </button>
          ))}
          {q.state === "resolved" && q.resolved_by && (
            <span className="ml-1 inline-flex items-center gap-1 text-subtle">
              {q.resolved_by === "agent" ? (
                <Bot className="size-3.5" aria-hidden />
              ) : (
                <UserRound className="size-3.5" aria-hidden />
              )}
              Closed by the{" "}
              {q.resolved_by === "agent" ? "agent via the completion rules" : q.resolved_by} at
              revision {q.resolved_revision}
            </span>
          )}
        </div>
        {outstanding.map((i) => (
          <p
            key={i.id}
            className="rounded-lg bg-violet-100/60 px-3 py-2 text-[12.5px] text-violet-700"
          >
            Requested in round {i.round}
            {i.status === "progress" && i.progress_note
              ? ` · progress reported: ${i.progress_note}`
              : " · awaiting the business"}
          </p>
        ))}
      </div>
    </li>
  );
}

function PolicyEvidence({ q, onSource }: { q: Question; onSource: (label: string) => void }) {
  const finding = q.metrics.policy_assessment as {
    detail: string;
    citations: { source_label: string; quote: string }[];
    disposition?: { reviewed_by: string; reason: string } | null;
  };
  return (
    <details className="rounded-lg border border-line-soft bg-canvas/40 p-3 text-xs">
      <summary className="cursor-pointer font-semibold text-teal-800">
        Review criteria and evidence
      </summary>
      <p className="mt-2 leading-relaxed text-muted">{q.criteria}</p>
      {finding.detail !== q.detail && <p className="mt-2 text-ink">{finding.detail}</p>}
      {finding.citations.map((citation, i) => (
        <blockquote
          key={i}
          className="mt-2 border-l-2 border-teal-200 pl-3 leading-relaxed text-muted"
        >
          <button
            className="mr-1 font-semibold text-teal-700 underline"
            onClick={() => onSource(citation.source_label)}
          >
            {citation.source_label}
          </button>
          “{citation.quote}”
        </blockquote>
      ))}
      {finding.disposition && (
        <p className="mt-2 text-muted">
          Reviewed by {finding.disposition.reviewed_by}: {finding.disposition.reason}
        </p>
      )}
    </details>
  );
}

function QuestionVisual({ q }: { q: Question }) {
  const m = q.metrics as Record<
    string,
    | string
    | number
    | { delivery_ref: string; quantity: string; receipts: string[]; received_at: string }[]
  >;
  if (q.key === "invoice_total" && m.expected_total !== undefined) {
    const ok = m.stated_total === m.expected_total;
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-line bg-[#fafbfa] px-4 py-3 text-[13.5px] tabular">
        <span className="text-muted">
          {String(m.quantity)} {String(m.unit)} × {sgd(m.unit_price)}
        </span>
        <span className="text-subtle">=</span>
        <span className="font-semibold text-ink">{sgd(m.expected_total)}</span>
        <span className="text-subtle">{ok ? "matches" : "but the invoice states"}</span>
        {!ok && (
          <span className="rounded-md bg-amber-100 px-2 py-0.5 font-bold text-amber-700">
            {sgd(m.stated_total)}
          </span>
        )}
        {ok && <CheckCircle2 className="size-4 text-teal-600" aria-label="matches" />}
      </div>
    );
  }
  if (q.key === "delivery_receipts" && m.invoiced_quantity !== undefined) {
    const invoiced = Number(m.invoiced_quantity);
    const events =
      (m.events as {
        delivery_ref: string;
        quantity: string;
        receipts: string[];
        received_at: string;
      }[]) ?? [];
    const received = Number(m.received_quantity ?? 0);
    return (
      <div className="rounded-xl border border-line bg-[#fafbfa] px-4 py-3">
        <div className="flex items-center justify-between text-[12.5px]">
          <span className="font-semibold text-ink tabular">
            {received} of {invoiced} {String(m.unit)} received
          </span>
          {invoiced - received > 0 && (
            <span className="font-semibold text-amber-700 tabular">
              {invoiced - received} without receipt
            </span>
          )}
        </div>
        <div
          className="mt-2 flex h-3 w-full gap-[2px] overflow-hidden rounded-full bg-[#e3e9e7]"
          role="img"
          aria-label={`${received} of ${invoiced} received across ${events.length} deliveries`}
        >
          {events.map((e) => (
            <Tip
              key={e.delivery_ref}
              content={`${e.delivery_ref}: ${e.quantity} ${String(m.unit)} · ${e.receipts.join(", ")} · ${e.received_at}`}
            >
              <span
                className="h-full bg-teal-600 first:rounded-l-full"
                style={{ width: `${(Number(e.quantity) / Math.max(invoiced, 1)) * 100}%` }}
              />
            </Tip>
          ))}
        </div>
        {events.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
            {events.map((e) => (
              <span key={e.delivery_ref}>
                <span className="font-semibold text-ink">{e.delivery_ref}</span> {e.quantity} ·{" "}
                {e.receipts.join(", ")}
              </span>
            ))}
            {Array.isArray(m.copies_ignored) &&
              (m.copies_ignored as unknown as string[]).length > 0 && (
                <span>
                  copies counted once: {(m.copies_ignored as unknown as string[]).join(", ")}
                </span>
              )}
          </div>
        )}
      </div>
    );
  }
  return null;
}
