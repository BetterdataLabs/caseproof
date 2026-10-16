"use client";

import { Building2, CheckCircle2, CircleAlert, FileUp } from "lucide-react";
import { use, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { useCaseDetail } from "@/lib/use-case";
import { ActivityFeed } from "@/components/case/activity";
import { Checklist } from "@/components/case/checklist";
import { DecisionPanel } from "@/components/case/decision-panel";
import { DocumentViewer } from "@/components/case/document-viewer";
import { Exchange } from "@/components/case/exchange";
import { CaseHeader } from "@/components/case/header";
import { SimulatorDrawer } from "@/components/case/simulator";
import { DocumentIntakeForm } from "@/components/case/document-intake";
import { DocumentChecksPanel } from "@/components/case/document-checks";
import { CreditResearchPanel } from "@/components/case/credit-research";
import { VendorContactPanel } from "@/components/case/vendor-contact";
import { HistoryPanel, SummaryPanel } from "@/components/case/summary";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  Skeleton,
  TabPanel,
  Tabs,
} from "@/components/ui/primitives";
import { TASK_KIND } from "@/components/ui/status";

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const q = useCaseDetail(id);
  const [tab, setTab] = useState("activity");
  const [source, setSource] = useState<string | null>(null);
  const [simulator, setSimulator] = useState(false);
  const [intake, setIntake] = useState(false);
  const taskRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const detail = q.data;

  const openTasks = useMemo(
    () => detail?.tasks.filter((t) => ["pending", "claimed"].includes(t.state)) ?? [],
    [detail],
  );
  const decided = useMemo(() => detail?.tasks.filter((t) => t.state === "decided") ?? [], [detail]);

  function showSource(label: string) {
    setSource(label);
    if (window.matchMedia("(max-width: 1279px)").matches)
      viewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (q.error && !detail) {
    const notFound = q.error instanceof ApiError && q.error.status === 404;
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        {notFound ? (
          <EmptyState icon={<CircleAlert className="size-5" />} title="Case not found">
            The case does not exist or belongs to another organisation.
          </EmptyState>
        ) : (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        )}
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="mx-auto max-w-[1440px] space-y-4 px-4 py-8 sm:px-6 lg:px-8">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-20 w-full" />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <Skeleton className="h-[520px]" />
          <Skeleton className="h-[520px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-6 sm:px-6 lg:px-8">
      <CaseHeader
        detail={detail}
        onOpenTask={() => taskRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
      />
      <VendorContactPanel detail={detail} />
      {detail.permissions.add_input && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-3">
          <p className="text-sm text-muted">
            Have new evidence or a customer reply? Add it here to continue the review.
          </p>
          <Button
            variant="secondary"
            icon={<FileUp className="size-4" />}
            onClick={() => setIntake(true)}
          >
            Add documents or reply
          </Button>
        </div>
      )}
      <Dialog
        open={intake}
        onOpenChange={setIntake}
        title="Add documents or reply"
        description="Upload a correction, a delivery receipt, or a message from the seller or buyer."
        wide
      >
        <DocumentIntakeForm detail={detail} onComplete={() => setIntake(false)} />
      </Dialog>

      {q.error && (
        <div className="mt-4">
          <ErrorState
            compact
            error={
              new Error(
                `Connection problem — showing the last saved view from ${relativeTime(detail.case.updated_at)}.`,
              )
            }
            onRetry={() => q.refetch()}
          />
        </div>
      )}

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6 xl:grid-cols-[minmax(0,1fr)_440px]">
        <div className="min-w-0 space-y-6">
          {openTasks.length > 0 && (
            <div ref={taskRef} className="scroll-mt-6 space-y-4">
              {openTasks.map((t) => (
                <DecisionPanel key={t.id} detail={detail} task={t} onSource={showSource} />
              ))}
            </div>
          )}

          <Checklist detail={detail} onSource={showSource} />
          <DocumentChecksPanel detail={detail} onSource={showSource} />
          <CreditResearchPanel detail={detail} />

          {detail.blockers.some((b) => b.kind !== "check") &&
            detail.case.lifecycle !== "complete" && (
              <Card className="px-5 py-4">
                <p className="text-[13px] font-semibold text-ink">Also preventing completion</p>
                <ul className="mt-2 space-y-1.5">
                  {detail.blockers
                    .filter((b) => b.kind !== "check")
                    .map((b, i) => (
                      <li key={i} className="flex gap-2 text-[13px] text-muted">
                        <span
                          className="mt-1.5 size-1.5 shrink-0 rounded-full bg-amber-600"
                          aria-hidden
                        />
                        <span>{b.detail}</span>
                      </li>
                    ))}
                </ul>
              </Card>
            )}

          <Card className="px-5 pb-2 pt-1">
            <Tabs
              value={tab}
              onValueChange={setTab}
              tabs={[
                { value: "activity", label: "Activity" },
                {
                  value: "exchange",
                  label: "Requests & replies",
                  count:
                    detail.requests.filter((r) => r.state !== "draft").length +
                    detail.replies.length,
                },
                { value: "decisions", label: "Decisions", count: decided.length },
                { value: "summary", label: "Review summary", count: detail.exports.length },
                { value: "history", label: "History" },
              ]}
            >
              <TabPanel value="activity">
                <ActivityFeed detail={detail} />
              </TabPanel>
              <TabPanel value="exchange">
                <Exchange detail={detail} onSource={showSource} />
              </TabPanel>
              <TabPanel value="decisions">
                {decided.length === 0 && detail.claims.length === 0 ? (
                  <EmptyState
                    icon={<CheckCircle2 className="size-5" />}
                    title="No human decisions yet"
                  >
                    Routine progress needs no approval. A person is asked only for disputed
                    information, free text or decisions outside the agent&apos;s authority.
                  </EmptyState>
                ) : (
                  <ul className="space-y-3 py-4">
                    {detail.claims.map((c) => (
                      <li key={c.id} className="rounded-xl border border-line bg-[#fafbfa] p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            tone={
                              c.status === "retained"
                                ? "amber"
                                : c.status === "satisfied"
                                  ? "teal"
                                  : "neutral"
                            }
                          >
                            Dispute {c.status}
                          </Badge>
                          <span className="text-[13px] font-semibold text-ink">{c.statement}</span>
                        </div>
                        <p className="mt-1 text-[12.5px] text-muted">
                          Conditions: corrected {String(c.conditions.receipt_number)} replacing v
                          {String(c.conditions.disputed_version)} must state{" "}
                          {String(c.conditions.claimed_quantity)} for{" "}
                          {String(c.conditions.delivery_ref)}; remaining quantity needs distinct
                          receipts. Source {c.source}.
                        </p>
                      </li>
                    ))}
                    {decided.map((t) => {
                      const kind = TASK_KIND[t.kind] ?? TASK_KIND.evidence_problem;
                      const Icon = kind.icon;
                      return (
                        <li key={t.id} className="rounded-xl border border-line p-4">
                          <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
                            <Icon className="size-4 text-teal-700" aria-hidden /> {kind.label} ·{" "}
                            {t.title}
                          </div>
                          <p className="mt-2 text-[14px] font-semibold text-ink">
                            {t.decision?.label}
                          </p>
                          <p className="mt-0.5 text-[13px] text-muted">“{t.decision?.reason}”</p>
                          {t.decision?.conditions && "interpretation" in t.decision.conditions && (
                            <p className="mt-1 text-[13px] text-ink">
                              Interpretation: {String(t.decision.conditions.interpretation)}
                            </p>
                          )}
                          <p className="mt-1.5 text-[11.5px] text-subtle">
                            {t.decision?.actor} · {relativeTime(t.decision?.created_at)} · covers{" "}
                            {t.source_labels.join(", ") || "no sources"}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </TabPanel>
              <TabPanel value="summary">
                <SummaryPanel detail={detail} />
              </TabPanel>
              <TabPanel value="history">
                <HistoryPanel detail={detail} />
              </TabPanel>
            </Tabs>
          </Card>
        </div>

        <div ref={viewerRef} className="scroll-mt-4 xl:sticky xl:top-4">
          <DocumentViewer detail={detail} selected={source} onSelect={setSource} />
        </div>
      </div>

      {detail.permissions.simulate && (
        <>
          <button
            onClick={() => setSimulator(true)}
            className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full border-2 border-dashed border-amber-600 bg-amber-100 px-4 py-3 text-[13.5px] font-semibold text-amber-700 shadow-[var(--shadow-pop)] hover:bg-amber-200"
          >
            <Building2 className="size-4" aria-hidden />
            Customer exchange <span className="hidden sm:inline">(demo)</span>
          </button>
          <SimulatorDrawer detail={detail} open={simulator} onOpenChange={setSimulator} />
        </>
      )}
    </div>
  );
}
