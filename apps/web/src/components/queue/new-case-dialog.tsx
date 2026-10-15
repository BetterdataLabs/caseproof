"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Eye, Hand } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, command, getJson, newKey } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Scenario } from "@/lib/types";
import {
  Badge,
  Button,
  Callout,
  Dialog,
  Field,
  Select,
  Skeleton,
  cx,
} from "@/components/ui/primitives";
import { DocumentIntakeForm } from "@/components/case/document-intake";
import { ScenarioGuide } from "@/components/case/scenario-guide";
import { VendorContactField } from "@/components/case/vendor-contact";

const MODES = [
  {
    value: "autonomous",
    label: "Autonomous sandbox",
    icon: Bot,
    text: "The agent requests, waits and completes supported cases. Exceptions come to a person.",
  },
  {
    value: "shadow",
    label: "Shadow",
    icon: Eye,
    text: "The agent records proposed actions only. No requests are sent and nothing is completed.",
  },
  {
    value: "off",
    label: "Off (manual)",
    icon: Hand,
    text: "No agent runs. Reviewers use the manual fallback with the same rules.",
  },
];

export function NewCaseDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const session = useSession();
  const [scenario, setScenario] = useState("two-gaps");
  const [source, setSource] = useState("upload");
  const [mode, setMode] = useState("autonomous");
  const [assignee, setAssignee] = useState(session.user.id);
  const [vendorContact, setVendorContact] = useState<string | null>(null);
  const key = useRef<string | null>(null);

  const catalog = useQuery({
    queryKey: ["scenarios"],
    queryFn: ({ signal }) =>
      getJson<{ notice: string; scenarios: Scenario[] }>("/v1/catalog/scenarios", signal),
    enabled: open,
  });
  const members = useQuery({
    queryKey: ["members"],
    queryFn: ({ signal }) =>
      getJson<{ members: { id: string; name: string; roles: string[] }[] }>("/v1/members", signal),
    enabled: open,
  });

  const create = useMutation({
    mutationFn: () => {
      const vendors =
        members.data?.members.filter((m) => m.roles.length === 1 && m.roles.includes("vendor")) ??
        [];
      const contact =
        vendorContact ?? (session.demo_mode && vendors.length === 1 ? vendors[0].id : "");
      key.current = key.current ?? newKey("case"); // reused if the user retries the same intent
      return command<{ id: string; reference: string }>(
        "/v1/cases",
        {
          scenario_key: scenario,
          automation_mode: mode,
          assigned_to: assignee,
          vendor_contact_id: contact || null,
        },
        key.current,
      );
    },
    onSuccess: (res) => {
      key.current = null;
      toast.success(`${res.reference} created`, {
        description: mode === "off" ? "Manual review." : "The agent is inspecting the documents.",
      });
      qc.invalidateQueries({ queryKey: ["cases"] });
      onOpenChange(false);
      router.push(`/cases/${res.id}`);
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      wide
      title="New document review"
      description="Start with your own documents or choose a ready-made demo."
      footer={
        source === "demo" ? (
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={() => create.mutate()} loading={create.isPending}>
              Create case
            </Button>
          </>
        ) : undefined
      }
    >
      <div className="mb-5 flex gap-2" role="group" aria-label="Case source">
        <Button
          variant={source === "upload" ? "primary" : "secondary"}
          onClick={() => setSource("upload")}
        >
          Your documents
        </Button>
        <Button
          variant={source === "demo" ? "primary" : "secondary"}
          onClick={() => setSource("demo")}
        >
          Demo scenarios
        </Button>
      </div>
      {source === "upload" ? (
        <DocumentIntakeForm
          onComplete={(res) => {
            onOpenChange(false);
            router.push(`/cases/${res.id}`);
          }}
        />
      ) : (
        <div className="space-y-6">
          <VendorContactField
            defaultValue={vendorContact ?? undefined}
            onChange={(value) => {
              setVendorContact(value);
              key.current = null;
            }}
          />
          <fieldset>
            <legend className="mb-2 text-[13px] font-semibold text-ink">Example case</legend>
            <p className="mb-3 text-xs text-muted">
              Choose a fictional sale with prepared documents and replies. Each example demonstrates
              a different review outcome.
            </p>
            {catalog.isLoading && <Skeleton className="h-40" />}
            <div role="radiogroup" className="grid gap-2 sm:grid-cols-2">
              {catalog.data?.scenarios.map((s) => (
                <label
                  key={s.key}
                  className={cx(
                    "flex cursor-pointer flex-col rounded-xl border p-3.5 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[#956200]",
                    scenario === s.key
                      ? "border-teal-700 bg-teal-50 ring-1 ring-teal-700"
                      : "border-line hover:border-teal-300",
                  )}
                >
                  <input
                    type="radio"
                    name="scenario"
                    value={s.key}
                    checked={scenario === s.key}
                    onChange={() => setScenario(s.key)}
                    className="sr-only"
                  />
                  <span className="flex items-center justify-between gap-2">
                    <Badge tone={scenario === s.key ? "teal" : "neutral"}>{s.family}</Badge>
                    <span className="font-mono text-[11px] text-subtle">{s.invoice_reference}</span>
                  </span>
                  <span className="mt-2 text-[14px] font-semibold text-ink">{s.title}</span>
                  <span className="mt-0.5 text-[12.5px] leading-relaxed text-muted">
                    {s.description}
                  </span>
                  <span className="mt-2 text-[11.5px] text-subtle">
                    {s.seller} → {s.buyer} · {s.initial_documents} document
                    {s.initial_documents === 1 ? "" : "s"}
                  </span>
                </label>
              ))}
            </div>
            {catalog.data && <p className="mt-2 text-[12px] text-subtle">{catalog.data.notice}</p>}
          </fieldset>

          <ScenarioGuide
            steps={catalog.data?.scenarios.find((s) => s.key === scenario)?.walkthrough}
          />

          <fieldset>
            <legend className="mb-2 text-[13px] font-semibold text-ink">Automation mode</legend>
            <div role="radiogroup" className="grid gap-2 sm:grid-cols-3">
              {MODES.map((m) => {
                const Icon = m.icon;
                return (
                  <label
                    key={m.value}
                    className={cx(
                      "flex cursor-pointer flex-col rounded-xl border p-3 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[#956200]",
                      mode === m.value
                        ? "border-teal-700 bg-teal-50 ring-1 ring-teal-700"
                        : "border-line hover:border-teal-300",
                    )}
                  >
                    <input
                      type="radio"
                      name="mode"
                      value={m.value}
                      checked={mode === m.value}
                      onChange={() => setMode(m.value)}
                      className="sr-only"
                    />
                    <span className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
                      <Icon className="size-4 text-teal-700" aria-hidden /> {m.label}
                    </span>
                    <span className="mt-1 text-[12px] leading-relaxed text-muted">{m.text}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <Field
            label="Assigned reviewer"
            htmlFor="assignee"
            hint="The bank staff member responsible for questions that need a human decision. For a solo demo, keep yourself selected."
          >
            <Select id="assignee" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              {(members.data?.members ?? [])
                .filter((m) => m.roles.includes("reviewer") || m.roles.includes("supervisor"))
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              {!members.data && <option value={session.user.id}>{session.user.name}</option>}
            </Select>
          </Field>

          {create.error && (
            <Callout tone="red" title="The case was not created">
              {create.error instanceof ApiError ? create.error.message : "Please try again."} Your
              selection is kept; retrying uses the same request key.
            </Callout>
          )}
        </div>
      )}
    </Dialog>
  );
}
