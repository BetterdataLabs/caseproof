"use client";

import { Bell, Bot, Building2, Clock3, FileText, Inbox, UserRound } from "lucide-react";
import { dateTime, relativeTime } from "@/lib/format";
import type { CaseDetail, InfoRequest, Reply } from "@/lib/types";
import { Badge, EmptyState, SectionLabel } from "@/components/ui/primitives";

const ITEM_STATUS: Record<string, { label: string; tone: "violet" | "blue" | "teal" | "neutral" }> =
  {
    outstanding: { label: "Outstanding", tone: "violet" },
    progress: { label: "Progress reported", tone: "blue" },
    answered: { label: "Resolved", tone: "teal" },
    closed: { label: "Superseded by a later round", tone: "neutral" },
  };

export function Exchange({
  detail,
  onSource,
}: {
  detail: CaseDetail;
  onSource: (label: string) => void;
}) {
  const sent = detail.requests.filter((r) => r.state !== "draft");
  type Entry =
    | { at: string; kind: "request"; r: InfoRequest }
    | { at: string; kind: "reply"; r: Reply }
    | { at: string; kind: "reminder"; r: InfoRequest };
  const entries: Entry[] = [
    ...sent.map((r) => ({ at: r.issued_at ?? r.created_at, kind: "request" as const, r })),
    ...sent
      .filter((r) => r.reminder_sent_at)
      .map((r) => ({ at: r.reminder_sent_at!, kind: "reminder" as const, r })),
    ...detail.replies.map((r) => ({ at: r.created_at, kind: "reply" as const, r })),
  ].sort((a, b) => (a.at < b.at ? -1 : 1));

  if (!entries.length)
    return (
      <EmptyState icon={<Inbox className="size-5" />} title="No requests yet">
        When evidence is missing, the agent records one consolidated request here and tracks each
        item separately. Use Add documents or reply to respond.
      </EmptyState>
    );

  return (
    <div className="space-y-4 py-4">
      <p className="flex items-center gap-2 text-[12.5px] text-muted">
        <Inbox className="size-4 text-subtle" aria-hidden /> Requests and replies in this workspace
        · no external email
      </p>
      <ol className="space-y-4">
        {entries.map((e, i) =>
          e.kind === "request" ? (
            <RequestCard key={`q${e.r.id}`} r={e.r} />
          ) : e.kind === "reminder" ? (
            <li
              key={`m${e.r.id}${i}`}
              className="flex items-center gap-2 pl-2 text-[13px] text-muted"
            >
              <Bell className="size-4 text-amber-600" aria-hidden /> Policy timer sent the single
              permitted reminder for round {e.r.round} · {dateTime(e.at)}
            </li>
          ) : (
            <ReplyCard key={`r${e.r.id}`} r={e.r} onSource={onSource} />
          ),
        )}
      </ol>
    </div>
  );
}

function RequestCard({ r }: { r: InfoRequest }) {
  const proposed = r.state === "proposed";
  return (
    <li className="mr-0 overflow-hidden rounded-xl border border-line bg-paper sm:mr-10">
      <div className="flex flex-wrap items-center gap-2 border-b border-line-soft bg-[#fafbfa] px-4 py-2.5">
        <span className="grid size-6 place-items-center rounded-md bg-navy-900 text-white">
          {r.created_by === "agent" ? (
            <Bot className="size-3.5" aria-hidden />
          ) : (
            <UserRound className="size-3.5" aria-hidden />
          )}
        </span>
        <span className="text-[13px] font-semibold text-ink">
          {proposed ? "Proposed request (shadow mode, not sent)" : `Request round ${r.round}`}
        </span>
        <Badge tone={r.state === "issued" ? "violet" : r.state === "answered" ? "teal" : "neutral"}>
          {r.state === "issued" ? "Awaiting reply" : r.state}
        </Badge>
        <span className="ml-auto text-[11.5px] text-subtle">
          {dateTime(r.issued_at ?? r.created_at)}
        </span>
      </div>
      <div className="px-4 py-3">
        <p className="text-[12px] text-muted">
          To {r.recipient} · <span className="font-semibold text-ink">{r.subject}</span>
        </p>
        <ul className="mt-3 space-y-2.5">
          {r.items.map((item, idx) => {
            const s = ITEM_STATUS[item.status] ?? ITEM_STATUS.outstanding;
            return (
              <li key={item.id} className="rounded-lg border border-line-soft bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[12px] font-semibold text-muted">
                    Item {idx + 1} · {item.question_label}
                  </span>
                  <Badge tone={s.tone}>{s.label}</Badge>
                </div>
                <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink">{item.text}</p>
                {item.progress_note && (
                  <p className="mt-1.5 rounded-md bg-blue-50 px-2 py-1 text-[12.5px] text-blue-700">
                    Progress: {item.progress_note} — not receipt evidence
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        {r.state === "issued" && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
            <span className="flex items-center gap-1">
              <Clock3 className="size-3.5" aria-hidden />
              {r.reminder_sent_at
                ? `Reminder sent ${relativeTime(r.reminder_sent_at)}`
                : `Reminder ${relativeTime(r.reminder_due_at)}`}
            </span>
            {r.stop_due_at && (
              <span>
                Reviewer stop point {r.stop_reached_at ? "reached" : relativeTime(r.stop_due_at)}
              </span>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

function ReplyCard({ r, onSource }: { r: Reply; onSource: (label: string) => void }) {
  return (
    <li className="ml-0 overflow-hidden rounded-xl border border-[#ddd3f5] bg-violet-100/30 sm:ml-10">
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
        <span className="grid size-6 place-items-center rounded-md bg-violet-700 text-white">
          <Building2 className="size-3.5" aria-hidden />
        </span>
        <span className="text-[13px] font-semibold text-ink">{r.sender}</span>
        <Badge tone="violet">{r.kind.replace(/_/g, " ")}</Badge>
        <span className="ml-auto text-[11.5px] text-subtle">{dateTime(r.created_at)}</span>
      </div>
      <div className="px-4 pb-3">
        <p className="text-[13.5px] text-ink">{r.summary}</p>
        {r.versions.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <SectionLabel>Sources</SectionLabel>
            {r.versions.map((label) => (
              <button
                key={label}
                onClick={() => onSource(label)}
                className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-1.5 py-0.5 text-[12px] font-semibold text-teal-700 hover:bg-teal-50"
              >
                <FileText className="size-3" aria-hidden /> {label}
              </button>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}
