"use client";

import {
  AlertOctagon,
  BadgeCheck,
  CircleDashed,
  CircleDot,
  Clock3,
  FileCheck2,
  FileText,
  FileWarning,
  Hand,
  Inbox,
  Loader2,
  MailQuestion,
  MessageSquareText,
  PauseCircle,
  PackageCheck,
  ReceiptText,
  ShieldAlert,
  Truck,
} from "lucide-react";
import React from "react";
import type { StatusKey } from "@/lib/types";
import { cx } from "./primitives";

export const STATUS: Record<
  StatusKey,
  {
    label: string;
    tone: string;
    icon: React.ComponentType<{ className?: string }>;
    ring: string;
    text: string;
    bg: string;
  }
> = {
  needs_decision: {
    label: "Needs a decision",
    tone: "amber",
    icon: Hand,
    ring: "border-amber-200",
    text: "text-amber-700",
    bg: "bg-amber-100",
  },
  working: {
    label: "Agent working",
    tone: "blue",
    icon: Loader2,
    ring: "border-blue-200",
    text: "text-blue-700",
    bg: "bg-blue-100",
  },
  waiting_customer: {
    label: "Waiting for the business",
    tone: "violet",
    icon: Clock3,
    ring: "border-[#ddd3f5]",
    text: "text-violet-700",
    bg: "bg-violet-100",
  },
  paused: {
    label: "Paused",
    tone: "red",
    icon: PauseCircle,
    ring: "border-red-200",
    text: "text-red-700",
    bg: "bg-red-100",
  },
  complete: {
    label: "Review complete",
    tone: "teal",
    icon: BadgeCheck,
    ring: "border-teal-200",
    text: "text-teal-800",
    bg: "bg-teal-100",
  },
  manual: {
    label: "Manual review",
    tone: "neutral",
    icon: Hand,
    ring: "border-line",
    text: "text-muted",
    bg: "bg-[#f1f4f3]",
  },
  idle: {
    label: "Idle",
    tone: "neutral",
    icon: CircleDashed,
    ring: "border-line",
    text: "text-muted",
    bg: "bg-[#f1f4f3]",
  },
};

export function StatusPill({
  status,
  size = "md",
}: {
  status: StatusKey;
  size?: "sm" | "md" | "lg";
}) {
  const s = STATUS[status] ?? STATUS.idle;
  const Icon = s.icon;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold whitespace-nowrap",
        s.ring,
        s.text,
        s.bg,
        size === "sm" && "px-2 py-0.5 text-[11.5px]",
        size === "md" && "px-2.5 py-1 text-[12.5px]",
        size === "lg" && "px-3 py-1.5 text-[13.5px]",
      )}
    >
      <Icon
        className={cx(
          size === "lg" ? "size-4" : "size-3.5",
          status === "working" && "animate-spin",
        )}
        aria-hidden
      />
      {s.label}
    </span>
  );
}

export const QUESTION_STATE: Record<
  string,
  { label: string; className: string; icon: React.ComponentType<{ className?: string }> }
> = {
  resolved: {
    label: "Resolved",
    className: "bg-teal-100 text-teal-800 border-teal-200",
    icon: BadgeCheck,
  },
  waiting_evidence: {
    label: "Waiting for evidence",
    className: "bg-violet-100 text-violet-700 border-[#ddd3f5]",
    icon: Clock3,
  },
  waiting_decision: {
    label: "Waiting for a decision",
    className: "bg-amber-100 text-amber-700 border-amber-200",
    icon: Hand,
  },
  open: { label: "Open", className: "bg-[#f1f4f3] text-ink border-line", icon: CircleDot },
};

export function QuestionStateChip({ state }: { state: string }) {
  const s = QUESTION_STATE[state] ?? QUESTION_STATE.open;
  const Icon = s.icon;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11.5px] font-semibold whitespace-nowrap",
        s.className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {s.label}
    </span>
  );
}

export function roleIcon(role: string, className = "size-4") {
  if (role === "invoice") return <ReceiptText className={className} aria-hidden />;
  if (role === "delivery_receipt") return <PackageCheck className={className} aria-hidden />;
  if (role === "written_message") return <MessageSquareText className={className} aria-hidden />;
  if (role === "status_update") return <Truck className={className} aria-hidden />;
  return <FileText className={className} aria-hidden />;
}

export function sourceStateBadge(v: {
  state: string;
  is_active: boolean;
  duplicate_of: string | null;
  coverage: string;
}) {
  if (v.duplicate_of)
    return { label: `Copy of ${v.duplicate_of}`, tone: "neutral" as const, icon: FileText };
  if (v.state === "rejected")
    return {
      label: v.coverage === "not_required" ? "Not used · replaced" : "Not accepted",
      tone: v.coverage === "not_required" ? ("neutral" as const) : ("red" as const),
      icon: FileWarning,
    };
  if (v.state === "withdrawn")
    return { label: "Withdrawn", tone: "neutral" as const, icon: FileWarning };
  if (v.state === "superseded")
    return { label: "Superseded", tone: "neutral" as const, icon: FileText };
  if (v.coverage === "needs_review")
    return { label: "Needs review", tone: "amber" as const, icon: MailQuestion };
  if (v.coverage === "reviewed")
    return { label: "Reviewed", tone: "teal" as const, icon: FileCheck2 };
  if (v.is_active) return { label: "Active", tone: "teal" as const, icon: FileCheck2 };
  return { label: v.state, tone: "neutral" as const, icon: FileText };
}

export const TOOL_LABEL: Record<string, string> = {
  read_case: "Read case",
  inspect_source: "Inspected source",
  compare_statements: "Compared statements",
  run_checks: "Ran checks",
  prepare_request: "Prepared request",
  issue_request: "Issued request",
  wait_for_event: "Waiting",
  open_human_task: "Opened decision task",
  try_complete: "Attempted completion",
};

export const TASK_KIND: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }> }
> = {
  dispute: { label: "Disputed evidence", icon: ShieldAlert },
  message_review: { label: "Written message", icon: MessageSquareText },
  evidence_problem: { label: "Evidence problem", icon: FileWarning },
  document_review: { label: "Document appearance", icon: FileWarning },
  policy_review: { label: "Policy interpretation", icon: FileWarning },
  document_rejection: { label: "Rejected document", icon: FileWarning },
  no_response: { label: "No reply", icon: Inbox },
  service_failure: { label: "Service failure", icon: AlertOctagon },
  budget_exhausted: { label: "Allowance reached", icon: PauseCircle },
};
