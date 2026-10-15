"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BadgeCheck,
  Clock3,
  Hand,
  Loader2,
  PauseCircle,
  Plus,
  Search,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getJson } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { useRoles } from "@/lib/session";
import type { CaseList, CaseSummary, StatusKey } from "@/lib/types";
import { PageHeader } from "@/components/shell/app-shell";
import { NewCaseDialog } from "@/components/queue/new-case-dialog";
import {
  Avatar,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
  Tip,
  cx,
} from "@/components/ui/primitives";
import { StatusPill } from "@/components/ui/status";

const VIEWS: { key: string; label: string; icon: typeof Hand; hint: string }[] = [
  {
    key: "needs_decision",
    label: "Needs a decision",
    icon: Hand,
    hint: "A reviewer must decide a specific question",
  },
  {
    key: "working",
    label: "Agent working",
    icon: Loader2,
    hint: "The agent is inspecting, checking or requesting",
  },
  {
    key: "waiting_customer",
    label: "Waiting for the business",
    icon: Clock3,
    hint: "A tracked request is outstanding",
  },
  {
    key: "paused",
    label: "Paused",
    icon: PauseCircle,
    hint: "Automation stopped with work preserved",
  },
  {
    key: "complete",
    label: "Complete",
    icon: BadgeCheck,
    hint: "Review summary ready for the financing process",
  },
];

const TILE_TONE: Record<string, string> = {
  needs_decision: "text-amber-700",
  working: "text-blue-700",
  waiting_customer: "text-violet-700",
  paused: "text-red-700",
  complete: "text-teal-800",
};

export default function QueuePage() {
  const router = useRouter();
  const roles = useRoles();
  const [view, setView] = useState("all");
  const [mine, setMine] = useState(false);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setQuery(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  const params = new URLSearchParams({ view: "all" });
  if (mine) params.set("assigned", "me");
  if (query) params.set("q", query);
  const list = useQuery({
    queryKey: ["cases", mine, query],
    queryFn: ({ signal }) => getJson<CaseList>(`/v1/cases?${params}`, signal),
    placeholderData: keepPreviousData,
    refetchInterval: (q) => ((q.state.data?.counts.working ?? 0) > 0 ? 2_000 : 8_000),
  });

  const items = useMemo(() => {
    const all = list.data?.items ?? [];
    return view === "all" ? all : all.filter((c) => c.status.key === view);
  }, [list.data, view]);
  const counts = list.data?.counts ?? {};

  return (
    <div className="mx-auto max-w-[1360px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        title="Work queue"
        description={
          roles.canDecide
            ? "Cases are grouped by the action they need. Routine follow-up runs automatically; you see a case when a decision is yours to make."
            : "Browse cases, documents, conversations and review history. Your viewer access is read-only."
        }
        actions={
          roles.canDecide && (
            <Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
              New case
            </Button>
          )
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {VIEWS.map((v) => {
          const Icon = v.icon;
          const active = view === v.key;
          return (
            <button
              key={v.key}
              onClick={() => setView(active ? "all" : v.key)}
              aria-pressed={active}
              className={cx(
                "group rounded-[var(--radius-card)] border bg-paper p-4 text-left shadow-[var(--shadow-card)] transition-all hover:border-teal-300",
                active ? "border-teal-700 ring-2 ring-teal-200" : "border-line",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] font-semibold text-muted">{v.label}</span>
                <Icon
                  className={cx(
                    "size-4",
                    TILE_TONE[v.key],
                    v.key === "working" && (counts.working ?? 0) > 0 && "animate-spin",
                  )}
                  aria-hidden
                />
              </div>
              <p
                className={cx(
                  "mt-2 text-[30px] font-bold leading-none tracking-[-0.03em]",
                  (counts[v.key] ?? 0) > 0 ? "text-ink" : "text-subtle",
                )}
              >
                {list.isLoading ? "–" : (counts[v.key] ?? 0)}
              </p>
              <p className="mt-2 line-clamp-2 min-h-[30px] text-[11.5px] leading-snug text-subtle">
                {v.hint}
              </p>
            </button>
          );
        })}
      </div>

      <Card className="mt-6 overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-line-soft px-4 py-3">
          <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle"
              aria-hidden
            />
            <Input
              aria-label="Search cases"
              placeholder="Search reference, invoice or business"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          {roles.canDecide && (
            <button
              onClick={() => setMine((m) => !m)}
              aria-pressed={mine}
              className={cx(
                "inline-flex h-10 items-center gap-2 rounded-[10px] border px-3 text-[13px] font-semibold transition-colors",
                mine
                  ? "border-teal-700 bg-teal-50 text-teal-800"
                  : "border-line bg-white text-muted hover:border-teal-300",
              )}
            >
              <UserRound className="size-4" aria-hidden /> Assigned to me
            </button>
          )}
          <div className="ml-auto text-[12.5px] text-subtle" aria-live="polite">
            {view !== "all" && (
              <button
                className="mr-3 font-semibold text-teal-700 hover:underline"
                onClick={() => setView("all")}
              >
                Clear filter
              </button>
            )}
            {items.length} case{items.length === 1 ? "" : "s"}
            {list.isFetching && !list.isLoading && (
              <span className="ml-2 inline-block size-1.5 rounded-full bg-teal-600 align-middle" />
            )}
          </div>
        </div>

        {list.error && !list.data && (
          <div className="p-4">
            <ErrorState error={list.error} onRetry={() => list.refetch()} />
          </div>
        )}
        {list.isLoading && (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        )}
        {list.data && items.length === 0 && (
          <EmptyState
            icon={<BadgeCheck className="size-5" />}
            title={view === "all" ? "No cases yet" : "Nothing in this view"}
            action={
              roles.canDecide && view === "all" ? (
                <Button onClick={() => setCreating(true)} icon={<Plus className="size-4" />}>
                  Create a case
                </Button>
              ) : undefined
            }
          >
            {view === "all"
              ? "Create a case from the fictional document catalog to watch the agent work."
              : "Cases appear here when they need this kind of attention."}
          </EmptyState>
        )}
        {items.length > 0 && (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[920px] text-left text-[13.5px]">
                <thead>
                  <tr className="border-b border-line-soft bg-[#fafbfa] text-[11.5px] font-bold uppercase tracking-[0.06em] text-subtle">
                    <th className="px-4 py-2.5">Case</th>
                    <th className="px-4 py-2.5">Business</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5">Checklist</th>
                    <th className="px-4 py-2.5">Next</th>
                    <th className="px-4 py-2.5">Updated</th>
                    <th className="px-4 py-2.5">
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <CaseRow key={c.id} c={c} onOpen={() => router.push(`/cases/${c.id}`)} />
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="divide-y divide-line-soft md:hidden">
              {items.map((c) => (
                <li key={c.id}>
                  <Link href={`/cases/${c.id}`} className="block px-4 py-3.5 hover:bg-teal-50/50">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[12px] text-muted">{c.reference}</span>
                      <StatusPill status={c.status.key} size="sm" />
                    </div>
                    <p className="mt-1 font-semibold text-ink">{c.title}</p>
                    <p className="text-[12.5px] text-muted">{c.seller}</p>
                    <p className="mt-1.5 text-[12.5px] text-muted">{c.next_action}</p>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
      <NewCaseDialog open={creating} onOpenChange={setCreating} />
    </div>
  );
}

function ChecklistDots({ c }: { c: CaseSummary }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1">
        {c.question_states.map((q) => (
          <Tip key={q.key} content={`${q.key.replace(/_/g, " ")}: ${q.state.replace(/_/g, " ")}`}>
            <span
              className={cx(
                "block h-2 w-6 rounded-full",
                q.state === "resolved"
                  ? "bg-teal-600"
                  : q.state === "waiting_decision"
                    ? "bg-amber-600"
                    : q.state === "waiting_evidence"
                      ? "bg-violet-700/70"
                      : "bg-[#d9e1df]",
              )}
            />
          </Tip>
        ))}
      </div>
      <span className="text-[12px] text-muted tabular">
        {c.total_questions - c.open_questions}/{c.total_questions}
      </span>
    </div>
  );
}

function CaseRow({ c, onOpen }: { c: CaseSummary; onOpen: () => void }) {
  return (
    <tr
      className="cursor-pointer border-b border-line-soft transition-colors last:border-0 hover:bg-teal-50/50"
      onClick={onOpen}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
      tabIndex={0}
      aria-label={`${c.reference} ${c.title}`}
    >
      <td className="px-4 py-3">
        <p className="font-semibold text-ink">{c.title}</p>
        <p className="mt-0.5 font-mono text-[11.5px] text-muted">
          {c.reference} · {c.invoice_reference}
          {c.automation_mode !== "autonomous" && (
            <span className="ml-1.5 rounded bg-[#eef2f0] px-1 font-sans text-[10.5px] font-bold uppercase text-muted">
              {c.automation_mode}
            </span>
          )}
        </p>
      </td>
      <td className="max-w-[220px] px-4 py-3">
        <p className="truncate text-ink">{c.seller}</p>
        <p className="truncate text-[12px] text-muted">Buyer: {c.buyer}</p>
      </td>
      <td className="px-4 py-3">
        <StatusPill status={c.status.key as StatusKey} size="sm" />
      </td>
      <td className="px-4 py-3">
        <ChecklistDots c={c} />
      </td>
      <td className="max-w-[260px] px-4 py-3">
        <p className="line-clamp-2 text-[12.5px] text-muted">{c.next_action}</p>
        {c.next_event_at && (
          <p className="mt-0.5 text-[11.5px] text-subtle">{relativeTime(c.next_event_at)}</p>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-[12.5px] text-muted">
        <div className="flex items-center gap-2">
          {c.assigned_to && (
            <Tip content={`Assigned to ${c.assigned_to.name}`}>
              <span>
                <Avatar name={c.assigned_to.name} size={22} />
              </span>
            </Tip>
          )}
          {relativeTime(c.updated_at)}
        </div>
      </td>
      <td className="px-3 py-3 text-subtle">
        <ArrowRight className="size-4" aria-hidden />
      </td>
    </tr>
  );
}
