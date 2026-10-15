"use client";

import { AlertTriangle, Bot, Hand, Lock, ShieldAlert, Sparkles, UserCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { relativeTime } from "@/lib/format";
import { useSession } from "@/lib/session";
import { useCaseCommand } from "@/lib/use-case";
import type { CaseDetail, HumanTask } from "@/lib/types";
import {
  Badge,
  Button,
  Callout,
  Field,
  Input,
  SectionLabel,
  Textarea,
  cx,
} from "@/components/ui/primitives";
import { TASK_KIND } from "@/components/ui/status";

const DECISION_HELP: Record<string, string> = {
  accept_policy_review:
    "Explain how the current documents satisfy this criterion. Your interpretation is saved for this policy and evidence set; new evidence requires another assessment. Core calculations still apply.",
  exclude_rejected_document:
    "Explain why this rejected file is not needed. It stays in history and counts toward no check. The accepted invoice and receipt evidence must satisfy the checklist independently.",
  accept_document_appearance:
    "Record how you checked the highlighted findings, reference template and issuer's explanation. This covers only this document version's appearance; invoice and delivery checks still apply. It is not a certification of authenticity.",
  retain_dispute_request_evidence:
    "Keep the dispute open and authorise a request for a specific correction from the permitted source. Neither statement is declared true; the agent checks the conditions when evidence arrives.",
  record_interpretation:
    "Record what the sources support (for example, a harmless time update). Covers exactly the listed message versions.",
  mark_irrelevant:
    "The message does not bear on the checklist. Covers exactly the listed message versions; new messages still need review.",
  keep_on_hold: "Pause automation on this case. Nothing is resolved; a supervisor can resume.",
  authorise_request:
    "Authorise one further request round for corrected evidence. Does not resolve the question.",
  authorise_extra_round: "Authorise one further request round for the outstanding items.",
  resume_automation: "Resume the agent from its saved work. Completed checks are preserved.",
  grant_extension: "Grant a bounded extension (up to 6 wake-ups and USD 0.50). Supervisor only.",
};

const RELATION_TONE: Record<string, "red" | "teal" | "blue" | "neutral" | "amber"> = {
  contradicts: "red",
  consistent: "teal",
  new_information: "blue",
  unrelated: "neutral",
  unclear: "amber",
};

export function DecisionPanel({
  detail,
  task,
  onSource,
}: {
  detail: CaseDetail;
  task: HumanTask;
  onSource: (label: string) => void;
}) {
  const session = useSession();
  const kind = TASK_KIND[task.kind] ?? TASK_KIND.evidence_problem;
  const KindIcon = kind.icon;
  const mine = task.claimed_by?.id === session.user.id;
  const [now] = useState(() => Date.now());
  const claimedByOther =
    task.state === "claimed" &&
    !mine &&
    !!task.claim_expires_at &&
    new Date(task.claim_expires_at).getTime() > now;
  const canAct =
    detail.permissions.decide &&
    (task.required_role !== "supervisor" || detail.permissions.supervise);

  const suggestion = useMemo(() => suggestConditions(detail, task), [detail, task]);
  const [decision, setDecision] = useState(task.allowed_decisions[0]?.type ?? "");
  const [reason, setReason] = useState("");
  const [interpretation, setInterpretation] = useState("");
  const [receipt, setReceipt] = useState(suggestion.receipt_number ?? "");
  const [delivery, setDelivery] = useState(suggestion.delivery_ref ?? "");
  const [quantity, setQuantity] = useState(suggestion.claimed_quantity ?? "");
  const [wakeups, setWakeups] = useState("4");
  const [budget, setBudget] = useState("0.25");

  const claim = useCaseCommand<void>(
    detail.case.id,
    () => `/v1/tasks/${task.id}/claim`,
    () => ({}),
    { success: "You are reviewing this task" },
  );
  const submit = useCaseCommand<void, { revision: number }>(
    detail.case.id,
    () => `/v1/tasks/${task.id}/decisions`,
    () => ({
      decision_type: decision,
      reason,
      expected_revision: detail.case.revision,
      covered_version_ids: task.source_version_ids,
      params:
        decision === "record_interpretation"
          ? { interpretation }
          : decision === "retain_dispute_request_evidence"
            ? { receipt_number: receipt, delivery_ref: delivery, claimed_quantity: quantity }
            : decision === "grant_extension"
              ? { extra_wakeups: Number(wakeups), extra_budget_usd: budget }
              : {},
    }),
    { success: "Decision recorded — the agent continues from here" },
  );
  const conflict = !!submit.error?.isConflict;

  const needsInterpretation = decision === "record_interpretation";
  const needsConditions = decision === "retain_dispute_request_evidence";
  const valid =
    reason.trim().length >= 5 &&
    (!needsInterpretation || interpretation.trim().length >= 5) &&
    (!needsConditions || (receipt && delivery && Number(quantity) > 0));

  return (
    <section
      aria-labelledby={`task-${task.id}`}
      className="overflow-hidden rounded-[var(--radius-card)] border border-amber-200 bg-paper shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-200 bg-amber-50 px-5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-lg bg-amber-700 text-white">
            <Hand className="size-4" aria-hidden />
          </span>
          <div>
            <p className="text-[11.5px] font-bold uppercase tracking-[0.08em] text-amber-700">
              Needs your decision
            </p>
            <p className="flex items-center gap-1.5 text-[12.5px] text-muted">
              <KindIcon className="size-3.5" aria-hidden /> {kind.label} · opened by the{" "}
              {task.opened_by === "agent" ? "agent" : "policy timer"}{" "}
              {relativeTime(task.created_at)}
            </p>
          </div>
        </div>
        {task.state === "claimed" && task.claimed_by && (
          <Badge
            tone={mine ? "teal" : "amber"}
            icon={mine ? <UserCheck className="size-3" /> : <Lock className="size-3" />}
          >
            {mine
              ? `You are reviewing · claim ends ${relativeTime(task.claim_expires_at)}`
              : `${task.claimed_by.name} is reviewing`}
          </Badge>
        )}
      </div>

      <div className="space-y-5 px-5 py-5">
        <div>
          <h3
            id={`task-${task.id}`}
            className="text-[17px] font-semibold leading-snug tracking-[-0.015em] text-ink"
          >
            {task.title}
          </h3>
          <p className="mt-2 text-[15px] leading-relaxed text-ink">{task.question}</p>
          {task.kind === "document_review" &&
            detail.documents
              .flatMap((d) => d.versions)
              .filter((v) => task.source_version_ids.includes(v.id))
              .map((v) => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => onSource(v.label)}
                  className="mt-3 text-sm font-semibold text-teal-700 underline"
                >
                  View highlighted findings on {v.label}
                </button>
              ))}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-xl bg-[#f6f8f7] p-3.5">
            <SectionLabel>Why automation stopped</SectionLabel>
            <p className="mt-1 text-[13.5px] leading-relaxed text-ink">{task.why_stopped}</p>
          </div>
          {task.proposed_action && (
            <div className="rounded-xl bg-[#f6f8f7] p-3.5">
              <SectionLabel>The agent proposes</SectionLabel>
              <p className="mt-1 flex gap-2 text-[13.5px] leading-relaxed text-ink">
                <Bot className="mt-0.5 size-4 shrink-0 text-navy-700" aria-hidden />
                {task.proposed_action}
              </p>
            </div>
          )}
        </div>

        {task.passages.length > 0 && (
          <div>
            <SectionLabel>Source passages</SectionLabel>
            <ul className="mt-2 space-y-2">
              {task.passages.map((p, i) => (
                <li
                  key={i}
                  className={cx(
                    "rounded-xl border p-3",
                    p.kind === "message"
                      ? "border-amber-200 bg-amber-50/50"
                      : "border-line bg-white",
                  )}
                >
                  <div className="flex items-center gap-2 text-[12px]">
                    <button
                      onClick={() => onSource(p.label)}
                      className="rounded-md border border-line bg-white px-1.5 py-0.5 font-semibold text-teal-700 hover:bg-teal-50"
                    >
                      {p.label}
                    </button>
                    <span className="text-muted">
                      {p.kind === "message"
                        ? `Written message · attributed to ${p.attributed_to}`
                        : "Document line"}
                    </span>
                    {p.relation && (
                      <Badge tone={RELATION_TONE[p.relation] ?? "neutral"}>
                        {p.relation.replace(/_/g, " ")}
                      </Badge>
                    )}
                  </div>
                  <blockquote
                    className={cx(
                      "mt-2 text-[14px] leading-relaxed",
                      p.kind === "message" ? "text-ink" : "font-mono text-[13px] text-ink",
                    )}
                  >
                    “{p.quote}”
                  </blockquote>
                  {p.claim && (
                    <p className="mt-1 text-[12.5px] text-muted">Compared with: {p.claim}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {task.observations.map((o) => (
          <div key={o.id} className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Sparkles className="size-4 text-blue-700" aria-hidden />
              <span className="text-[13px] font-semibold text-ink">Gemini comparison</span>
              <Badge tone={RELATION_TONE[o.relation] ?? "neutral"}>
                {o.relation.replace(/_/g, " ")}
              </Badge>
              <span className="text-[12px] text-muted">
                {o.subject} vs {o.compared.join(", ") || "case sources"} · quotes verified against
                the sources
              </span>
            </div>
            <p className="mt-2 text-[13.5px] leading-relaxed text-ink">{o.summary}</p>
            {o.payload.instructions_detected && (
              <p className="mt-2 flex items-center gap-2 rounded-lg bg-red-100 px-3 py-2 text-[12.5px] font-semibold text-red-700">
                <ShieldAlert className="size-4" aria-hidden /> The message contains instructions
                aimed at the agent. They were treated as evidence and not followed.
              </p>
            )}
            {(o.payload.claims ?? []).length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {o.payload.claims!.map((c, i) => (
                  <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[13px]">
                    <Badge tone={RELATION_TONE[c.relation] ?? "neutral"}>
                      {c.relation.replace(/_/g, " ")}
                    </Badge>
                    <span className="text-ink">{c.statement}</span>
                    {(c.delivery_ref || c.quantity || c.time_qualifier) && (
                      <span className="text-[12px] text-muted">
                        {[
                          c.delivery_ref,
                          c.quantity && `${c.quantity} ${c.unit ?? ""}`.trim(),
                          c.time_qualifier,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {o.payload.missing_context && (
              <p className="mt-2 text-[12.5px] text-muted">
                Missing context: {o.payload.missing_context}
              </p>
            )}
          </div>
        ))}

        {!canAct ? (
          <Callout tone="neutral" title="Read only">
            {task.required_role === "supervisor"
              ? "This decision needs an operations supervisor."
              : "Your role can view this task but not decide it."}
          </Callout>
        ) : claimedByOther ? (
          <Callout tone="amber" title={`${task.claimed_by?.name} is reviewing this task`}>
            Their claim prevents two people editing the same decision. It expires{" "}
            {relativeTime(task.claim_expires_at)} without deciding anything.
          </Callout>
        ) : (
          <form
            className="space-y-4 rounded-xl border border-line p-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit.mutate();
            }}
          >
            <fieldset>
              <legend className="mb-2 text-[13px] font-semibold text-ink">Your decision</legend>
              <div className="grid gap-2" role="radiogroup">
                {task.allowed_decisions.map((d) => (
                  <label
                    key={d.type}
                    className={cx(
                      "flex cursor-pointer gap-3 rounded-xl border p-3 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[#956200]",
                      decision === d.type
                        ? "border-teal-700 bg-teal-50"
                        : "border-line hover:border-teal-300",
                    )}
                  >
                    <input
                      type="radio"
                      name={`decision-${task.id}`}
                      value={d.type}
                      checked={decision === d.type}
                      onChange={() => setDecision(d.type)}
                      className="mt-1 accent-[#00675f]"
                    />
                    <span>
                      <span className="block text-[13.5px] font-semibold text-ink">{d.label}</span>
                      <span className="block text-[12.5px] leading-relaxed text-muted">
                        {DECISION_HELP[d.type]}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            {needsConditions && (
              <div className="grid gap-3 rounded-xl bg-[#f6f8f7] p-3.5 sm:grid-cols-3">
                <Field
                  label="Disputed receipt"
                  htmlFor="c-receipt"
                  hint="The receipt number printed on the document being questioned, such as MR-701."
                >
                  <Input
                    id="c-receipt"
                    value={receipt}
                    onChange={(e) => setReceipt(e.target.value)}
                    placeholder="R1"
                  />
                </Field>
                <Field
                  label="Delivery"
                  htmlFor="c-delivery"
                  hint="The delivery reference on that receipt, such as DEL-701. It identifies the arrival being disputed."
                >
                  <Input
                    id="c-delivery"
                    value={delivery}
                    onChange={(e) => setDelivery(e.target.value)}
                    placeholder="D1"
                  />
                </Field>
                <Field
                  label="Claimed quantity"
                  htmlFor="c-qty"
                  hint="How many units the sender says arrived in that delivery. Use the same unit as the invoice, such as boxes."
                >
                  <Input
                    id="c-qty"
                    inputMode="numeric"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value.replace(/[^0-9]/g, ""))}
                    placeholder="80"
                  />
                </Field>
                <p className="text-[12px] leading-relaxed text-muted sm:col-span-3">
                  Acceptance conditions: a corrected {receipt || "receipt"} from the permitted
                  source that explicitly replaces the current version and states{" "}
                  {quantity || "the claimed quantity"} for {delivery || "the delivery"}, plus
                  distinct receipts for any remaining quantity. A different correction or a new
                  dispute returns to a reviewer.
                </p>
              </div>
            )}
            {needsInterpretation && (
              <Field
                label="Interpretation supported by the sources"
                htmlFor="c-interp"
                hint="Explain what the message means and which documents support that reading. Refer to source labels such as S1. Use at least 5 characters."
              >
                <Textarea
                  id="c-interp"
                  value={interpretation}
                  onChange={(e) => setInterpretation(e.target.value)}
                  placeholder="e.g. The note describes two arrivals on the same day that together match receipt BT-R7; no conflict."
                />
              </Field>
            )}
            {decision === "grant_extension" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Extra agent runs (max 6)"
                  htmlFor="c-w"
                  hint="How many more times the agent may start work on this case. The normal limit has been reached."
                >
                  <Input
                    id="c-w"
                    inputMode="numeric"
                    value={wakeups}
                    onChange={(e) => setWakeups(e.target.value)}
                  />
                </Field>
                <Field
                  label="Extra model budget, USD (max 0.50)"
                  htmlFor="c-b"
                  hint="Additional AI usage allowed for this case. For example, 0.25 adds a 25-cent allowance."
                >
                  <Input
                    id="c-b"
                    inputMode="decimal"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                  />
                </Field>
              </div>
            )}
            <Field
              label="Reason (recorded in the case history)"
              htmlFor={`reason-${task.id}`}
              hint="Explain why the evidence supports your chosen decision. Other reviewers will use this to understand your reasoning. Use at least 5 characters."
            >
              <Textarea
                id={`reason-${task.id}`}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="State the basis for this decision."
                onFocus={() => task.state === "pending" && !claim.isPending && claim.mutate()}
              />
            </Field>
            <p className="text-[12px] text-muted">
              Covers source versions {task.source_labels.join(", ") || "—"} at case revision{" "}
              {detail.case.revision}. There is no general approval or override of failed checks.
            </p>
            {conflict && (
              <Callout
                tone="amber"
                icon={<AlertTriangle className="size-4 text-amber-700" />}
                title="The case changed while you were reviewing"
              >
                Your entries are kept. Check the updated evidence above, then submit again.
              </Callout>
            )}
            <div className="flex flex-wrap items-center justify-end gap-2">
              {task.state === "pending" && (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => claim.mutate()}
                  loading={claim.isPending}
                >
                  Start review
                </Button>
              )}
              <Button type="submit" disabled={!valid} loading={submit.isPending}>
                Record decision
              </Button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

function suggestConditions(
  detail: CaseDetail,
  task: HumanTask,
): { receipt_number?: string; delivery_ref?: string; claimed_quantity?: string } {
  const claims = task.observations
    .flatMap((o) => o.payload.claims ?? [])
    .filter((c) => c.relation === "contradicts" && c.delivery_ref);
  const claim = claims[0];
  if (!claim) return {};
  const receiptDoc = detail.documents.find(
    (d) =>
      d.role === "delivery_receipt" &&
      d.versions.some((v) => v.is_active && v.business_event_ref === claim.delivery_ref),
  );
  return {
    receipt_number: receiptDoc?.number,
    delivery_ref: claim.delivery_ref ?? undefined,
    claimed_quantity: claim.quantity?.replace(/[^0-9]/g, "") || undefined,
  };
}
