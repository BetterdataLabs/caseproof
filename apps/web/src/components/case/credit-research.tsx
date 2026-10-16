"use client";

import { useState } from "react";
import { Globe, Search } from "lucide-react";
import Link from "next/link";
import { dateTime } from "@/lib/format";
import type { CaseDetail, CreditResearch } from "@/lib/types";
import { useCaseCommand } from "@/lib/use-case";
import { Badge, Button, Card, Field, Input, Select } from "@/components/ui/primitives";

export function CreditResearchFields({ vendor = false }: { vendor?: boolean }) {
  const [enabled, setEnabled] = useState(false);
  return (
    <div className="rounded-xl border border-line bg-teal-50/30 p-4">
      <label className="flex cursor-pointer items-start gap-3 text-sm font-semibold text-ink">
        <input
          type="checkbox"
          name="credit_research"
          value="true"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="mt-1 accent-teal-700"
        />
        <span>
          Include company credit research <span className="font-normal text-muted">(optional)</span>
          <span className="mt-1 block text-xs font-normal leading-relaxed text-muted">
            Search public sources with Google and prepare a cited analysis of the company’s
            financial position and business risks.{" "}
            {vendor
              ? "The report is shared with the bank."
              : "Included in the bank’s final review report."}
          </span>
        </span>
      </label>
      {enabled && (
        <div className="mt-4 space-y-3">
          <Field
            label="Company to research"
            htmlFor="research-target"
            hint="The buyer owes the invoice. The seller is seeking financing. The company name comes from your invoice."
          >
            <Select id="research-target" name="research_target" defaultValue="buyer">
              <option value="buyer">Buyer — ability to pay the invoice</option>
              <option value="seller">Seller — business seeking financing</option>
            </Select>
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Country of registration" htmlFor="research-country">
              <Input
                id="research-country"
                name="company_country"
                placeholder="e.g. Singapore"
                required
                maxLength={80}
              />
            </Field>
            <Field
              label="Registration number (optional)"
              htmlFor="research-registration"
              hint="Helps distinguish companies with similar names."
            >
              <Input
                id="research-registration"
                name="registration_number"
                maxLength={80}
                placeholder="e.g. company UEN"
              />
            </Field>
          </div>
          <p className="text-xs leading-relaxed text-muted">
            Only the company name and identifiers above are used for public searches. The analysis
            may be inconclusive for private or fictional companies. It is not a credit rating.
            Google’s free search allowance may apply; model and search charges can apply.
          </p>
        </div>
      )}
    </div>
  );
}

const signals: Record<string, string> = {
  concern: "Concern identified",
  mixed: "Mixed evidence",
  no_adverse_found: "No concern in cited evidence",
  unknown: "Not enough evidence",
};
export const researchOutcomes: Record<string, string> = {
  attention_needed: "Bank review needed",
  insufficient_information: "Insufficient information",
  no_material_flags_identified: "No material flags identified",
};

export function ResearchStatusBadge({ report }: { report: Pick<CreditResearch, "status"> }) {
  const status = report.status ?? "pending";
  return (
    <Badge
      tone={
        status === "failed"
          ? "amber"
          : status === "complete"
            ? "teal"
            : status === "researching"
              ? "blue"
              : "neutral"
      }
    >
      {
        { pending: "Queued", researching: "Researching", complete: "Complete", failed: "Failed" }[
          status
        ]
      }
    </Badge>
  );
}

export function CreditResearchPanel({
  detail,
  expanded = false,
}: {
  detail: CaseDetail;
  expanded?: boolean;
}) {
  const report = detail.case.credit_research;
  const retry = useCaseCommand<void>(
    detail.case.id,
    () => `/v1/cases/${detail.case.id}/credit-research/retry`,
    () => ({ expected_revision: detail.case.revision }),
    { success: "Company research queued" },
  );
  if (!report?.enabled) return null;
  const searches = report.searches ?? [];
  const sources = new Map(
    searches.flatMap((search) => search.sources).map((source) => [source.id, source]),
  );
  function sourceLinks(ids: string[]) {
    return ids.map((id, index) => {
      const source = sources.get(id);
      return (
        <span key={id}>
          {index > 0 && " · "}
          {source ? (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="break-words font-semibold text-teal-700 underline"
            >
              {source.title}
            </a>
          ) : (
            id
          )}
        </span>
      );
    });
  }
  const pending = report.status === "pending" || report.status === "researching";
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-line px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Globe className="size-4 text-teal-700" />
            Company credit research
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <ResearchStatusBadge report={report} />
            {report.status === "complete" && report.assessment && (
              <Badge tone={report.assessment === "attention_needed" ? "amber" : "neutral"}>
                {researchOutcomes[report.assessment]}
              </Badge>
            )}
          </div>
        </div>
        <p className="mt-1 text-xs text-muted">
          {report.subject?.name ?? "Company name will be read from the invoice"} ·{" "}
          {report.target === "seller" ? "Seller seeking financing" : "Buyer owing the invoice"}
          {report.subject?.country || report.country
            ? ` · ${report.subject?.country || report.country}`
            : ""}
          {report.subject?.registration_number ? ` · ${report.subject.registration_number}` : ""}
        </p>
        {!expanded && (
          <Link
            href={`/research?case=${detail.case.id}`}
            className="mt-2 inline-block text-xs font-semibold text-teal-700 hover:underline"
          >
            View in Research
          </Link>
        )}
      </div>
      <div className="space-y-4 px-5 py-4">
        <p className="text-sm leading-relaxed text-ink">
          {pending
            ? "Checking company identity, financial evidence and business risks. Results are saved as each step completes."
            : report.summary || report.error}
        </p>
        {pending && <p className="text-xs text-muted">{searches.length} of 3 searches saved.</p>}
        {report.status === "complete" && (
          <p className="text-xs text-muted">
            {report.coverage} of 6 areas have usable evidence · Entity {report.identity} ·{" "}
            {report.completed_at ? new Date(report.completed_at).toLocaleDateString() : ""}.
            Evidence coverage measures available information, not creditworthiness.
          </p>
        )}
        {report.status === "failed" &&
          detail.permissions.decide &&
          detail.case.lifecycle !== "archived" && (
            <Button
              variant="secondary"
              loading={retry.isPending}
              onClick={() => retry.mutate()}
              icon={<Search className="size-4" />}
            >
              Retry research
            </Button>
          )}
        {retry.error && (
          <p role="alert" className="text-sm text-red-700">
            {retry.error.message}
          </p>
        )}
        {report.dimensions && (
          <div className="space-y-2">
            {report.dimensions.map((d) => (
              <details
                key={d.key}
                open={expanded || undefined}
                className="rounded-lg border border-line p-3"
              >
                <summary className="cursor-pointer text-sm font-semibold text-ink">
                  {d.label}
                  <span className="mt-0.5 block text-xs font-normal text-muted">
                    {signals[d.signal]}
                  </span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted">{d.analysis}</p>
                {d.citations.map((c) => (
                  <blockquote
                    key={c.evidence_id}
                    className="mt-2 border-l-2 border-teal-300 pl-3 text-xs leading-relaxed text-muted"
                  >
                    Grounded research passage: “{c.quote}” {sourceLinks(c.sources)}
                  </blockquote>
                ))}
              </details>
            ))}
          </div>
        )}
        {!!report.information_to_obtain?.length && (
          <details open={expanded || undefined} className="text-sm">
            <summary className="cursor-pointer font-semibold text-teal-700">
              Information the bank still needs
            </summary>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-xs leading-relaxed text-muted">
              {report.information_to_obtain.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        )}
        {searches.length > 0 && (
          <details open={expanded || undefined} className="text-sm">
            <summary className="cursor-pointer font-semibold text-teal-700">
              Sources and search record
            </summary>
            <div className="mt-3 space-y-5">
              {searches.map((s) => (
                <div key={s.angle}>
                  <p className="mb-2 text-xs font-semibold text-ink">
                    Search {s.angle} ·{" "}
                    {(
                      {
                        1: "Identity and adverse information",
                        2: "Financial reports",
                        3: "Business and market conditions",
                      } as Record<number, string>
                    )[s.angle] ?? "Public sources"}
                  </p>
                  <p className="mb-2 text-xs text-muted">Retrieved {dateTime(s.retrieved_at)}</p>
                  {s.sources.length === 0 && (
                    <p className="text-xs text-muted">No cited public sources returned.</p>
                  )}
                  <ul className="space-y-2">
                    {s.sources.map((source) => (
                      <li key={source.id} className="text-xs">
                        <a
                          className="break-words text-teal-700 underline"
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {source.id} · {source.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 break-words text-xs text-muted">
                    Queries: {s.queries.join(" · ") || "Not returned by Google"}
                  </p>
                  {!!s.passages?.length && (
                    <details
                      open={expanded || undefined}
                      className="mt-3 rounded-lg border border-line p-3"
                    >
                      <summary className="cursor-pointer text-xs font-semibold text-ink">
                        Supporting passages ({s.passages.length})
                      </summary>
                      <p className="mt-2 text-xs leading-relaxed text-muted">
                        Saved Google-grounded passages used by the agent. Open the cited sources to
                        check the original publications.
                      </p>
                      <div className="mt-3 space-y-3">
                        {s.passages.map((passage) => (
                          <blockquote
                            key={passage.id}
                            className="border-l-2 border-teal-300 pl-3 text-xs leading-relaxed text-muted"
                          >
                            <p className="whitespace-pre-wrap">{passage.text}</p>
                            <div className="mt-1">{sourceLinks(passage.sources)}</div>
                          </blockquote>
                        ))}
                      </div>
                    </details>
                  )}
                  {s.search_suggestions && (
                    <iframe
                      title={`Google Search suggestions ${s.angle}`}
                      srcDoc={s.search_suggestions}
                      sandbox="allow-popups allow-popups-to-escape-sandbox"
                      referrerPolicy="no-referrer"
                      className="mt-2 h-32 w-full border-0"
                    />
                  )}
                </div>
              ))}
            </div>
          </details>
        )}
        <p className="border-t border-line pt-3 text-xs leading-relaxed text-muted">
          {report.limitation} {report.method ? `Method: ${report.method}.` : ""}
        </p>
      </div>
    </Card>
  );
}
