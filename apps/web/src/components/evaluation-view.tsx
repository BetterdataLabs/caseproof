"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical, Info, ShieldCheck } from "lucide-react";
import { getJson } from "@/lib/api";
import { dateTime, humanize, usd } from "@/lib/format";
import { PageHeader } from "@/components/shell/app-shell";
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Skeleton,
  Tip,
  cx,
} from "@/components/ui/primitives";

type Agg = Record<string, number | null>;
interface Report {
  generated_at: string;
  model: string;
  location: string;
  cases: number;
  families: string[];
  time_model_minutes: { manual: Record<string, number>; tasks: Record<string, number> };
  summary: { manual: Agg; rules: Agg; agent: Agg; per_family: Record<string, Record<string, Agg>> };
  notes: string[];
}

const CONDITIONS = [
  { key: "manual", label: "Manual follow-up", hint: "Estimated from the stated time model" },
  { key: "rules", label: "Fixed-rule workflow", hint: "Same platform, no language model" },
  { key: "agent", label: "CaseProof agent", hint: "Gemini via ADK on Vertex AI" },
] as const;

const FAMILY_LABEL: Record<string, string> = {
  clean: "Clean evidence",
  two_gaps: "Two independent gaps",
  partial_dispatch: "Partial reply: dispatch then receipt",
  duplicate_copy: "Duplicate receipt copy",
  wrong_total: "Wrong total only",
  replacement_scope: "Replacement changes other fields",
  same_event_dispute: "Same-event dispute",
  harmless_time: "Harmless time update",
  unrelated_message: "Unrelated message",
  injection: "Injected instructions",
  cumulative: "Cumulative receipt",
  model_failure: "Model outage",
};

function n(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : String(v);
}

export function EvaluationView() {
  const q = useQuery({
    queryKey: ["evaluation"],
    queryFn: ({ signal }) =>
      getJson<{ available: boolean; report?: Report }>("/v1/evaluation", signal),
  });
  if (q.error)
    return (
      <div className="p-8">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  const r = q.data?.report;
  const s = r?.summary;
  const minutes = s
    ? CONDITIONS.map((c) => ({ ...c, value: Number(s[c.key]?.staff_minutes ?? 0) }))
    : [];
  const maxMinutes = Math.max(1, ...minutes.map((m) => m.value));

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        title="Evaluation"
        description="Held-out cases across twelve families, run through the same platform, documents, checklist and staged replies under each condition. Expected outcomes live outside the application and are compared only after each case finishes."
        eyebrow={
          r && (
            <Badge
              tone="teal"
              className="whitespace-normal!"
              icon={<FlaskConical className="size-3" />}
            >
              {r.cases} cases · {r.families.length} families · {r.model} ({r.location}) ·{" "}
              {dateTime(r.generated_at)}
            </Badge>
          )
        }
      />
      {q.isLoading && <Skeleton className="h-96" />}
      {q.data && !q.data.available && (
        <Card>
          <EmptyState icon={<FlaskConical className="size-5" />} title="No evaluation report yet">
            No evaluation report has been published for this deployment.
          </EmptyState>
        </Card>
      )}
      {r && s && (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="p-4">
              <p className="flex items-center justify-between text-[12.5px] font-semibold text-muted">
                Unsafe completions <ShieldCheck className="size-4 text-teal-700" aria-hidden />
              </p>
              <p className="mt-2 text-[30px] font-bold leading-none tracking-[-0.03em] text-ink">
                {n(s.agent.incorrect_completions)}
              </p>
              <p className="mt-2 text-[12px] text-subtle">
                Agent · fixed rules: {n(s.rules.incorrect_completions)}. Any unsafe completion
                blocks the release.
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-[12.5px] font-semibold text-muted">
                Routine cases completed automatically
              </p>
              <p className="mt-2 text-[30px] font-bold leading-none tracking-[-0.03em] text-ink">
                {n(s.agent.automatic_completions)}
                <span className="text-[16px] font-semibold text-subtle">
                  {" "}
                  / {n(s.agent.automatic_completion_opportunities)}
                </span>
              </p>
              <p className="mt-2 text-[12px] text-subtle">
                No staff confirmation · fixed rules: {n(s.rules.automatic_completions)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-[12.5px] font-semibold text-muted">
                Message interpretation accuracy
              </p>
              <p className="mt-2 text-[30px] font-bold leading-none tracking-[-0.03em] text-ink">
                {s.agent.interpretation_accuracy !== null &&
                s.agent.interpretation_accuracy !== undefined
                  ? `${Math.round(Number(s.agent.interpretation_accuracy) * 100)}%`
                  : "—"}
              </p>
              <p className="mt-2 text-[12px] text-subtle">
                Dispute vs harmless vs unrelated, {n(s.agent.interpretation_cases)} messages · fixed
                rules cannot interpret
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-[12.5px] font-semibold text-muted">
                Injected instructions flagged
              </p>
              <p className="mt-2 text-[30px] font-bold leading-none tracking-[-0.03em] text-ink">
                {s.agent.injection_flag_rate !== null && s.agent.injection_flag_rate !== undefined
                  ? `${Math.round(Number(s.agent.injection_flag_rate) * 100)}%`
                  : "—"}
              </p>
              <p className="mt-2 text-[12px] text-subtle">
                None followed in any condition: tool authority is enforced by the application
              </p>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Estimated staff minutes for the whole set"
              description="Lower is better. Includes every human task and decision; manual follow-up is a stated estimate, not a measurement."
            />
            <div
              className="space-y-3 px-5 py-5"
              role="img"
              aria-label={minutes.map((m) => `${m.label}: ${m.value} minutes`).join("; ")}
            >
              {minutes.map((m) => (
                <div
                  key={m.key}
                  className="grid grid-cols-[150px_minmax(0,1fr)_64px] items-center gap-3 sm:grid-cols-[190px_minmax(0,1fr)_72px]"
                >
                  <span className="text-[13px] font-semibold text-ink">{m.label}</span>
                  <Tip content={`${m.label}: ${m.value} minutes · ${m.hint}`}>
                    <div className="h-6 rounded-[4px] bg-[#eef2f0]">
                      <div
                        className={cx(
                          "h-6 rounded-[4px]",
                          m.key === "agent" ? "bg-teal-700" : "bg-[#9fb3ae]",
                        )}
                        style={{ width: `${(m.value / maxMinutes) * 100}%` }}
                      />
                    </div>
                  </Tip>
                  <span className="text-right text-[13px] font-semibold text-ink tabular">
                    {m.value} min
                  </span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader
              title="Comparison"
              description="Same held-out inputs and scripted reviewer decisions in every condition."
            />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line-soft bg-[#fafbfa] text-[11px] font-bold uppercase tracking-[0.06em] text-subtle">
                    <th className="px-5 py-2.5">Measure</th>
                    {CONDITIONS.map((c) => (
                      <th key={c.key} className="px-5 py-2.5 text-right">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="tabular">
                  {[
                    ["Incorrect (unsafe) completions", "incorrect_completions"],
                    ["Missed completions", "missed_completions"],
                    ["False escalations to a person", "false_escalations"],
                    ["Missed escalations", "missed_escalations"],
                    ["Human tasks opened", "human_tasks"],
                    ["Repeat requests", "repeat_requests"],
                    ["Messages with a prepared, quote-verified comparison", "prepared_comparisons"],
                    ["Staff minutes (estimated)", "staff_minutes"],
                    ["Model calls", "model_calls"],
                    ["Model cost (USD)", "cost_usd"],
                    ["Mean seconds per case", "mean_seconds_per_case"],
                  ].map(([label, key]) => (
                    <tr key={key} className="border-b border-line-soft last:border-0">
                      <td className="px-5 py-2.5 text-ink">{label}</td>
                      {CONDITIONS.map((c) => {
                        const v = s[c.key]?.[key];
                        return (
                          <td key={c.key} className="px-5 py-2.5 text-right font-semibold text-ink">
                            {key === "cost_usd" ? (
                              v === undefined ? (
                                "—"
                              ) : (
                                usd(v, 3)
                              )
                            ) : c.key === "manual" && v === undefined ? (
                              <span className="font-normal text-subtle">n/a</span>
                            ) : (
                              n(v as number)
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader
              title="By scenario family"
              description="Completed / cases, human tasks and, for written messages, the agent's interpretation."
            />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-[13px]">
                <thead>
                  <tr className="border-b border-line-soft bg-[#fafbfa] text-[11px] font-bold uppercase tracking-[0.06em] text-subtle">
                    <th className="px-5 py-2.5">Family</th>
                    <th className="px-5 py-2.5 text-right">Rules: completed</th>
                    <th className="px-5 py-2.5 text-right">Rules: tasks</th>
                    <th className="px-5 py-2.5 text-right">Agent: completed</th>
                    <th className="px-5 py-2.5 text-right">Agent: tasks</th>
                    <th className="px-5 py-2.5 text-right">Agent: interpretation</th>
                    <th className="px-5 py-2.5 text-right">Unsafe</th>
                  </tr>
                </thead>
                <tbody className="tabular">
                  {Object.entries(s.per_family).map(([family, row]) => (
                    <tr key={family} className="border-b border-line-soft last:border-0">
                      <td className="px-5 py-2.5 font-semibold text-ink">
                        {FAMILY_LABEL[family] ?? humanize(family)}
                      </td>
                      <td className="px-5 py-2.5 text-right">
                        {n(row.rules?.completed)}/{n(row.rules?.cases)}
                      </td>
                      <td className="px-5 py-2.5 text-right">{n(row.rules?.human_tasks)}</td>
                      <td className="px-5 py-2.5 text-right">
                        {n(row.agent?.completed)}/{n(row.agent?.cases)}
                      </td>
                      <td className="px-5 py-2.5 text-right">{n(row.agent?.human_tasks)}</td>
                      <td className="px-5 py-2.5 text-right">
                        {row.agent?.interpretation_cases
                          ? `${row.agent.interpretation_correct}/${row.agent.interpretation_cases}`
                          : "—"}
                      </td>
                      <td className="px-5 py-2.5 text-right">
                        {Number(row.agent?.incorrect_completions ?? 0) +
                          Number(row.rules?.incorrect_completions ?? 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="p-5">
            <p className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
              <Info className="size-4 text-teal-700" aria-hidden /> How to read this
            </p>
            <ul className="mt-2 space-y-1.5 text-[13px] text-muted">
              {r.notes.map((note) => (
                <li key={note}>• {note}</li>
              ))}
              <li>
                • Time model (minutes): manual{" "}
                {Object.entries(r.time_model_minutes.manual)
                  .map(([k, v]) => `${humanize(k).toLowerCase()} ${v}`)
                  .join(", ")}
                ; reviewer tasks{" "}
                {Object.entries(r.time_model_minutes.tasks)
                  .map(([k, v]) => `${humanize(k).toLowerCase()} ${v}`)
                  .join(", ")}
                .
              </li>
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
