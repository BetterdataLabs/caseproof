"use client";

import {
  ArrowLeft,
  BadgeCheck,
  Bot,
  ChevronDown,
  Clock3,
  Download,
  Eye,
  Hand,
  Loader2,
  Pause,
  PauseCircle,
  Play,
  Settings2,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { dateTime, relativeTime, sgd, usd } from "@/lib/format";
import { useCaseCommand } from "@/lib/use-case";
import type { CaseDetail } from "@/lib/types";
import {
  Badge,
  Button,
  Dialog,
  Field,
  Menu,
  Select,
  Textarea,
  Tip,
  cx,
} from "@/components/ui/primitives";
import { StatusPill } from "@/components/ui/status";

import { PolicyVersionAction } from "./policy-version";

export function CaseHeader({ detail, onOpenTask }: { detail: CaseDetail; onOpenTask: () => void }) {
  const c = detail.case;
  const invoice = detail.questions.find((q) => q.key === "invoice_total")?.metrics as
    Record<string, string> | undefined;
  const current = detail.exports.find((e) => e.is_current && e.state === "ready");
  const [control, setControl] = useState<null | "pause" | "resume" | "mode">(null);
  const [manual, setManual] = useState<null | "run_checks" | "request_open_items" | "complete">(
    null,
  );

  return (
    <header className="space-y-4">
      <Link
        href="/queue"
        className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-muted hover:text-teal-700"
      >
        <ArrowLeft className="size-4" aria-hidden /> Work queue
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[12.5px] font-semibold text-muted">{c.reference}</span>
            <StatusPill status={c.status.key} />
            {c.automation_mode !== "autonomous" && (
              <Badge
                tone="neutral"
                icon={
                  c.automation_mode === "shadow" ? (
                    <Eye className="size-3" />
                  ) : (
                    <Hand className="size-3" />
                  )
                }
              >
                {c.automation_mode === "shadow" ? "Shadow mode" : "Automation off"}
              </Badge>
            )}
          </div>
          <h1 className="mt-2 text-[24px] font-bold tracking-[-0.03em] text-ink sm:text-[27px]">
            {c.title}
          </h1>
          <p className="mt-1 text-[14px] text-muted">
            <span className="font-semibold text-ink">{c.seller}</span> is seeking financing on
            invoice {c.invoice_reference} to{" "}
            <span className="font-semibold text-ink">{c.buyer}</span>
            {invoice?.stated_total && <> · stated {sgd(invoice.stated_total)}</>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PolicyVersionAction detail={detail} />
          {current && (
            <a
              href={`/api/v1/exports/${current.id}/pdf`}
              className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-teal-700 bg-teal-700 px-4 text-sm font-semibold text-white shadow-sm hover:bg-teal-800"
            >
              <Download className="size-4" aria-hidden /> Review summary
            </a>
          )}
          {(detail.permissions.supervise || detail.permissions.decide) && (
            <Menu
              trigger={
                <Button variant="secondary" icon={<Settings2 className="size-4" />}>
                  Controls <ChevronDown className="size-3.5" aria-hidden />
                </Button>
              }
              items={[
                ...(detail.permissions.supervise
                  ? [
                      c.execution === "paused"
                        ? {
                            label: "Resume automation",
                            icon: <Play className="size-4" />,
                            onSelect: () => setControl("resume"),
                          }
                        : {
                            label: "Pause automation",
                            icon: <Pause className="size-4" />,
                            onSelect: () => setControl("pause"),
                            disabled: c.lifecycle === "complete",
                          },
                      {
                        label: "Change automation mode",
                        icon: <Bot className="size-4" />,
                        onSelect: () => setControl("mode"),
                      },
                    ]
                  : []),
                ...(detail.permissions.decide
                  ? [
                      "separator" as const,
                      {
                        label: "Manual: run checks",
                        icon: <Wrench className="size-4" />,
                        onSelect: () => setManual("run_checks"),
                        disabled: c.automation_mode === "autonomous" && c.execution !== "paused",
                      },
                      {
                        label: "Manual: request open items",
                        icon: <Wrench className="size-4" />,
                        onSelect: () => setManual("request_open_items"),
                        disabled: c.automation_mode === "autonomous" && c.execution !== "paused",
                      },
                      {
                        label: "Manual: try completion",
                        icon: <Wrench className="size-4" />,
                        onSelect: () => setManual("complete"),
                        disabled: c.automation_mode === "autonomous" && c.execution !== "paused",
                      },
                    ]
                  : []),
              ]}
            />
          )}
        </div>
      </div>
      <StatusBanner detail={detail} onOpenTask={onOpenTask} />
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-[var(--radius-card)] border border-line bg-paper px-5 py-3.5 text-[12.5px] shadow-[var(--shadow-card)] sm:grid-cols-3 lg:grid-cols-6">
        <Meta
          label="Facility"
          value={c.facility_reference || "—"}
          tip="The bank’s reference for the financing arrangement. A dash means none is linked to this review."
        />
        <Meta
          label="Assigned reviewer"
          value={c.assigned_to?.name ?? "Unassigned"}
          tip="The staff member responsible for reviewing questions the agent cannot resolve."
        />
        <Meta
          label="Policy"
          value={`Checklist v${c.policy.version}`}
          tip={`The rules this review follows: ${c.policy.name}. The version identifies which set of rules applies.`}
        />
        <Meta
          label="Revision"
          value={`#${c.revision}`}
          tip="The saved version of the whole case. This number increases when evidence, checks or decisions change."
        />
        <Meta
          label="Processing steps"
          value={`${c.budget.wakeups_used} of ${c.budget.wakeups_max}`}
          tip="Saved stages of document reading, checks and follow-up, out of this case’s allowed limit. Waiting for a reply does not use steps."
        />
        <Meta
          label={detail.case.credit_research?.enabled ? "AI & search spend (est.)" : "Model spend"}
          value={`${usd(c.budget.cost_actual_usd, 4)}`}
          tip={`AI usage cost for this case. ${usd(c.budget.cost_reserved_usd)} is reserved for work in progress; the case limit is ${usd(c.budget.budget_usd, 2)}.`}
        />
      </dl>
      <ControlDialog detail={detail} kind={control} onClose={() => setControl(null)} />
      <ManualDialog detail={detail} action={manual} onClose={() => setManual(null)} />
    </header>
  );
}

function Meta({ label, value, tip }: { label: string; value: string; tip?: string }) {
  const body = (
    <div className="min-w-0">
      <dt className="text-subtle">{label}</dt>
      <dd className="truncate font-semibold text-ink tabular">{value}</dd>
    </div>
  );
  return tip ? (
    <Tip content={tip}>
      <div tabIndex={0}>{body}</div>
    </Tip>
  ) : (
    body
  );
}

function StatusBanner({ detail, onOpenTask }: { detail: CaseDetail; onOpenTask: () => void }) {
  const c = detail.case;
  const key = c.status.key;
  const pending = detail.tasks.filter((t) => ["pending", "claimed"].includes(t.state));
  const outstanding = detail.requests.filter((r) => r.state === "issued");
  const map = {
    needs_decision: {
      cls: "border-amber-200 bg-amber-50",
      icon: <Hand className="size-5 text-amber-700" />,
      title: `${pending.length} decision${pending.length === 1 ? "" : "s"} for a reviewer`,
      body: pending[0]?.title ?? c.next_action,
    },
    working: {
      cls: "border-blue-200 bg-blue-50",
      icon: <Loader2 className="size-5 animate-spin text-blue-700" />,
      title: "The agent is working on this case",
      body: "Reading the evidence and checking what still needs attention. The results will update here automatically.",
    },
    waiting_customer: {
      cls: "border-[#ddd3f5] bg-violet-100/50",
      icon: <Clock3 className="size-5 text-violet-700" />,
      title: "Waiting for the business",
      body: `${outstanding.reduce((n, r) => n + r.items.filter((i) => ["outstanding", "progress"].includes(i.status)).length, 0)} requested item(s) outstanding. ${detail.permissions.add_input ? "Use “Add documents or reply” below to supply the corrections or receipts listed in the checklist. The agent will check them automatically." : "The business needs to supply the corrections or receipts listed in the checklist."} ${c.next_event_at ? `Next scheduled follow-up ${relativeTime(c.next_event_at)} (${dateTime(c.next_event_at)}).` : ""}`,
    },
    paused: {
      cls: "border-red-200 bg-red-50",
      icon: <PauseCircle className="size-5 text-red-700" />,
      title: "Automation paused",
      body: c.next_action,
    },
    complete: {
      cls: "border-teal-200 bg-teal-50",
      icon: <BadgeCheck className="size-5 text-teal-800" />,
      title: "Document review complete",
      body: "Every checklist question is resolved on current evidence. The summary goes to the bank's financing process — the lending decision stays with the bank.",
    },
    manual: {
      cls: "border-line bg-paper",
      icon: <Hand className="size-5 text-muted" />,
      title: "Manual review",
      body: "Automation is off. Open Controls to run checks, request missing items or try completion yourself. The same document checks still apply.",
    },
    idle: {
      cls: "border-line bg-paper",
      icon: <Bot className="size-5 text-muted" />,
      title: "Idle",
      body: c.next_action || "No work is scheduled.",
    },
  }[key];
  return (
    <div
      role="status"
      aria-live="polite"
      className={cx(
        "flex flex-wrap items-center gap-4 rounded-[var(--radius-card)] border px-5 py-4",
        map.cls,
      )}
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/80 shadow-sm">
        {map.icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-semibold text-ink">{map.title}</p>
        <p className="mt-0.5 text-[13.5px] text-muted">{map.body}</p>
      </div>
      {key === "needs_decision" && detail.permissions.decide && (
        <Button variant="amber" onClick={onOpenTask}>
          Review decision
        </Button>
      )}
    </div>
  );
}

function ControlDialog({
  detail,
  kind,
  onClose,
}: {
  detail: CaseDetail;
  kind: null | "pause" | "resume" | "mode";
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState(
    detail.case.automation_mode === "autonomous" ? "shadow" : "autonomous",
  );
  const cmd = useCaseCommand<void>(
    detail.case.id,
    () => `/v1/cases/${detail.case.id}/automation`,
    () => ({
      action: kind === "mode" ? "set_mode" : kind,
      mode: kind === "mode" ? mode : undefined,
      reason,
      expected_revision: detail.case.revision,
    }),
    {
      success: "Control change recorded",
      onSuccess: () => {
        setReason("");
        onClose();
      },
    },
  );
  const title =
    kind === "pause"
      ? "Pause automation"
      : kind === "resume"
        ? "Resume automation"
        : "Change automation mode";
  return (
    <Dialog
      open={kind !== null}
      onOpenChange={(v) => !v && onClose()}
      title={title}
      description="Control what the agent does on this case. Your change and its reason are saved in the case history."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => cmd.mutate()}
            loading={cmd.isPending}
            disabled={reason.trim().length < 5}
            variant={kind === "pause" ? "danger" : "primary"}
          >
            {title}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {kind === "mode" && (
          <Field
            label="Mode"
            htmlFor="mode"
            hint={
              mode === "autonomous"
                ? "The agent reads PDFs, checks evidence, records requests and completes supported reviews. Exceptions go to a person."
                : mode === "shadow"
                  ? "The agent records suggestions for you to inspect. You perform the review actions manually."
                  : "The agent stays off. Use the manual actions in Controls to carry out the review."
            }
          >
            <Select id="mode" value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="autonomous" disabled={detail.case.automation_mode === "autonomous"}>
                Autonomous sandbox
              </option>
              <option value="shadow" disabled={detail.case.automation_mode === "shadow"}>
                Shadow — record proposals only
              </option>
              <option value="off" disabled={detail.case.automation_mode === "off"}>
                Off — manual review
              </option>
            </Select>
          </Field>
        )}
        <Field
          label="Reason"
          htmlFor="control-reason"
          hint="Explain why you are changing automation, using at least 5 characters. Other staff can read this in the case history."
        >
          <Textarea
            id="control-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why is this change needed?"
          />
        </Field>
      </div>
    </Dialog>
  );
}

function ManualDialog({
  detail,
  action,
  onClose,
}: {
  detail: CaseDetail;
  action: null | "run_checks" | "request_open_items" | "complete";
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const cmd = useCaseCommand<void>(
    detail.case.id,
    () => `/v1/cases/${detail.case.id}/manual`,
    () => ({ action, reason, expected_revision: detail.case.revision }),
    {
      success: "Manual action recorded",
      onSuccess: () => {
        setReason("");
        onClose();
      },
    },
  );
  const label = {
    run_checks: "Run checks",
    request_open_items: "Request open items",
    complete: "Try completion",
  }[action ?? "run_checks"];
  return (
    <Dialog
      open={action !== null}
      onOpenChange={(v) => !v && onClose()}
      title={`Manual fallback · ${label}`}
      description="Uses the same identity, source, revision and audit controls as the agent. It cannot waive missing originals or failed arithmetic."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => cmd.mutate()}
            loading={cmd.isPending}
            disabled={reason.trim().length < 5}
          >
            {label}
          </Button>
        </>
      }
    >
      <Field
        label="Reason"
        htmlFor="manual-reason"
        hint="Explain why you are taking this action yourself, using at least 5 characters. This is saved with the action in the case history."
      >
        <Textarea
          id="manual-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Record why you are acting manually."
        />
      </Field>
      {cmd.error && <p className="mt-3 text-[13px] text-red-700">{cmd.error.message}</p>}
    </Dialog>
  );
}
