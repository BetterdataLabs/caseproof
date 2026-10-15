"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Clock3,
  FileText,
  MessageSquareText,
  Repeat,
  Send,
  Truck,
  Undo2,
  X,
} from "lucide-react";
import { Dialog as RDialog } from "radix-ui";
import { useState } from "react";
import { getJson } from "@/lib/api";
import { useCaseCommand } from "@/lib/use-case";
import type { CaseDetail, StagedResponse } from "@/lib/types";
import { Badge, Button, SectionLabel, Textarea, cx } from "@/components/ui/primitives";
import { ScenarioGuide } from "@/components/case/scenario-guide";

const KIND_ICON = {
  document: FileText,
  status_update: Truck,
  written_message: MessageSquareText,
  withdrawal: Undo2,
} as const;

export function SimulatorDrawer({
  detail,
  open,
  onOpenChange,
}: {
  detail: CaseDetail;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const caseId = detail.case.id;
  const options = useQuery({
    queryKey: ["staged", caseId, detail.case.revision],
    queryFn: ({ signal }) =>
      getJson<{
        responses: StagedResponse[];
        compose_enabled: boolean;
        seller: string;
        walkthrough: string[];
      }>(`/v1/demo/cases/${caseId}/responses`, signal),
    enabled: open,
  });
  const [text, setText] = useState("");
  const [sending, setSending] = useState<string | null>(null);
  const send = useCaseCommand<
    { staged_key?: string; composed_text?: string },
    { created: boolean }
  >(
    caseId,
    () => `/v1/demo/cases/${caseId}/responses`,
    (v) => v,
    {
      success: (r) =>
        r.created
          ? "Reply delivered to the case — the agent wakes up"
          : "Exact replay suppressed: no new work, allowances unchanged",
      onSuccess: () => {
        setText("");
        setSending(null);
        qc.invalidateQueries({ queryKey: ["staged", caseId] });
      },
    },
  );
  const clock = useCaseCommand<{ hours: number }, { effects: string[] }>(
    caseId,
    () => `/v1/demo/cases/${caseId}/clock`,
    (v) => v,
    {
      success: (r) =>
        r.effects.length
          ? `Demo clock advanced · ${r.effects.join(", ")} applied by the policy timer`
          : "Demo clock advanced",
    },
  );
  const waiting = detail.requests.some((r) => r.state === "issued");

  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-40 bg-navy-950/30 animate-[var(--animate-fade-in)]" />
        <RDialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col border-l-4 border-dashed border-amber-600 bg-amber-50 shadow-[var(--shadow-pop)] animate-[var(--animate-slide-in)] focus:outline-none">
          <div className="flex items-start justify-between gap-3 border-b border-amber-200 px-5 py-4">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-amber-700">
                Demonstration only · simulation operator
              </p>
              <RDialog.Title className="mt-1 text-[18px] font-semibold tracking-[-0.015em] text-ink">
                Customer exchange
              </RDialog.Title>
              <RDialog.Description className="mt-1 text-[13px] leading-relaxed text-muted">
                Act as <span className="font-semibold text-ink">{detail.case.seller}</span>.
                Responses enter the case as ordinary saved events. The agent never sees this list or
                any future reply.
              </RDialog.Description>
            </div>
            <RDialog.Close
              className="rounded-lg p-1.5 text-muted hover:bg-amber-100"
              aria-label="Close customer exchange"
            >
              <X className="size-5" />
            </RDialog.Close>
          </div>
          <div className="scroll-thin flex-1 space-y-6 overflow-y-auto px-5 py-5">
            <ScenarioGuide steps={options.data?.walkthrough} />
            <div>
              <SectionLabel>Staged fictional responses</SectionLabel>
              {options.data?.responses.length === 0 && (
                <p className="mt-2 text-[13px] text-muted">This dossier has no staged replies.</p>
              )}
              <ul className="mt-2 space-y-2">
                {options.data?.responses.map((r) => {
                  const Icon = KIND_ICON[r.kind as keyof typeof KIND_ICON] ?? FileText;
                  return (
                    <li
                      key={r.key}
                      className={cx(
                        "rounded-xl border bg-paper p-3",
                        r.already_sent ? "border-line opacity-80" : "border-amber-200",
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-700">
                          <Icon className="size-4" aria-hidden />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[13.5px] font-semibold leading-snug text-ink">
                            {r.label}
                          </p>
                          <p className="mt-0.5 text-[11.5px] text-muted">
                            {r.kind.replace(/_/g, " ")} · from {r.sender}
                          </p>
                        </div>
                      </div>
                      <div className="mt-2.5 flex items-center justify-end gap-2">
                        {r.already_sent && <Badge tone="neutral">Sent</Badge>}
                        <Button
                          size="sm"
                          variant={r.already_sent ? "secondary" : "amber"}
                          icon={
                            r.already_sent ? (
                              <Repeat className="size-3.5" />
                            ) : (
                              <Send className="size-3.5" />
                            )
                          }
                          loading={send.isPending && sending === r.key}
                          disabled={send.isPending}
                          onClick={() => {
                            setSending(r.key);
                            send.mutate({ staged_key: r.key });
                          }}
                        >
                          {r.already_sent ? "Replay exactly" : "Send"}
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>

            {options.data?.compose_enabled && (
              <div>
                <SectionLabel>Compose a written message (private evaluation lane)</SectionLabel>
                <p className="mt-1 text-[12.5px] text-muted">
                  Free text is read by Gemini and always receives a recorded human disposition
                  before completion.
                </p>
                <Textarea
                  className="mt-2 bg-white"
                  maxLength={1200}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="e.g. Only 70 boxes of D1 arrived; the rest come next week."
                  aria-label="Compose a written message"
                />
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[11.5px] text-subtle tabular">{text.length}/1200</span>
                  <Button
                    size="sm"
                    variant="amber"
                    icon={<Building2 className="size-3.5" />}
                    disabled={text.trim().length < 3 || send.isPending}
                    loading={send.isPending && sending === "composed"}
                    onClick={() => {
                      setSending("composed");
                      send.mutate({ composed_text: text });
                    }}
                  >
                    Send as {detail.case.seller.split(" ")[0]}
                  </Button>
                </div>
              </div>
            )}

            <div>
              <SectionLabel>Demo clock</SectionLabel>
              <p className="mt-1 text-[12.5px] text-muted">
                Moves this case&apos;s policy timers. Waiting costs no model calls; the timer sends
                the single permitted reminder, then routes the case to a reviewer.
                {detail.case.clock_offset_hours > 0 &&
                  ` Advanced ${detail.case.clock_offset_hours} h so far.`}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {[
                  { h: 48, label: "+48 h · reminder due" },
                  { h: 72, label: "+72 h · stop point" },
                  { h: 24, label: "+24 h" },
                ].map((c) => (
                  <Button
                    key={c.h}
                    size="sm"
                    variant="secondary"
                    icon={<Clock3 className="size-3.5" />}
                    disabled={!waiting || clock.isPending}
                    onClick={() => clock.mutate({ hours: c.h })}
                  >
                    {c.label}
                  </Button>
                ))}
              </div>
              {!waiting && (
                <p className="mt-1.5 text-[11.5px] text-subtle">
                  Available while a request is outstanding.
                </p>
              )}
            </div>
          </div>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}
