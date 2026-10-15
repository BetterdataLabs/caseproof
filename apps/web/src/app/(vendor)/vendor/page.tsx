"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileUp, Inbox, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { getJson } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { vendorTone, type VendorCase } from "@/lib/vendor";
import { SubmissionForm } from "@/components/vendor/submission-form";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
} from "@/components/ui/primitives";

export default function VendorPage() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const list = useQuery({
    queryKey: ["vendor", "cases"],
    queryFn: ({ signal }) => getJson<{ items: VendorCase[] }>("/v1/vendor/cases", signal),
    refetchInterval: 5000,
  });
  const items = (list.data?.items ?? []).filter((item) =>
    `${item.reference} ${item.title} ${item.invoice} ${item.buyer}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const replies = list.data?.items.filter((item) => item.status === "reply_needed").length ?? 0;
  return (
    <>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-teal-700">
            Vendor workspace
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">
            Requests &amp; submissions
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
            Send documents to the bank and keep every request and reply in one place.
          </p>
        </div>
        <Button onClick={() => setCreating(true)} icon={<FileUp className="size-4" />}>
          New submission
        </Button>
      </div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-paper px-5 py-4">
        <p className="text-sm text-muted">
          {replies ? (
            <>
              <strong className="text-ink">
                {replies} case{replies === 1 ? " needs" : "s need"} a reply.
              </strong>{" "}
              Open the conversation to see what is missing.
            </>
          ) : (
            "See your submissions and cases the bank has shared with you as the vendor contact."
          )}
        </p>
        <a
          className="text-xs font-semibold text-teal-700 underline underline-offset-4"
          href="/sample-documents/scenarios/index.html"
          target="_blank"
          rel="noreferrer"
        >
          Need sample documents?
        </a>
      </div>
      {list.isLoading && <Skeleton className="h-52" />}
      {list.error && <ErrorState error={list.error} onRetry={() => list.refetch()} />}
      {!!list.data?.items.length && (
        <div className="relative mb-4 max-w-md">
          <Search className="absolute left-3 top-3 size-4 text-subtle" aria-hidden />
          <Input
            aria-label="Find a submission"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search invoice, buyer or reference"
            className="pl-9"
          />
        </div>
      )}
      {list.data && items.length === 0 ? (
        <div className="rounded-2xl border border-line bg-paper p-8">
          <EmptyState
            icon={<Inbox className="size-6" />}
            title={search ? "No matching cases" : "Your cases will appear here"}
          >
            {search
              ? "Try another invoice number or buyer name."
              : "Submit an invoice, or ask the bank reviewer to select you as the vendor contact on an existing case. Its document requests will appear here."}
          </EmptyState>
          {!search && (
            <div className="mt-4 text-center">
              <Button variant="secondary" onClick={() => setCreating(true)}>
                Submit an invoice
              </Button>
            </div>
          )}
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/vendor/${item.id}`}
                className="group flex items-center gap-4 rounded-2xl border border-line bg-paper p-5 shadow-[var(--shadow-card)] transition-colors hover:border-teal-300"
              >
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700">
                  <Inbox className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-subtle">{item.reference}</span>
                    <Badge tone={vendorTone[item.status]}>{item.status_label}</Badge>
                  </div>
                  <h2 className="mt-2 break-words text-base font-semibold text-ink">
                    {item.invoice ? `${item.seller} · ${item.invoice}` : item.title}
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    {item.invoice ? `Buyer: ${item.buyer}` : "Reading your invoice details"}
                  </p>
                  <p className="mt-2 text-xs text-subtle">
                    Updated {relativeTime(item.updated_at)}
                  </p>
                </div>
                <ArrowRight
                  className="size-5 shrink-0 text-subtle group-hover:text-teal-700"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Dialog
        open={creating}
        onOpenChange={setCreating}
        title="New submission"
        description="Start a document review with your bank."
        wide
      >
        <SubmissionForm
          onComplete={(result) => {
            setCreating(false);
            router.push(`/vendor/${result.id}`);
          }}
        />
      </Dialog>
    </>
  );
}
