"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertOctagon,
  Bot,
  Cpu,
  FlaskRound,
  OctagonX,
  PauseCircle,
  Play,
  Timer,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, command, getJson, newKey } from "@/lib/api";
import { humanize, relativeTime, usd } from "@/lib/format";
import { useRoles } from "@/lib/session";
import { PageHeader } from "@/components/shell/app-shell";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Meter,
  Select,
  Skeleton,
  Textarea,
} from "@/components/ui/primitives";

interface Ops {
  controls: {
    automation_enabled: boolean;
    revision: number;
    model_fault: string | null;
    model_fault_remaining: number;
    reason: string;
    updated_at: string;
  };
  cases: Record<string, number>;
  case_total: number;
  open_tasks: number;
  paused: { id: string; reference: string; title: string; reason: string; next_action: string }[];
  queue: { queued: number; running: number; oldest_queued_seconds: number };
  model: {
    name: string;
    location: string;
    calls_today: number;
    errors_today: number;
    error_codes: string[];
    cost_today_usd: string;
    daily_budget_usd: string;
    p95_latency_ms: number | null;
    input_tokens_today: number;
    output_tokens_today: number;
  };
  stale_rejections: number;
  recent_runs: {
    id: string;
    case_id: string;
    case_reference: string;
    trigger: string;
    controller: string;
    outcome: string;
    stop_reason: string;
    model_calls: number;
    tool_calls: number;
    model_calls_limit: number;
    tool_calls_limit: number;
    cost_usd: string;
    started_at: string;
    duration_s: number | null;
  }[];
  limits: Record<string, string | number>;
}

function Stat({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-[12.5px] font-semibold text-muted">
        {label}
        <span className="text-subtle">{icon}</span>
      </div>
      <p className="mt-2 text-[28px] font-bold leading-none tracking-[-0.03em] text-ink">{value}</p>
      {sub && <div className="mt-2 text-[12px] text-subtle">{sub}</div>}
    </Card>
  );
}

export default function OperationsPage() {
  const roles = useRoles();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["operations"],
    queryFn: ({ signal }) => getJson<Ops>("/v1/operations", signal),
    refetchInterval: 5_000,
  });
  const [dialog, setDialog] = useState<null | "stop" | "resume" | "fault">(null);
  const [reason, setReason] = useState("");
  const [fault, setFault] = useState("timeout");
  const key = useRef<string | null>(null);
  const change = useMutation({
    mutationFn: (body: Record<string, unknown>) => {
      key.current = key.current ?? newKey("ctl");
      return command(
        "/v1/operations/controls",
        { ...body, reason, expected_control_revision: q.data?.controls.revision },
        key.current,
      );
    },
    onSuccess: () => {
      key.current = null;
      toast.success("Control change recorded");
      setDialog(null);
      setReason("");
      qc.invalidateQueries({ queryKey: ["operations"] });
      qc.invalidateQueries({ queryKey: ["session"] });
    },
    onError: (e) => {
      key.current = null;
      toast.error(e instanceof ApiError ? e.message : "Change failed");
    },
  });

  if (q.error)
    return (
      <div className="mx-auto max-w-[1360px] px-8 py-8">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  const d = q.data;
  const spend = Number(d?.model.cost_today_usd ?? 0);
  const budget = Number(d?.model.daily_budget_usd ?? 20);

  return (
    <div className="mx-auto max-w-[1360px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        title="Operations"
        description="Queue health, model usage against its caps, paused work and automation controls. Telemetry carries IDs, reason codes, durations and usage — never document content."
        actions={
          d && (
            <>
              {roles.isAdmin && (
                <Button
                  variant="secondary"
                  icon={<FlaskRound className="size-4" />}
                  onClick={() => setDialog("fault")}
                >
                  Fault injection
                </Button>
              )}
              {roles.canSupervise &&
                (d.controls.automation_enabled ? (
                  <Button
                    variant="danger"
                    icon={<OctagonX className="size-4" />}
                    onClick={() => setDialog("stop")}
                  >
                    Emergency stop
                  </Button>
                ) : (
                  <Button icon={<Play className="size-4" />} onClick={() => setDialog("resume")}>
                    Resume automation
                  </Button>
                ))}
            </>
          )
        }
      />
      {!d ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {!d.controls.automation_enabled && (
            <div className="flex items-center gap-3 rounded-[var(--radius-card)] border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
              <AlertOctagon className="size-5" aria-hidden />
              <span>
                <span className="font-semibold">Emergency stop active.</span> New agent effects are
                rejected at the transaction boundary. Reason: {d.controls.reason}
              </span>
            </div>
          )}
          {d.controls.model_fault && (
            <div className="flex items-center gap-3 rounded-[var(--radius-card)] border border-amber-200 bg-amber-50 px-5 py-3 text-[13.5px] text-amber-700">
              <FlaskRound className="size-4" aria-hidden /> Fault injection armed: the next{" "}
              {d.controls.model_fault_remaining} model call(s) fail with a simulated{" "}
              {d.controls.model_fault}. Labelled as injected in provider records.
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Queue"
              value={d.queue.queued}
              icon={<Timer className="size-4" />}
              sub={`${d.queue.running} running · oldest waiting ${d.queue.oldest_queued_seconds}s · limit ${d.limits.org_concurrency} per organisation`}
            />
            <Stat
              label="Open decisions"
              value={d.open_tasks}
              icon={<Bot className="size-4" />}
              sub={`${d.case_total} cases · ${d.cases.complete ?? 0} complete`}
            />
            <Stat
              label="Model calls today"
              value={d.model.calls_today}
              icon={<Cpu className="size-4" />}
              sub={`${d.model.errors_today} errors${d.model.error_codes.length ? ` (${d.model.error_codes.join(", ")})` : ""} · p95 ${d.model.p95_latency_ms ? (d.model.p95_latency_ms / 1000).toFixed(1) + " s" : "—"}`}
            />
            <Card className="p-4">
              <div className="flex items-center justify-between text-[12.5px] font-semibold text-muted">
                Model spend today
                <Zap className="size-4 text-subtle" aria-hidden />
              </div>
              <p className="mt-2 text-[28px] font-bold leading-none tracking-[-0.03em] text-ink">
                {usd(spend, 3)}
              </p>
              <div className="mt-3">
                <Meter
                  value={spend}
                  max={budget}
                  label="Daily model budget used"
                  tone={spend / budget > 0.8 ? "red" : spend / budget > 0.5 ? "amber" : "teal"}
                />
              </div>
              <p className="mt-1.5 text-[12px] text-subtle">
                of {usd(budget, 2)} daily cap · {(d.model.input_tokens_today / 1000).toFixed(1)}k in
                / {(d.model.output_tokens_today / 1000).toFixed(1)}k out tokens
              </p>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <Card className="overflow-hidden">
              <CardHeader
                title="Recent agent runs"
                description={`${d.model.name} · ${d.model.location} · ${d.stale_rejections} stale results rejected`}
              />
              {d.recent_runs.length === 0 ? (
                <EmptyState icon={<Bot className="size-5" />} title="No runs yet" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-[13px]">
                    <thead>
                      <tr className="border-b border-line-soft bg-[#fafbfa] text-[11px] font-bold uppercase tracking-[0.06em] text-subtle">
                        <th className="px-4 py-2">Case</th>
                        <th className="px-4 py-2">Trigger</th>
                        <th className="px-4 py-2">Outcome</th>
                        <th className="px-4 py-2 text-right">Model</th>
                        <th className="px-4 py-2 text-right">Tools</th>
                        <th className="px-4 py-2 text-right">Time</th>
                        <th className="px-4 py-2 text-right">Cost</th>
                        <th className="px-4 py-2">Started</th>
                      </tr>
                    </thead>
                    <tbody className="tabular [&_td]:whitespace-nowrap">
                      {d.recent_runs.map((r) => (
                        <tr key={r.id} className="border-b border-line-soft last:border-0">
                          <td className="px-4 py-2">
                            <Link
                              href={`/cases/${r.case_id}`}
                              className="font-mono text-[12px] font-semibold text-teal-700 hover:underline"
                            >
                              {r.case_reference}
                            </Link>
                          </td>
                          <td className="px-4 py-2 text-muted">
                            {humanize(r.trigger.replace(/([a-z])([A-Z])/g, "$1_$2"))}
                          </td>
                          <td className="px-4 py-2">
                            <Badge
                              tone={
                                r.outcome === "completed"
                                  ? "teal"
                                  : r.outcome === "paused"
                                    ? "red"
                                    : r.outcome === "human_task"
                                      ? "amber"
                                      : r.outcome === "waiting"
                                        ? "violet"
                                        : "neutral"
                              }
                            >
                              {humanize(r.outcome)}
                            </Badge>
                            {r.stop_reason && (
                              <span className="ml-1.5 text-[11.5px] text-subtle">
                                {r.stop_reason}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2 text-right">
                            {r.model_calls}/{r.model_calls_limit}
                          </td>
                          <td className="px-4 py-2 text-right">
                            {r.tool_calls}/{r.tool_calls_limit}
                          </td>
                          <td className="px-4 py-2 text-right">{r.duration_s ?? "—"} s</td>
                          <td className="px-4 py-2 text-right">{usd(r.cost_usd)}</td>
                          <td className="px-4 py-2 text-muted">{relativeTime(r.started_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
            <div className="space-y-6">
              <Card>
                <CardHeader title="Paused work" icon={<PauseCircle className="size-4" />} />
                {d.paused.length === 0 ? (
                  <p className="px-5 py-4 text-[13px] text-muted">Nothing is paused.</p>
                ) : (
                  <ul className="divide-y divide-line-soft">
                    {d.paused.map((p) => (
                      <li key={p.id} className="px-5 py-3">
                        <Link
                          href={`/cases/${p.id}`}
                          className="text-[13.5px] font-semibold text-teal-700 hover:underline"
                        >
                          {p.reference} · {p.title}
                        </Link>
                        <p className="mt-0.5 text-[12.5px] text-muted">
                          {humanize(p.reason)} — {p.next_action}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card>
                <CardHeader
                  title="Default operating limits"
                  description="Newer policy versions may set different case limits. Concurrency is managed by the server."
                />
                <dl className="divide-y divide-line-soft text-[13px]">
                  {[
                    ["Model calls per invocation", d.limits.model_calls],
                    ["Tool calls per invocation", d.limits.tool_calls],
                    ["Active seconds per invocation", d.limits.active_seconds],
                    ["Automatic wake-ups per case", d.limits.wakeups],
                    ["Model budget per case", `USD ${d.limits.case_budget_usd}`],
                    [
                      "Concurrent agent runs",
                      `${d.limits.global_concurrency} total · ${d.limits.org_concurrency} per organisation`,
                    ],
                  ].map(([k, v]) => (
                    <div key={String(k)} className="flex justify-between gap-3 px-5 py-2.5">
                      <dt className="text-muted">{k}</dt>
                      <dd className="font-semibold text-ink tabular">{v}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
            </div>
          </div>
        </div>
      )}

      <Dialog
        open={dialog !== null}
        onOpenChange={(v) => !v && setDialog(null)}
        title={
          dialog === "stop"
            ? "Emergency stop"
            : dialog === "resume"
              ? "Resume automation"
              : "Fault injection (demonstration)"
        }
        description={
          dialog === "stop"
            ? "Rejects new agent effects for this organisation at the transaction boundary. In-flight model calls may still incur cost; their results are not applied."
            : dialog === "resume"
              ? "Cases continue on their next saved event."
              : "Make the next model calls fail with a simulated transient error to exercise bounded retries, pause and recovery. Never available outside the demo environment."
        }
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button
              variant={dialog === "stop" ? "danger" : "primary"}
              disabled={reason.trim().length < 5}
              loading={change.isPending}
              onClick={() =>
                change.mutate(
                  dialog === "fault"
                    ? { model_fault: fault, fault_count: 3 }
                    : { automation_enabled: dialog === "resume" },
                )
              }
            >
              Confirm
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {dialog === "fault" && (
            <Field
              label="Simulated problem"
              htmlFor="fault"
              hint="Test recovery by making the next three AI calls in this organisation fail. Timeout means no response; quota means the service refuses more calls. Clear removes the simulation."
            >
              <Select id="fault" value={fault} onChange={(e) => setFault(e.target.value)}>
                <option value="timeout">Model timeout × 3 calls</option>
                <option value="quota">Quota exhausted × 3 calls</option>
                <option value="none">Clear fault injection</option>
              </Select>
            </Field>
          )}
          <Field
            label="Reason"
            htmlFor="ops-reason"
            hint="Explain this organisation-wide change, using at least 5 characters. The reason is saved so other staff can understand it."
          >
            <Textarea id="ops-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
        </div>
      </Dialog>
    </div>
  );
}
