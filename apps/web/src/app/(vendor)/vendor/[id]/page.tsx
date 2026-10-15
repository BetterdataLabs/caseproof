"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  ChevronDown,
  Download,
  FileText,
  MessageSquare,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getJson } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { vendorTone, type VendorDetail, type VendorDocument } from "@/lib/vendor";
import { SubmissionForm } from "@/components/vendor/submission-form";
import { Badge, ErrorState, Skeleton } from "@/components/ui/primitives";

function Attachment({ caseId, document }: { caseId: string; document: VendorDocument }) {
  return (
    <a
      href={`/api/v1/vendor/cases/${caseId}/sources/${document.id}/original`}
      className="flex min-w-0 items-center gap-2 rounded-lg border border-line bg-paper px-3 py-2 text-xs text-teal-800 hover:bg-teal-50"
    >
      <FileText className="size-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1 break-words">{document.name}</span>
      <Download className="size-3.5 shrink-0" aria-hidden />
    </a>
  );
}

export default function VendorCasePage() {
  const { id } = useParams<{ id: string }>();
  const query = useQuery({
    queryKey: ["vendor", "case", id],
    queryFn: ({ signal }) => getJson<VendorDetail>(`/v1/vendor/cases/${id}`, signal),
    refetchInterval: 3000,
  });
  const detail = query.data;
  if (!detail)
    return query.error ? (
      <ErrorState error={query.error} onRetry={() => query.refetch()} />
    ) : (
      <Skeleton className="h-96" />
    );
  const c = detail.case;
  const latestRequest = detail.messages.findLast((message) => message.direction === "incoming")?.id;
  return (
    <>
      <Link
        href="/vendor"
        className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-teal-700"
      >
        <ArrowLeft className="size-4" />
        Requests &amp; submissions
      </Link>
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-xs text-subtle">{c.reference}</span>
          <Badge tone={vendorTone[c.status]}>{c.status_label}</Badge>
        </div>
        <h1 className="mt-3 break-words text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          {c.invoice ? `Invoice ${c.invoice}` : c.title}
        </h1>
        <p className="mt-2 text-sm text-muted">
          {c.invoice
            ? `${c.seller} → ${c.buyer}`
            : "Reading the seller, buyer and invoice details from your document."}
        </p>
      </div>
      <div className="mb-7 flex items-start gap-3 rounded-xl border border-teal-200 bg-teal-50 px-5 py-4">
        <MessageSquare className="mt-0.5 size-5 shrink-0 text-teal-700" />
        <div>
          <p className="text-sm font-semibold text-teal-900">{c.status_label}</p>
          <p className="mt-1 text-sm leading-relaxed text-teal-800">{c.next_step}</p>
          {c.research_status && (
            <p className="mt-2 text-xs text-teal-800">
              Company research:{" "}
              {c.research_status === "complete"
                ? "report available to the bank"
                : c.research_status === "failed"
                  ? "the bank can retry the research"
                  : "being prepared for the bank"}
              .
            </p>
          )}
        </div>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-5">
          <section
            aria-label="Conversation with the bank"
            className="overflow-hidden rounded-2xl border border-line bg-paper shadow-[var(--shadow-card)]"
          >
            <div className="border-b border-line px-5 py-4">
              <h2 className="font-semibold text-ink">Conversation with {detail.bank}</h2>
              <p className="mt-1 text-xs text-muted">
                Requests, documents and replies for this invoice.
              </p>
            </div>
            {detail.messages.map((message, index) => (
              <details
                key={message.id}
                open={index === detail.messages.length - 1 || message.id === latestRequest}
                className="group border-b border-line-soft last:border-0"
              >
                <summary className="flex cursor-pointer list-none items-start gap-3 p-5 [&::-webkit-details-marker]:hidden">
                  <span
                    className={`grid size-8 shrink-0 place-items-center rounded-lg ${message.direction === "incoming" ? "bg-navy-900 text-white" : "bg-teal-50 text-teal-700"}`}
                  >
                    {message.direction === "incoming" ? (
                      <Building2 className="size-4" />
                    ) : (
                      <UserRound className="size-4" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-1">
                      <p className="text-sm font-semibold text-ink">{message.sender}</p>
                      <span className="text-[11px] text-subtle">
                        {dateTime(message.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 break-words text-[13px] text-muted">{message.subject}</p>
                  </div>
                  <ChevronDown className="mt-1 size-4 shrink-0 text-subtle transition-transform group-open:rotate-180" />
                </summary>
                <div className="px-5 pb-5 sm:pl-16">
                  <p className="mb-3 text-xs text-subtle">To {message.recipient}</p>
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink">
                    {message.body}
                  </p>
                  {message.attachments.length > 0 && (
                    <div className="mt-4 space-y-2">
                      {message.attachments.map((doc) => (
                        <Attachment key={doc.id} caseId={id} document={doc} />
                      ))}
                    </div>
                  )}
                </div>
              </details>
            ))}
          </section>
          {c.can_reply && (
            <section className="rounded-2xl border border-line bg-paper p-5 shadow-[var(--shadow-card)]">
              <details open={c.status !== "complete"}>
                <summary className="cursor-pointer text-base font-semibold text-ink">
                  {c.status === "complete" ? "Send an update" : "Reply to the bank"}
                </summary>
                <div className="mt-4">
                  {c.status === "complete" && (
                    <p className="mb-4 text-sm text-muted">
                      New information reopens the document review.
                    </p>
                  )}
                  <SubmissionForm detail={detail} onComplete={() => query.refetch()} />
                </div>
              </details>
            </section>
          )}
        </div>
        <aside className="min-w-0 rounded-2xl border border-line bg-paper p-5">
          <h2 className="text-sm font-semibold text-ink">Documents on this submission</h2>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            Earlier versions stay available after a correction.
          </p>
          <div className="mt-4 space-y-4">
            {detail.documents.map((doc) => (
              <div key={doc.id}>
                <Attachment caseId={id} document={doc} />
                <p className="mt-1.5 text-[11px] text-subtle">
                  {doc.role === "invoice" ? "Invoice" : "Delivery receipt"}
                  {doc.version ? ` · version ${doc.version}` : ""} ·{" "}
                  {doc.state === "superseded"
                    ? "Replaced"
                    : doc.state === "rejected"
                      ? "Needs attention"
                      : doc.state === "ready"
                        ? "Received"
                        : doc.state === "withdrawn"
                          ? "Withdrawn"
                          : "Being read"}
                </p>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </>
  );
}
