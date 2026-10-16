"use client";

import {
  BadgeCheck,
  Bell,
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Cog,
  FileInput,
  FileSearch,
  FileWarning,
  Hand,
  ListChecks,
  Loader2,
  MailCheck,
  PauseCircle,
  RotateCcw,
  Search,
  UserCheck,
} from "lucide-react";
import React, { useId, useState } from "react";
import { dateTime, humanize, timeOnly, usd } from "@/lib/format";
import type { AgentRun, AuditEvent, CaseDetail } from "@/lib/types";
import { Badge, EmptyState, cx } from "@/components/ui/primitives";
import { TOOL_LABEL } from "@/components/ui/status";

const OUTCOME: Record<
  string,
  { label: string; tone: "teal" | "blue" | "amber" | "violet" | "red" | "neutral" }
> = {
  working: { label: "In progress", tone: "blue" },
  done: { label: "Done", tone: "neutral" },
  saved: { label: "Progress saved", tone: "neutral" },
  needs_review: { label: "Follow-up needed", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
  waiting: { label: "Waiting for the business", tone: "violet" },
  human_task: { label: "Reviewer decision needed", tone: "amber" },
  completed: { label: "Review completed", tone: "teal" },
  paused: { label: "Paused", tone: "red" },
  stale: { label: "Superseded by new input", tone: "neutral" },
  shadow: { label: "Proposal saved", tone: "neutral" },
  no_action: { label: "No further action", tone: "neutral" },
};

const STAGE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  document: FileSearch,
  checks: ListChecks,
  appearance: FileSearch,
  research: Search,
  actions: MailCheck,
};
const EVENT_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  CaseCreated: FileInput,
  ReplyReceived: MailCheck,
  HumanDecisionRecorded: UserCheck,
  ReminderSent: Bell,
  ReviewCompleted: BadgeCheck,
  ReviewReopened: RotateCcw,
  AutomationPaused: PauseCircle,
  AutomationResumed: Cog,
  EvidenceRejected: FileWarning,
  EvidenceWithdrawn: FileWarning,
  DemoClockAdvanced: Clock3,
  HumanTaskSuperseded: CircleAlert,
  AutomationModeChanged: Cog,
  DuplicateSuppressed: CircleAlert,
  LeaseExpired: CircleAlert,
};
const FEED_EVENTS = new Set(Object.keys(EVENT_ICON));

interface Review {
  id: string;
  title: string;
  runs: AgentRun[];
}
type FeedItem =
  { kind: "review"; at: string; review: Review } | { kind: "event"; at: string; event: AuditEvent };

function activityOf(run: AgentRun) {
  // Allow a cached response from the preceding API version to render safely.
  return (
    run.activity ?? {
      review_id: run.id,
      review_title: "Document review",
      stage: "actions",
      title: "Review documents",
      summary: run.summary || "Review progress recorded.",
      state: !run.ended_at ? "working" : run.outcome === "waiting" ? "saved" : run.outcome,
      continues: false,
      cost_known: true,
    }
  );
}

function reviewsFor(runs: AgentRun[]): Review[] {
  const groups = new Map<string, Review>();
  for (const run of [...runs].sort((a, b) => a.started_at.localeCompare(b.started_at))) {
    const activity = activityOf(run);
    let review = groups.get(activity.review_id);
    if (!review) {
      review = { id: activity.review_id, title: activity.review_title, runs: [] };
      groups.set(review.id, review);
    }
    review.runs.push(run);
  }
  return [...groups.values()];
}

export function ActivityFeed({ detail }: { detail: CaseDetail }) {
  const reviews = reviewsFor(detail.runs);
  const newest = reviews.at(-1)?.id;
  const items: FeedItem[] = [
    ...reviews.map((review) => ({
      kind: "review" as const,
      at: review.runs[0].started_at,
      review,
    })),
    ...detail.timeline
      .filter((e) => FEED_EVENTS.has(e.type))
      .map((event) => ({ kind: "event" as const, at: event.created_at, event })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  const queued = detail.case.execution === "queued" && !detail.runs.some((r) => !r.ended_at);
  if (!items.length && !queued)
    return <EmptyState icon={<Bot className="size-5" />} title="No activity yet" />;
  return (
    <ol className="space-y-4 py-4" aria-label="Review activity">
      {queued && (
        <li
          role="status"
          className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-[13px] text-blue-700"
        >
          <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
          {reviews.length
            ? "Continuing the review. Completed work is saved."
            : "Document review is queued."}
        </li>
      )}
      {items.map((item) =>
        item.kind === "review" ? (
          <ReviewCard
            key={item.review.id}
            review={item.review}
            latest={item.review.id === newest}
            execution={detail.case.execution}
          />
        ) : (
          <EventRow key={item.event.id} event={item.event} />
        ),
      )}
    </ol>
  );
}

function EventRow({ event }: { event: AuditEvent }) {
  const Icon = EVENT_ICON[event.type] ?? Cog;
  return (
    <li className="flex gap-3 px-1">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-[#eef2f0] text-muted">
        <Icon className="size-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 pb-1">
        <p className="text-[13px] text-ink">{event.summary}</p>
        {event.reason && <p className="mt-0.5 text-[12.5px] text-muted">{event.reason}</p>}
        <p className="mt-0.5 text-[11.5px] text-subtle">
          {event.actor} · {dateTime(event.created_at)}
        </p>
      </div>
    </li>
  );
}

function ReviewCard({
  review,
  latest,
  execution,
}: {
  review: Review;
  latest: boolean;
  execution: string;
}) {
  const [open, setOpen] = useState(latest);
  const bodyId = useId();
  const first = review.runs[0];
  const last = review.runs[review.runs.length - 1];
  const lastActivity = activityOf(last);
  const live =
    !last.ended_at ||
    (latest && lastActivity.continues && ["queued", "running"].includes(execution));
  const state = live
    ? "working"
    : lastActivity.continues && lastActivity.state === "done"
      ? "saved"
      : lastActivity.state;
  const outcome = OUTCOME[state] ?? OUTCOME.saved;
  const failures = review.runs.filter((run) => activityOf(run).state === "failed");
  const warnings = [
    ...new Map(failures.map((run) => [activityOf(run).title, activityOf(run)])).values(),
  ];
  return (
    <li
      className={cx(
        "overflow-hidden rounded-xl border bg-paper",
        live ? "border-blue-200" : "border-line",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex w-full items-start gap-3 px-4 py-4 text-left transition-colors hover:bg-[#fafbfa] focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-teal-700 sm:px-5"
      >
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-800">
          {live ? (
            <Loader2 className="size-[18px] animate-spin" aria-hidden />
          ) : (
            <ListChecks className="size-[18px]" aria-hidden />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <span className="text-[14px] font-semibold text-ink">{review.title}</span>
            <Badge tone={outcome.tone}>{outcome.label}</Badge>
          </span>
          <span className="mt-1 block text-[12px] text-subtle">
            {dateTime(first.started_at)} · {review.runs.length} step
            {review.runs.length === 1 ? "" : "s"}
            {!live && last.ended_at && ` · ${duration(first.started_at, last.ended_at)}`}
          </span>
        </span>
        <ChevronDown
          className={cx(
            "mt-1 size-4 shrink-0 text-subtle transition-transform",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {warnings.map((warning) => (
        <div
          key={warning.title}
          className="mx-4 mb-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 sm:mx-5"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-red-600" aria-hidden />
          <div className="min-w-0 text-[12.5px]">
            <p className="font-semibold text-red-700">{warning.title}</p>
            <p className="mt-0.5 leading-relaxed text-red-700">{warning.summary}</p>
          </div>
        </div>
      ))}
      <div id={bodyId} hidden={!open} className="border-t border-line-soft">
        <ol className="px-4 pb-1 pt-5 sm:px-5" aria-label={`${review.title} steps`}>
          {review.runs.map((run) => (
            <StageRow key={run.id} run={run} />
          ))}
        </ol>
        <TechnicalDetails review={review} />
      </div>
    </li>
  );
}

function StageRow({ run }: { run: AgentRun }) {
  const activity = activityOf(run);
  const outcome = OUTCOME[activity.state] ?? OUTCOME.saved;
  const Icon =
    activity.state === "working"
      ? Loader2
      : activity.state === "failed"
        ? CircleAlert
        : activity.state === "human_task"
          ? Hand
          : activity.state === "done"
            ? Check
            : (STAGE_ICON[activity.stage] ?? Cog);
  const actions = run.actions.filter(
    (a) => a.tool !== "wait_for_event" || a.result_code !== "WAITING",
  );
  return (
    <li className="group relative flex gap-3 pb-5 last:pb-3">
      <span
        className="absolute bottom-0 left-[13px] top-8 w-px bg-line-soft group-last:hidden"
        aria-hidden
      />
      <span
        className={cx(
          "relative grid size-7 shrink-0 place-items-center rounded-full border bg-white",
          activity.state === "failed"
            ? "border-red-200 text-red-600"
            : activity.state === "needs_review"
              ? "border-amber-200 text-amber-700"
              : activity.state === "working"
                ? "border-blue-200 text-blue-700"
                : "border-line text-teal-700",
        )}
      >
        <Icon
          className={cx("size-3.5", activity.state === "working" && "animate-spin")}
          aria-hidden
        />
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
          <p className="text-[13px] font-semibold text-ink">{activity.title}</p>
          <Badge tone={outcome.tone}>{outcome.label}</Badge>
          <time
            dateTime={run.started_at}
            className="ml-auto hidden text-[11.5px] tabular-nums text-subtle sm:block"
          >
            {timeOnly(run.started_at)}
          </time>
        </div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{activity.summary}</p>
        {actions.length > 0 && (
          <ul className="mt-2 space-y-2 border-l-2 border-line-soft pl-3">
            {actions.map((action) => (
              <li key={action.seq} className="text-[12px] leading-relaxed">
                <p className="font-medium text-ink">
                  {TOOL_LABEL[action.tool] ?? humanize(action.tool)}
                  {action.shadow && <span className="ml-2 text-subtle">Proposed only</span>}
                  {badAction(action.result_code) && (
                    <span className="ml-2 text-amber-700">Needs attention</span>
                  )}
                </p>
                {(action.reason || action.result_summary) && (
                  <p className="text-muted">{action.reason || action.result_summary}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

function TechnicalDetails({ review }: { review: Review }) {
  const calls = review.runs.reduce((n, r) => n + r.model_calls, 0);
  const retries = review.runs.reduce((n, r) => n + r.retries, 0);
  const cost = review.runs.reduce((n, r) => n + Number(r.cost_usd), 0);
  const unknownCost = review.runs.some((run) => !activityOf(run).cost_known);
  return (
    <details className="border-t border-line-soft bg-[#fafbfa] px-4 py-3 text-[12px] sm:px-5">
      <summary className="w-fit cursor-pointer font-medium text-muted focus-visible:outline-teal-700">
        Technical details
      </summary>
      <p className="mt-3 text-muted">
        {calls} model call{calls === 1 ? "" : "s"}
        {retries > 0 && ` · ${retries} retr${retries === 1 ? "y" : "ies"}`}
        {` · ${usd(String(cost))} recorded`}
        {unknownCost && " · Some usage unavailable"}
      </p>
      <ul className="mt-2 divide-y divide-line-soft">
        {review.runs.map((run) => (
          <li key={run.id} className="py-2">
            <details>
              <summary className="cursor-pointer leading-relaxed text-ink">
                {activityOf(run).title} · {timeOnly(run.started_at)}
              </summary>
              <div className="space-y-2 pl-4 pt-2 text-muted">
                <p>
                  {run.controller === "adk-gemini" ? `${run.model} via ADK` : "Fixed-rule workflow"}{" "}
                  · {run.model_calls} model calls · {run.tool_calls} tool actions
                  {run.ended_at && ` · ${duration(run.started_at, run.ended_at)}`}
                  {run.retries > 0 && ` · ${run.retries} retr${run.retries === 1 ? "y" : "ies"}`}
                </p>
                <p>
                  Trigger: {humanize(run.trigger.replace(/([a-z])([A-Z])/g, "$1_$2"))} · Revision{" "}
                  {run.input_revision} → {run.final_revision ?? "in progress"}
                </p>
                {run.stop_reason && <p>Stop reason: {humanize(run.stop_reason)}</p>}
                {run.summary && <p>{run.summary}</p>}
                {run.actions.map((action) => (
                  <div
                    key={action.seq}
                    className="space-y-1 rounded-lg border border-line-soft bg-white p-2"
                  >
                    <p className="font-mono text-[11px]">
                      {action.tool} · {action.result_code} · {action.duration_ms} ms
                    </p>
                    <p>{action.result_summary}</p>
                    {Object.keys(action.args).length > 0 && (
                      <p className="break-all font-mono text-[11px] text-subtle">
                        {formatArgs(action.args)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </details>
          </li>
        ))}
      </ul>
    </details>
  );
}

function duration(start: string, end: string): string {
  const seconds = Math.max(0, Math.round((Date.parse(end) - Date.parse(start)) / 1000));
  return seconds >= 60 ? `${Math.floor(seconds / 60)}m ${seconds % 60}s` : `${seconds}s`;
}

function badAction(code: string) {
  return (
    /STALE|LIMIT|INVALID|NOT_|ALREADY|DENIED|ERROR|STOP|PAUSED/.test(code) &&
    code !== "ALREADY_ISSUED"
  );
}

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0))
    .map(
      ([k, v]) =>
        `${k}=${Array.isArray(v) ? v.join(",") : typeof v === "object" ? JSON.stringify(v) : String(v)}`,
    )
    .join("  ");
}
