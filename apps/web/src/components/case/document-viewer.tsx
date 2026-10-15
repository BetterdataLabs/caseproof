"use client";

import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Hash,
  ImageOff,
  Quote,
} from "lucide-react";
import { useMemo, useState } from "react";
import { bytes, dateTime, humanize } from "@/lib/format";
import type { CaseDetail, SourceVersion } from "@/lib/types";
import { Badge, Card, EmptyState, Mono, SectionLabel, Tip, cx } from "@/components/ui/primitives";
import { roleIcon, sourceStateBadge } from "@/components/ui/status";
import { REVIEW_LABEL } from "@/components/case/document-checks";

const FACT_LABEL: Record<string, string> = {
  invoice_number: "Invoice number",
  version: "Version",
  replaces_version: "Replaces version",
  issue_date: "Issue date",
  seller: "Seller",
  seller_uen: "Seller UEN",
  buyer: "Buyer",
  payment_terms: "Payment terms",
  item: "Item",
  quantity: "Quantity",
  unit: "Unit",
  unit_price: "Unit price",
  tax: "Tax",
  other_charges: "Other charges",
  total_amount: "Total amount",
  receipt_number: "Receipt number",
  delivery_ref: "Delivery reference",
  invoice_ref: "Invoice reference",
  issued_by: "Issued by",
  supplier: "Supplier",
  received_at: "Received at",
  basis: "Quantity basis",
  condition: "Condition",
};
const KEY_FACTS = new Set([
  "quantity",
  "unit_price",
  "total_amount",
  "delivery_ref",
  "received_at",
  "basis",
  "replaces_version",
  "issued_by",
]);

export function allVersions(detail: CaseDetail): (SourceVersion & { number: string })[] {
  return detail.documents
    .flatMap((d) => d.versions.map((v) => ({ ...v, number: d.number })))
    .sort((a, b) => Number(a.label.slice(1)) - Number(b.label.slice(1)));
}

export function DocumentViewer({
  detail,
  selected,
  onSelect,
}: {
  detail: CaseDetail;
  selected: string | null;
  onSelect: (label: string) => void;
}) {
  const versions = useMemo(() => allVersions(detail), [detail]);
  const current = versions.find((v) => v.label === selected) ?? versions[0];

  if (!versions.length) {
    return (
      <Card>
        <EmptyState icon={<FileText className="size-5" />} title="No sources yet" />
      </Card>
    );
  }
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-line-soft px-4 pb-3 pt-4">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-ink">Evidence</h2>
          <span className="text-[12px] text-subtle">
            {versions.length} source version{versions.length === 1 ? "" : "s"}
          </span>
        </div>
        <div
          className="scroll-thin -mx-1 mt-3 flex gap-1.5 overflow-x-auto px-1 pb-1"
          role="tablist"
          aria-label="Case sources"
        >
          {versions.map((v) => {
            const badge = sourceStateBadge(v);
            const active = v.label === current.label;
            return (
              <button
                key={v.id}
                role="tab"
                aria-selected={active}
                onClick={() => onSelect(v.label)}
                className={cx(
                  "flex shrink-0 items-center gap-1.5 rounded-lg border px-2 py-1.5 text-[12.5px] font-semibold transition-colors",
                  active
                    ? "border-teal-700 bg-teal-50 text-teal-800"
                    : "border-line bg-white text-muted hover:border-teal-300",
                  v.state === "rejected" &&
                    v.coverage === "blocking" &&
                    !active &&
                    "border-red-200 text-red-700",
                  v.coverage === "needs_review" && !active && "border-amber-200 text-amber-700",
                  ["superseded", "withdrawn"].includes(v.state) && !active && "opacity-70",
                )}
              >
                {roleIcon(v.role, "size-3.5")}
                {v.label}
                {badge.tone === "amber" && (
                  <span className="size-1.5 rounded-full bg-amber-600" aria-label="needs review" />
                )}
                {badge.tone === "red" && (
                  <span className="size-1.5 rounded-full bg-red-600" aria-label="not accepted" />
                )}
              </button>
            );
          })}
        </div>
      </div>
      <SourceDetail
        key={current.id}
        caseId={detail.case.id}
        v={current}
        referencePages={detail.case.document_checks?.references[current.role]?.page_count ?? 1}
      />
    </Card>
  );
}

function SourceDetail({
  caseId,
  v,
  referencePages,
}: {
  caseId: string;
  v: SourceVersion & { number: string };
  referencePages: number;
}) {
  const [page, setPage] = useState(1);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [referenceOpen, setReferenceOpen] = useState(false);
  const review = v.visual_review;
  const finding = highlight === null ? null : review?.findings[highlight];
  const badge = sourceStateBadge(v);
  const BadgeIcon = badge.icon;
  const facts = v.facts;

  return (
    <div className="animate-[var(--animate-fade-in)]">
      <div className="px-4 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-[14.5px] font-semibold text-ink">
              <span className="text-teal-700">{roleIcon(v.role)}</span>
              {v.role_label} {v.number}
              {v.version_no && v.role !== "written_message" && v.role !== "status_update" && (
                <span className="font-normal text-muted">· v{v.version_no}</span>
              )}
            </p>
            <p className="mt-0.5 break-words text-[12px] text-muted">
              {v.label} · received {dateTime(v.created_at)} ·{" "}
              {v.received_via === "initial"
                ? "initial dossier"
                : v.received_via === "reply"
                  ? "reply from the business"
                  : v.received_via}
            </p>
          </div>
          <Badge tone={badge.tone} icon={<BadgeIcon className="size-3" aria-hidden />}>
            {badge.label}
          </Badge>
        </div>
        {v.reject_detail && (
          <p
            className={cx(
              "mt-3 rounded-lg px-3 py-2 text-[12.5px]",
              v.state === "rejected" && v.coverage === "blocking"
                ? "bg-red-50 text-red-700"
                : "bg-[#f3f6f5] text-muted",
            )}
          >
            {v.reject_code && <span className="font-semibold">{humanize(v.reject_code)}: </span>}
            {v.reject_detail}
          </p>
        )}
      </div>

      {review && (
        <section
          className="mx-4 mt-4 rounded-xl border border-line bg-canvas p-3"
          aria-label="Document appearance findings"
        >
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-ink">Document appearance</h3>
            <Badge tone={review.status === "review_required" ? "amber" : "neutral"}>
              {REVIEW_LABEL[review.status]}
            </Badge>
          </div>
          {review.summary && (
            <p className="mt-2 text-xs leading-relaxed text-ink">{review.summary}</p>
          )}
          <dl className="mt-2 space-y-1 text-xs text-muted">
            {review.template_requested && (
              <div>
                <dt className="inline font-medium">Template: </dt>
                <dd className="inline">
                  {review.template ? humanize(review.template) : "Pending"}
                </dd>
              </div>
            )}
            {review.tampering_requested && (
              <div>
                <dt className="inline font-medium">Possible tampering: </dt>
                <dd className="inline">
                  {review.tampering ? humanize(review.tampering) : "Pending"}
                </dd>
              </div>
            )}
            {review.pages_examined !== undefined && (
              <div>
                <dt className="inline font-medium">Pages examined: </dt>
                <dd className="inline">
                  {review.pages_examined} of {review.page_count}
                </dd>
              </div>
            )}
          </dl>
          {review.findings.length > 0 && (
            <ul className="mt-3 space-y-2">
              {review.findings.map((f, index) => (
                <li key={index} className="rounded-lg border border-amber-200 bg-amber-50 p-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      setPage(f.page);
                      setHighlight(index);
                    }}
                    className="text-left text-xs font-semibold text-amber-800 underline"
                  >
                    Page {f.page} · {f.title}
                  </button>
                  <p className="mt-1 text-xs leading-relaxed text-ink">{f.detail}</p>
                  <p className="mt-1 text-[11px] text-muted">
                    {f.origin === "pdf_structure"
                      ? "PDF layer observation"
                      : "Gemini visual observation"}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {review.reviewed_by && (
            <p className="mt-2 text-xs text-muted">
              Reviewed by {review.reviewed_by}: {review.review_reason}
            </p>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-muted">{review.limitation}</p>
          {review.template_requested && (
            <button
              type="button"
              className="mt-3 text-xs font-semibold text-teal-700 underline"
              onClick={() => setReferenceOpen(!referenceOpen)}
            >
              {referenceOpen ? "Hide reference template" : "Show reference template"}
            </button>
          )}
        </section>
      )}

      {referenceOpen && review?.template_requested && (
        <div className="mx-4 mt-3">
          <p className="mb-2 text-xs font-semibold text-muted">
            Reference: {review.template_name} · page {Math.min(page, referencePages)}
          </p>
          <Preview
            key={`reference-${v.role}-${Math.min(page, referencePages)}`}
            src={`/api/v1/cases/${caseId}/document-checks/templates/${v.role}/preview?page=${Math.min(page, referencePages)}`}
            alt={`Reference template for ${v.role_label}`}
          />
        </div>
      )}

      {v.has_preview && (
        <div className="mt-3 px-4">
          <Preview
            key={page}
            src={`/api/v1/cases/${caseId}/sources/${v.id}/preview?page=${page}`}
            alt={`Raster preview of ${v.role_label} ${v.number}, page ${page}`}
            highlight={finding?.page === page ? finding.box : undefined}
          />
          <div className="mt-2 flex items-center justify-between text-[12px] text-muted">
            <span>Raster preview · active PDF content is never rendered</span>
            <span className="flex items-center gap-1">
              {(v.page_count ?? 1) > 1 && (
                <>
                  <button
                    className="rounded p-1 hover:bg-teal-50 disabled:opacity-40"
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="size-4" />
                  </button>
                  <span className="tabular">
                    {page}/{v.page_count}
                  </span>
                  <button
                    className="rounded p-1 hover:bg-teal-50 disabled:opacity-40"
                    disabled={page >= (v.page_count ?? 1)}
                    onClick={() => setPage(page + 1)}
                    aria-label="Next page"
                  >
                    <ChevronRight className="size-4" />
                  </button>
                </>
              )}
              <a
                href={`/api/v1/cases/${caseId}/sources/${v.id}/original`}
                className="ml-2 inline-flex items-center gap-1 font-semibold text-teal-700 hover:underline"
              >
                <Download className="size-3.5" aria-hidden /> Original
              </a>
            </span>
          </div>
        </div>
      )}

      {v.role === "written_message" && v.text && (
        <div className="px-4 pt-3">
          <figure className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
            <Quote className="size-4 text-amber-600" aria-hidden />
            <blockquote className="mt-1.5 text-[14px] leading-relaxed text-ink">
              {v.text}
            </blockquote>
            <figcaption className="mt-2 text-[12px] text-muted">
              Attributed to {v.attributed_to || "unknown sender"} · attribution is not proof of
              authorship
            </figcaption>
          </figure>
          <p className="mt-2 text-[12px] text-muted">
            {v.coverage === "needs_review"
              ? "Gemini reads this message and prepares the task; a person records its disposition before the review can complete."
              : v.coverage === "reviewed"
                ? "A reviewer recorded a disposition covering this exact message version."
                : humanize(v.coverage)}
          </p>
        </div>
      )}

      {v.role === "status_update" && v.structured && (
        <div className="px-4 pt-3">
          <dl className="grid grid-cols-2 gap-2 rounded-xl border border-line bg-[#fafbfa] p-3 text-[13px]">
            {Object.entries(v.structured).map(([k, val]) => (
              <div key={k}>
                <dt className="text-[11.5px] text-subtle">{humanize(k)}</dt>
                <dd className="font-semibold text-ink">{val}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-[12px] text-muted">
            Structured reply field. Dispatch is progress on a request, never receipt evidence.
          </p>
        </div>
      )}

      {facts.length > 0 && (
        <div className="px-4 pt-4">
          <SectionLabel>Validated facts · read from the document text</SectionLabel>
          <dl className="mt-2 divide-y divide-line-soft rounded-xl border border-line">
            {facts.map((f) => (
              <div
                key={f.field}
                className={cx(
                  "flex items-start justify-between gap-3 px-3 py-2 text-[13px]",
                  KEY_FACTS.has(f.field) && "bg-teal-50/40",
                )}
              >
                <dt className="text-muted">{FACT_LABEL[f.field] ?? humanize(f.field)}</dt>
                <dd className="flex min-w-0 items-center gap-1.5 text-right font-semibold text-ink">
                  <span className="truncate">{f.value}</span>
                  <Tip
                    content={
                      <span>
                        Exact line on page {f.page}: <span className="font-mono">“{f.quote}”</span>
                      </span>
                    }
                  >
                    <span
                      tabIndex={0}
                      aria-label={f.verified ? "Verified against the original" : "Not verified"}
                    >
                      <CheckCircle2
                        className={cx(
                          "size-3.5 shrink-0",
                          f.verified ? "text-teal-600" : "text-red-600",
                        )}
                      />
                    </span>
                  </Tip>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <div className="space-y-1.5 px-4 pb-4 pt-4 text-[12px] text-muted">
        {v.sha256 && (
          <p className="flex items-center gap-1.5">
            <Hash className="size-3.5 shrink-0" aria-hidden /> SHA-256{" "}
            <Mono className="truncate">{v.sha256.slice(0, 24)}…</Mono>
          </p>
        )}
        <p>
          {v.size_bytes ? `${bytes(v.size_bytes)} · ` : ""}
          {v.page_count ? `${v.page_count} page${v.page_count > 1 ? "s" : ""} · ` : ""}
          {v.declared_issuer
            ? `declared source: ${v.declared_issuer}`
            : v.role === "written_message"
              ? "free text"
              : "structured"}
        </p>
      </div>
    </div>
  );
}

function Preview({ src, alt, highlight }: { src: string; alt: string; highlight?: number[] }) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-[#eef2f0]">
      {!loaded && !failed && <div className="skeleton aspect-[1/1.414] w-full rounded-none" />}
      {failed ? (
        <div className="grid aspect-[1/1.414] place-items-center text-[13px] text-muted">
          <span className="flex items-center gap-2">
            <ImageOff className="size-4" /> Preview unavailable
          </span>
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          className={cx("w-full", !loaded && "absolute inset-0 opacity-0")}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      )}
      {loaded && !failed && highlight && (
        <span
          aria-label="Highlighted finding region"
          className="pointer-events-none absolute border-2 border-amber-600 bg-amber-400/20"
          style={{
            left: `${highlight[0] / 10}%`,
            top: `${highlight[1] / 10}%`,
            width: `${(highlight[2] - highlight[0]) / 10}%`,
            height: `${(highlight[3] - highlight[1]) / 10}%`,
          }}
        />
      )}
    </div>
  );
}
