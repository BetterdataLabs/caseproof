"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Hand, Inbox, Lock } from "lucide-react";
import Link from "next/link";
import { getJson } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { InboxTask } from "@/lib/types";
import { PageHeader } from "@/components/shell/app-shell";
import { Badge, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { TASK_KIND } from "@/components/ui/status";

export default function DecisionsPage() {
  const q = useQuery({
    queryKey: ["tasks"],
    queryFn: ({ signal }) => getJson<{ tasks: InboxTask[] }>("/v1/tasks", signal),
    refetchInterval: 10_000,
  });
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        title="Decisions"
        description="Specific questions the agent cannot settle on its own: disputed evidence, written messages and decisions outside its authority. Each opens with its sources and allowed decisions."
      />
      {q.error && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      )}
      {q.data && q.data.tasks.length === 0 && (
        <Card>
          <EmptyState icon={<Inbox className="size-5" />} title="No decisions waiting">
            Routine follow-up is running without approval dialogs. New decisions appear here as soon
            as the agent or a policy timer opens them.
          </EmptyState>
        </Card>
      )}
      <ul className="space-y-3">
        {q.data?.tasks.map((t) => {
          const kind = TASK_KIND[t.kind] ?? TASK_KIND.evidence_problem;
          const Icon = kind.icon;
          return (
            <li key={t.id}>
              <Link
                href={`/cases/${t.case.id}`}
                className="group flex gap-4 rounded-[var(--radius-card)] border border-line bg-paper p-5 shadow-[var(--shadow-card)] transition-colors hover:border-amber-200 hover:bg-amber-50/40"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-amber-100 text-amber-700">
                  <Icon className="size-5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                    <span className="font-mono font-semibold">{t.case.reference}</span>
                    <span>{t.case.title}</span>
                    <Badge tone="amber">{kind.label}</Badge>
                    {t.required_role === "supervisor" && <Badge tone="blue">Supervisor</Badge>}
                    {t.claimed_by && (
                      <Badge tone="neutral" icon={<Lock className="size-3" />}>
                        {t.claimed_by} reviewing
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1.5 text-[15px] font-semibold text-ink">{t.title}</p>
                  <p className="mt-1 line-clamp-2 text-[13.5px] text-muted">{t.question}</p>
                  <p className="mt-2 flex items-center gap-1.5 text-[12px] text-subtle">
                    <Hand className="size-3.5" aria-hidden /> {t.case.seller} · opened{" "}
                    {relativeTime(t.created_at)}
                  </p>
                </div>
                <ArrowRight
                  className="mt-1 size-5 shrink-0 text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-amber-700"
                  aria-hidden
                />
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
