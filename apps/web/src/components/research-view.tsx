"use client";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCheck,
  Clock3,
  Globe,
  RefreshCw,
  Search,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { dateTime, relativeTime } from "@/lib/format";
import type { ResearchList } from "@/lib/types";
import { useCaseDetail } from "@/lib/use-case";
import {
  CreditResearchPanel,
  researchOutcomes,
  ResearchStatusBadge,
} from "@/components/case/credit-research";
import { PageHeader } from "@/components/shell/app-shell";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  Select,
  Skeleton,
  cx,
} from "@/components/ui/primitives";

function ResearchDetail({ id }: { id: string }) {
  const detail = useCaseDetail(id);
  if (detail.error) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;
  if (!detail.data) return <Skeleton className="h-96" />;
  const c = detail.data.case;
  return (
    <section aria-label={`Research for ${c.reference}`} className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-xs font-semibold text-teal-700">{c.reference}</p>
            {c.lifecycle === "archived" && <Badge>Archived case</Badge>}
          </div>
          <h2 className="mt-1 text-lg font-semibold text-ink">{c.title}</h2>
          <p className="mt-1 text-xs text-muted">
            Invoice {c.invoice_reference || "not yet identified"} · {c.seller} → {c.buyer}
          </p>
        </div>
        <Link
          href={`/cases/${id}`}
          className="inline-flex items-center gap-1 text-sm font-semibold text-teal-700 hover:underline"
        >
          Open case <ArrowUpRight className="size-4" aria-hidden />
        </Link>
      </div>
      {c.credit_research?.enabled ? (
        <CreditResearchPanel detail={detail.data} expanded />
      ) : (
        <Card>
          <EmptyState
            icon={<Globe className="size-5" />}
            title="Research was not requested for this case"
          />
        </Card>
      )}
    </section>
  );
}

export function ResearchView() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);
  const list = useInfiniteQuery({
    queryKey: ["research", query, status],
    initialPageParam: 0,
    queryFn: ({ signal, pageParam }) => {
      const filters = new URLSearchParams({ q: query, status, cursor: String(pageParam) });
      return getJson<ResearchList>(`/v1/research?${filters}`, signal);
    },
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    refetchInterval: (q) => {
      const counts = q.state.data?.pages[0]?.counts;
      return (counts?.pending ?? 0) + (counts?.researching ?? 0) > 0 ? 5_000 : 15_000;
    },
  });
  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const counts = list.data?.pages[0]?.counts;
  const activeId = params.get("case") || items[0]?.id;
  const filtered = query.length > 0 || status !== "all";
  function clearSelection() {
    if (params.has("case")) router.replace("/research", { scroll: false });
  }
  function resetFilters() {
    setSearch("");
    setQuery("");
    setStatus("all");
    clearSelection();
  }

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        title="Research"
        description="The agent’s company findings, public sources and search history, organised by case."
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw className="size-4" />}
            loading={list.isRefetching}
            onClick={() => {
              void list.refetch();
              if (activeId) void qc.invalidateQueries({ queryKey: ["case", activeId] });
            }}
          >
            Refresh
          </Button>
        }
      />
      <div className="mb-6 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          { label: "Cases with research", value: counts?.all, icon: Globe },
          {
            label: "In progress",
            value: counts ? (counts.pending ?? 0) + (counts.researching ?? 0) : undefined,
            icon: Clock3,
          },
          {
            label: "Complete",
            value: counts ? (counts.complete ?? 0) : undefined,
            icon: CheckCheck,
          },
          {
            label: "Failed",
            value: counts ? (counts.failed ?? 0) : undefined,
            icon: TriangleAlert,
          },
        ].map(({ label, value, icon: Icon }) => (
          <Card key={label} className="p-4">
            <div className="flex items-center justify-between gap-2 text-xs font-semibold text-muted">
              {label}
              <Icon className="size-4 shrink-0 text-teal-700" aria-hidden />
            </div>
            <p className="mt-2 text-2xl font-bold text-ink tabular">{value ?? "—"}</p>
          </Card>
        ))}
      </div>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-3 size-4 text-subtle"
            aria-hidden
          />
          <Input
            aria-label="Search research by case or company"
            placeholder="Search by case, company or invoice…"
            value={search}
            maxLength={200}
            className="pl-9"
            onChange={(e) => {
              setSearch(e.target.value);
              clearSelection();
            }}
          />
        </div>
        <Select
          aria-label="Research status"
          className="sm:w-48"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            clearSelection();
          }}
        >
          <option value="all">All research</option>
          <option value="pending">Queued</option>
          <option value="researching">Researching</option>
          <option value="complete">Complete</option>
          <option value="failed">Failed</option>
        </Select>
      </div>
      {list.error && (
        <div className="mb-4">
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        </div>
      )}
      {list.isPending ? (
        <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Skeleton className="h-72" />
          <Skeleton className="h-96" />
        </div>
      ) : !items.length && !activeId && !list.error ? (
        <Card>
          <EmptyState
            icon={<Globe className="size-5" />}
            title={filtered ? "No matching research" : "No company research yet"}
            action={
              filtered ? (
                <Button variant="secondary" onClick={resetFilters}>
                  Clear filters
                </Button>
              ) : (
                <Link href="/queue" className="text-sm font-semibold text-teal-700 hover:underline">
                  Go to work queue
                </Link>
              )
            }
          >
            {filtered
              ? "Try a different company, case reference or status."
              : "Choose “Include company credit research” when creating a case. Findings and sources appear here as the agent saves them."}
          </EmptyState>
        </Card>
      ) : activeId ? (
        <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="overflow-hidden lg:sticky lg:top-6">
            <div className="border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">Cases</h2>
              <p className="mt-1 text-xs text-muted" aria-live="polite">
                {counts?.[status] ?? 0} {filtered ? "matching" : "with research"} · Most recently
                updated first
              </p>
            </div>
            <div className="max-h-96 overflow-y-auto lg:max-h-[calc(100vh-16rem)]">
              <ul aria-label="Cases with research" className="divide-y divide-line-soft">
                {items.map((item) => {
                  const report = item.research;
                  const company =
                    report.subject?.name || (report.target === "seller" ? item.seller : item.buyer);
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        aria-pressed={activeId === item.id}
                        onClick={() =>
                          router.replace(`/research?case=${item.id}`, { scroll: false })
                        }
                        className={cx(
                          "w-full border-l-[3px] px-4 py-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-teal-700 focus-visible:-outline-offset-2",
                          activeId === item.id
                            ? "border-teal-700 bg-teal-50/70"
                            : "border-transparent hover:bg-teal-50/40",
                        )}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-mono text-xs font-semibold text-teal-700">
                            {item.reference}
                          </span>
                          <ResearchStatusBadge report={report} />
                        </div>
                        <p className="mt-2 line-clamp-2 text-sm font-semibold text-ink">
                          {company || item.title}
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          {report.target === "seller" ? "Seller" : "Buyer"}
                          {report.subject?.country || report.country
                            ? ` · ${report.subject?.country || report.country}`
                            : ""}{" "}
                          · {item.invoice_reference || "Invoice pending"}
                        </p>
                        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted">
                          {report.status === "failed"
                            ? report.error ||
                              "Research could not be completed. Saved sources are available."
                            : report.summary ||
                              "The agent’s findings will appear as research progresses."}
                        </p>
                        {report.status === "complete" && report.assessment && (
                          <p className="mt-2 text-xs font-semibold text-ink">
                            {researchOutcomes[report.assessment]}
                          </p>
                        )}
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-subtle">
                          <span>
                            {report.search_count} searches · {report.source_count} sources
                          </span>
                          <time dateTime={item.updated_at} title={dateTime(item.updated_at)}>
                            {relativeTime(item.updated_at)}
                          </time>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {list.hasNextPage && (
                <div className="p-3">
                  <Button
                    variant="secondary"
                    className="w-full"
                    loading={list.isFetchingNextPage}
                    onClick={() => list.fetchNextPage()}
                  >
                    Load more cases
                  </Button>
                </div>
              )}
            </div>
          </Card>
          <ResearchDetail key={activeId} id={activeId} />
        </div>
      ) : null}
    </div>
  );
}
