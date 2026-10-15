"use client";

import {
  BadgeCheck,
  Bell,
  Bot,
  ChevronDown,
  CircleAlert,
  Clock3,
  Cog,
  FileInput,
  FileSearch,
  FileWarning,
  GitCompareArrows,
  Hand,
  ListChecks,
  Loader2,
  Mail,
  MailCheck,
  PauseCircle,
  RotateCcw,
  Send,
  UserCheck,
} from "lucide-react";
import React, { useState } from "react";
import { dateTime, humanize, timeOnly, usd } from "@/lib/format";
import type { AgentRun, AuditEvent, CaseDetail } from "@/lib/types";
import { Badge, EmptyState, cx } from "@/components/ui/primitives";
import { TOOL_LABEL } from "@/components/ui/status";

const TOOL_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  read_case: FileSearch,
  inspect_source: FileSearch,
  compare_statements: GitCompareArrows,
  run_checks: ListChecks,
  prepare_request: Mail,
  issue_request: Send,
  wait_for_event: Clock3,
  open_human_task: Hand,
  try_complete: BadgeCheck,
};

const OUTCOME: Record<
  string,
  { label: string; tone: "teal" | "blue" | "amber" | "violet" | "red" | "neutral" }
> = {
  running: { label: "Working", tone: "blue" },
  waiting: { label: "Waiting for the business", tone: "violet" },
  human_task: { label: "Handed to a reviewer", tone: "amber" },
  completed: { label: "Review completed", tone: "teal" },
  paused: { label: "Paused", tone: "red" },
  stale: { label: "Superseded by newer input", tone: "neutral" },
  shadow: { label: "Shadow proposal", tone: "neutral" },
  no_action: { label: "No action needed", tone: "neutral" },
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

type FeedItem =
  { kind: "run"; at: string; run: AgentRun } | { kind: "event"; at: string; event: AuditEvent };

export function ActivityFeed({ detail }: { detail: CaseDetail }) {
  const items: FeedItem[] = [
    ...detail.runs.map((run) => ({ kind: "run" as const, at: run.started_at, run })),
    ...detail.timeline
      .filter((e) => FEED_EVENTS.has(e.type))
      .map((event) => ({ kind: "event" as const, at: event.created_at, event })),
  ].sort((a, b) => (a.at < b.at ? 1 : -1));
  const running = detail.case.execution === "queued" && !detail.runs.some((r) => !r.ended_at);

  if (!items.length)
    return <EmptyState icon={<Bot className="size-5" />} title="No activity yet" />;
  return (
    <ol className="relative space-y-3 py-4" aria-live="polite">
      {running && (
        <li className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-[13.5px] text-blue-700">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Agent queued — a worker will pick
          this case up in a moment.
        </li>
      )}
      {items.map((item, i) =>
        item.kind === "run" ? (
          <RunCard key={item.run.id} run={item.run} defaultOpen={i < 2} />
        ) : (
          <EventRow key={item.event.id} event={item.event} />
        ),
      )}
    </ol>
  );
}

function EventRow({ event }: { event: AuditEvent }) {
  const Icon = EVENT_ICON[event.type] ?? Cog;
  const person = event.actor_type === "person";
  const customer = event.actor_type === "simulation";
  return (
    <li className="flex gap-3 px-1">
      <span
        className={cx(
          "mt-0.5 grid size-7 shrink-0 place-items-center rounded-full",
          person
            ? "bg-amber-100 text-amber-700"
            : customer
              ? "bg-violet-100 text-violet-700"
              : event.type === "ReviewCompleted"
                ? "bg-teal-100 text-teal-800"
                : "bg-[#eef2f0] text-muted",
        )}
      >
        <Icon className="size-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 pb-1">
        <p className="text-[13.5px] text-ink">{event.summary}</p>
        {event.reason && event.type !== "QuestionResolved" && (
          <p className="mt-0.5 text-[12.5px] text-muted">“{event.reason}”</p>
        )}
        <p className="mt-0.5 text-[11.5px] text-subtle">
          {event.actor} · {dateTime(event.created_at)} · rev {event.revision ?? "—"}
        </p>
      </div>
    </li>
  );
}

function RunCard({ run, defaultOpen }: { run: AgentRun; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const live = !run.ended_at;
  const outcome = OUTCOME[live ? "running" : run.outcome] ?? OUTCOME.no_action;
  const seconds = run.ended_at
    ? (new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000
    : null;
  const gemini = run.controller === "adk-gemini";
  return (
    <li
      className={cx(
        "overflow-hidden rounded-xl border bg-paper",
        live ? "border-blue-200 shadow-[0_0_0_3px_rgba(37,99,168,0.08)]" : "border-line",
      )}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-3 text-left hover:bg-[#fafbfa]"
      >
        <span
          className={cx(
            "grid size-7 shrink-0 place-items-center rounded-lg text-white",
            gemini ? "bg-navy-900" : "bg-[#5b6b70]",
          )}
        >
          {live ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Bot className="size-3.5" aria-hidden />
          )}
        </span>
        <span className="min-w-0 flex-1 basis-[calc(100%-48px)] sm:basis-auto">
          <span className="block text-[13.5px] font-semibold text-ink">
            {gemini ? "Agent run" : "Fixed-rule workflow"} ·{" "}
            {humanize(run.trigger.replace(/([a-z])([A-Z])/g, "$1_$2"))}
            {run.mode === "shadow" && (
              <Badge tone="neutral" className="ml-2">
                shadow
              </Badge>
            )}
          </span>
          <span className="block text-[11.5px] text-subtle">
            {timeOnly(run.started_at)} · {gemini ? `${run.model} via ADK` : "no language model"} ·{" "}
            {run.model_calls} model call{run.model_calls === 1 ? "" : "s"} · {run.tool_calls} tool
            {run.tool_calls === 1 ? "" : "s"}
            {seconds !== null && ` · ${seconds.toFixed(1)} s`}
            {Number(run.cost_usd) > 0 && ` · ${usd(run.cost_usd)}`}
            {run.retries > 0 && ` · ${run.retries} retr${run.retries === 1 ? "y" : "ies"}`}
          </span>
        </span>
        <Badge tone={outcome.tone}>{outcome.label}</Badge>
        <ChevronDown
          className={cx("size-4 text-subtle transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open && (
        <ol className="border-t border-line-soft px-4 py-3">
          {run.actions.length === 0 && (
            <li className="py-1 text-[13px] text-muted">
              {live ? "Reading the committed case state…" : "No tool actions recorded."}
            </li>
          )}
          {run.actions.map((a, idx) => {
            const Icon = TOOL_ICON[a.tool] ?? Cog;
            const bad =
              /STALE|LIMIT|INVALID|NOT_|ALREADY|DENIED|ERROR|STOP|PAUSED/.test(a.result_code) &&
              a.result_code !== "ALREADY_ISSUED";
            return (
              <li key={a.seq} className="relative flex gap-3 pb-3 last:pb-0">
                {idx < run.actions.length - 1 && (
                  <span
                    className="absolute left-[13px] top-7 h-[calc(100%-20px)] w-px bg-line"
                    aria-hidden
                  />
                )}
                <span
                  className={cx(
                    "z-[1] grid size-[27px] shrink-0 place-items-center rounded-full border bg-white",
                    bad ? "border-amber-200 text-amber-700" : "border-line text-teal-700",
                  )}
                >
                  <Icon className="size-3.5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-[13px] font-semibold text-ink">
                    {TOOL_LABEL[a.tool] ?? a.tool}
                    <span
                      className={cx(
                        "rounded px-1.5 py-px font-mono text-[10.5px] font-semibold",
                        bad ? "bg-amber-100 text-amber-700" : "bg-[#eef2f0] text-muted",
                      )}
                    >
                      {a.result_code}
                    </span>
                    {a.shadow && <Badge tone="neutral">proposed only</Badge>}
                    <span className="text-[11px] font-normal text-subtle">{a.duration_ms} ms</span>
                  </p>
                  {a.reason && (
                    <p className="mt-0.5 text-[13px] italic leading-relaxed text-muted">
                      “{a.reason}”
                    </p>
                  )}
                  {a.result_summary && (
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink/80">
                      {a.result_summary}
                    </p>
                  )}
                  {Object.keys(a.args).length > 0 && (
                    <p className="mt-0.5 break-all font-mono text-[11px] text-subtle">
                      {formatArgs(a.args)}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
          {run.stop_reason && (
            <li className="mt-2 rounded-lg bg-[#f6f8f7] px-3 py-2 text-[12.5px] text-muted">
              Stop reason: {humanize(run.stop_reason)}
            </li>
          )}
        </ol>
      )}
    </li>
  );
}

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0))
    .map(
      ([k, v]) =>
        `${k}=${Array.isArray(v) ? v.join(",") : typeof v === "string" && v.length > 40 ? v.slice(0, 40) + "…" : String(v)}`,
    )
    .join("  ");
}
