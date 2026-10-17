"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, FileJson, FileText, History, Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";
import { getJson } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useCaseCommand } from "@/lib/use-case";
import type { AuditEvent, CaseDetail } from "@/lib/types";
import {
  Badge,
  Button,
  Callout,
  EmptyState,
  ErrorState,
  Input,
  Mono,
  Skeleton,
  cx,
} from "@/components/ui/primitives";

export function SummaryPanel({ detail }: { detail: CaseDetail }) {
  const retry = useCaseCommand<void>(
    detail.case.id,
    () => `/v1/cases/${detail.case.id}/exports/retry`,
    () => ({}),
    { success: "Summary generation retried" },
  );
  if (!detail.exports.length)
    return (
      <EmptyState icon={<FileText className="size-5" />} title="No review summary yet">
        Completion freezes a revision-specific snapshot and renders a PDF and JSON record from it.
        Open questions: {detail.questions.filter((q) => q.state !== "resolved").length}.
      </EmptyState>
    );
  return (
    <div className="space-y-3 py-4">
      <Callout tone="neutral">
        Each summary is immutable and tied to a case revision. A later change marks it superseded; a
        downloaded file cannot be recalled, so its export ID makes its age explicit.
      </Callout>
      <ul className="space-y-2">
        {detail.exports.map((e) => (
          <li
            key={e.id}
            className={cx(
              "rounded-xl border p-4",
              e.is_current && e.state === "ready"
                ? "border-teal-200 bg-teal-50/40"
                : "border-line bg-paper",
            )}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[13px] font-semibold text-ink">{e.export_ref}</span>
              <Badge
                tone={
                  e.state === "ready"
                    ? "teal"
                    : e.state === "preparing"
                      ? "blue"
                      : e.state === "failed"
                        ? "red"
                        : "neutral"
                }
                icon={
                  e.state === "preparing" ? <Loader2 className="size-3 animate-spin" /> : undefined
                }
              >
                {e.state === "ready" && e.is_current ? "Current" : e.state}
              </Badge>
              <span className="text-[12.5px] text-muted">
                Revision {e.case_revision} · {e.policy_label} ·{" "}
                {dateTime(e.ready_at ?? e.created_at)}
              </span>
              <span className="ml-auto flex gap-2">
                {["ready", "superseded"].includes(e.state) && e.pdf_sha256 && (
                  <>
                    <a
                      href={`/api/v1/exports/${e.id}/pdf`}
                      className="inline-flex h-8 items-center gap-1.5 rounded-[10px] border border-line bg-white px-3 text-[13px] font-semibold text-ink hover:border-teal-300 hover:bg-teal-50"
                    >
                      <Download className="size-3.5" aria-hidden /> PDF
                    </a>
                    <a
                      href={`/api/v1/exports/${e.id}/json`}
                      className="inline-flex h-8 items-center gap-1.5 rounded-[10px] border border-line bg-white px-3 text-[13px] font-semibold text-ink hover:border-teal-300 hover:bg-teal-50"
                    >
                      <FileJson className="size-3.5" aria-hidden /> JSON
                    </a>
                  </>
                )}
                {e.is_current && ["failed"].includes(e.state) && (
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<RotateCcw className="size-3.5" />}
                    loading={retry.isPending}
                    onClick={() => retry.mutate()}
                  >
                    Retry
                  </Button>
                )}
              </span>
            </div>
            {e.superseded_reason && (
              <p className="mt-2 text-[12.5px] text-muted">Superseded: {e.superseded_reason}</p>
            )}
            {e.pdf_sha256 && (
              <p className="mt-1.5 text-[11.5px] text-subtle">
                PDF SHA-256 <Mono>{e.pdf_sha256.slice(0, 32)}…</Mono>
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function HistoryPanel({ detail }: { detail: CaseDetail }) {
  const [filter, setFilter] = useState("");
  const q = useQuery({
    queryKey: ["history", detail.case.id, detail.case.revision],
    queryFn: ({ signal }) =>
      getJson<{ events: AuditEvent[] }>(`/v1/cases/${detail.case.id}/history`, signal),
  });
  if (q.error)
    return (
      <div className="py-4">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  if (!q.data)
    return (
      <div className="space-y-2 py-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    );
  const events = q.data.events.filter(
    (e) =>
      !filter || `${e.type} ${e.summary} ${e.actor}`.toLowerCase().includes(filter.toLowerCase()),
  );
  return (
    <div className="py-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Input
          aria-label="Filter history"
          placeholder="Filter events"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-xs"
        />
        <span className="flex items-center gap-1.5 text-[12.5px] text-muted">
          <History className="size-4" aria-hidden /> Append-only record · {q.data.events.length}{" "}
          events
        </span>
      </div>
      <div className="scroll-thin max-h-[560px] overflow-auto rounded-xl border border-line">
        <table className="w-full min-w-[720px] text-left text-[12.5px]">
          <thead className="sticky top-0 bg-[#fafbfa]">
            <tr className="border-b border-line text-[11px] font-bold uppercase tracking-[0.06em] text-subtle">
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Rev</th>
              <th className="px-3 py-2">Event</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">Summary</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-b border-line-soft align-top last:border-0">
                <td className="whitespace-nowrap px-3 py-2 text-muted tabular">
                  {dateTime(e.created_at)}
                </td>
                <td className="px-3 py-2 text-muted tabular">{e.revision ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-[11.5px] text-ink">
                  {e.type}
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <Badge
                    tone={
                      e.actor_type === "person"
                        ? "amber"
                        : e.actor_type === "agent"
                          ? "navy"
                          : e.actor_type === "simulation"
                            ? "violet"
                            : "neutral"
                    }
                  >
                    {e.actor}
                  </Badge>
                </td>
                <td className="px-3 py-2 text-ink">
                  {e.summary}
                  {e.reason && <span className="block text-muted">{e.reason}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
