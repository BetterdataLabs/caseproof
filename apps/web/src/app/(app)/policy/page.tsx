"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookCheck,
  Check,
  ChevronDown,
  Clock3,
  FileText,
  History,
  ListChecks,
  LockKeyhole,
  Mail,
  Pencil,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { ApiError, command, getJson, newKey } from "@/lib/api";
import { dateTime, humanize } from "@/lib/format";
import { PageHeader } from "@/components/shell/app-shell";
import {
  Badge,
  Button,
  Callout,
  Dialog,
  ErrorState,
  Field,
  Input,
  Select,
  Skeleton,
  Textarea,
} from "@/components/ui/primitives";

import { PolicyRules, type PolicyRule } from "@/components/case/policy-rules";

interface PolicyDef {
  key: string;
  version: number;
  name: string;
  notice: string;
  supported_contract: string;
  requirements: PolicyRule[];
  source_roles: Record<
    string,
    { label: string; permitted_issuer?: string; requires_human_disposition?: boolean }
  >;
  replacement_rules: Record<
    string,
    { requires_explicit_supersession: boolean; same_issuer: boolean; may_change: string[] }
  >;
  templates: Record<string, { label: string; text: string }>;
  task_decisions: Record<string, string[]>;
  timers: Record<string, number | string>;
  limits: Record<string, number | string>;
  authority: { agent_may: string[]; agent_may_not: string[] };
}
interface Version {
  id: string;
  version: number;
  status: string;
  published_at: string;
  definition: PolicyDef;
}
interface Setting {
  key: string;
  section: "timers" | "limits";
  label: string;
  unit: string;
  min: number;
  max: number;
  hint: string;
  step: string;
}
interface PolicyData {
  policies: Version[];
  can_publish: boolean;
  editor: {
    max_requirements: number;
    settings: Setting[];
    replacement_fields: Record<string, string[]>;
    task_decisions: Record<string, string[]>;
  };
}
interface Change {
  label: string;
  before: string;
  after: string;
}
const DECISIONS: Record<string, string> = {
  retain_dispute_request_evidence: "Retain dispute and request evidence",
  record_interpretation: "Record an interpretation",
  mark_irrelevant: "Mark message irrelevant",
  keep_on_hold: "Keep the case on hold",
  authorise_request: "Authorise a request",
  authorise_extra_round: "Allow another request round",
  resume_automation: "Resume automation",
  grant_extension: "Extend the allowance",
};
const TASKS: Record<string, string> = {
  dispute: "Disputed evidence",
  no_response: "No reply",
  message_review: "Written message",
  service_failure: "Service failure",
  budget_exhausted: "Allowance reached",
  evidence_problem: "Evidence problem",
};

function changesBetween(before: PolicyDef, after: PolicyDef, settings: Setting[]): Change[] {
  const changes: Change[] = [];
  const add = (label: string, a: unknown, b: unknown) => {
    if (String(a) !== String(b)) changes.push({ label, before: String(a), after: String(b) });
  };
  add("Policy name", before.name, after.name);
  add("Description", before.notice, after.notice);
  const keys = new Set([...before.requirements, ...after.requirements].map((r) => r.key));
  keys.forEach((key) => {
    const a = before.requirements.find((r) => r.key === key);
    const b = after.requirements.find((r) => r.key === key);
    add(
      `Rule · ${b?.label || a?.label || "New rule"}`,
      a ? `${a.label}: ${a.description} (${a.depends_on_roles.join(", ")})` : "Not included",
      b ? `${b.label}: ${b.description} (${b.depends_on_roles.join(", ")})` : "Removed",
    );
  });
  settings.forEach((s) =>
    add(`${s.label} (${s.unit})`, before[s.section][s.key], after[s.section][s.key]),
  );
  Object.entries(before.templates).forEach(([key, t]) => {
    add(`${t.label} · title`, t.label, after.templates[key].label);
    add(`${t.label} · wording`, t.text, after.templates[key].text);
  });
  Object.entries(before.replacement_rules).forEach(([key, rule]) =>
    add(
      `${humanize(key)} · permitted corrections`,
      rule.may_change.map(humanize).join(", ") || "None",
      after.replacement_rules[key].may_change.map(humanize).join(", ") || "None",
    ),
  );
  Object.entries(before.task_decisions).forEach(([key, values]) =>
    add(
      `${TASKS[key]} · decisions`,
      values.map((v) => DECISIONS[v]).join(", "),
      after.task_decisions[key].map((v) => DECISIONS[v]).join(", "),
    ),
  );
  return changes;
}

function Section({
  title,
  summary,
  icon,
  children,
  open = false,
  wide = false,
  fixed = false,
}: {
  title: string;
  summary: string;
  icon: ReactNode;
  children: ReactNode;
  open?: boolean;
  wide?: boolean;
  fixed?: boolean;
}) {
  return (
    <details
      open={open}
      className={`group self-start overflow-hidden rounded-2xl border border-line bg-white shadow-[var(--shadow-card)] ${wide ? "lg:col-span-2" : ""}`}
    >
      <summary className="flex cursor-pointer list-none items-center gap-3 p-4 transition-colors hover:bg-teal-50/40 focus-visible:outline-2 focus-visible:outline-teal-700 sm:p-5 [&::-webkit-details-marker]:hidden">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700">
          {icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-ink">{title}</span>
          <span className="mt-0.5 block text-xs leading-relaxed text-muted">{summary}</span>
        </span>
        {fixed && <Badge icon={<LockKeyhole className="size-3" />}>Built-in</Badge>}
        <ChevronDown
          className="size-4 shrink-0 text-subtle transition-transform group-open:rotate-180"
          aria-hidden
        />
      </summary>
      <div className="space-y-4 border-t border-line-soft p-4 sm:p-5">{children}</div>
    </details>
  );
}

export default function PolicyPage() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["policies"],
    queryFn: ({ signal }) => getJson<PolicyData>("/v1/policies", signal),
  });
  const [selected, setSelected] = useState("");
  const [editing, setEditing] = useState<{ base: Version; definition: PolicyDef } | null>(null);
  const [review, setReview] = useState(false);
  const [reason, setReason] = useState("");
  const intent = useRef<{
    key: string;
    body: { base_policy_id: string; definition: PolicyDef; reason: string };
  } | null>(null);
  const publish = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error("Open a policy draft first.");
      intent.current ??= {
        key: newKey("policy"),
        body: { base_policy_id: editing.base.id, definition: editing.definition, reason },
      };
      return command<{ id: string; version: number }>(
        "/v1/policies/publish",
        intent.current.body,
        intent.current.key,
      );
    },
    onSuccess: (result) => {
      intent.current = null;
      setEditing(null);
      setReview(false);
      setReason("");
      setSelected(result.id);
      qc.invalidateQueries({ queryKey: ["policies"] });
      toast.success(`Policy v${result.version} published`, {
        description: "New cases will use this version. Existing cases keep their policy.",
      });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status < 500) {
        intent.current = null;
        qc.invalidateQueries({ queryKey: ["policies"] });
      }
    },
  });
  const latest = q.data?.policies.find((p) => p.status === "published");
  const version = editing?.base ?? q.data?.policies.find((p) => p.id === selected) ?? latest;
  const d = editing?.definition ?? version?.definition;
  const schema = q.data?.editor;
  const changes =
    editing && schema
      ? changesBetween(editing.base.definition, editing.definition, schema.settings)
      : [];
  const stale = !!editing && !!latest && editing.base.id !== latest.id;
  function edit(update: (draft: PolicyDef) => void) {
    intent.current = null;
    publish.reset();
    setEditing((current) => {
      if (!current) return current;
      const next = structuredClone(current.definition);
      update(next);
      return { ...current, definition: next };
    });
  }

  if (q.error && !q.data)
    return (
      <div className="p-8">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  return (
    <div className="mx-auto max-w-[1160px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        title="Policy"
        description="Set how document reviews work. Publish a new version for new cases; existing cases keep their assigned version."
        eyebrow={
          <Badge tone={editing ? "amber" : "teal"} icon={<BookCheck className="size-3" />}>
            {editing
              ? `Editing draft for v${(version?.version ?? 1) + 1}`
              : version
                ? `Published v${version.version}`
                : "Review rules"}
          </Badge>
        }
        actions={
          editing ? (
            <>
              <Button
                variant="secondary"
                disabled={publish.isPending}
                onClick={() => {
                  setEditing(null);
                  setReview(false);
                  setReason("");
                  intent.current = null;
                  publish.reset();
                }}
              >
                Discard changes
              </Button>
              <Button
                type="submit"
                form="policy-editor"
                disabled={!changes.length || stale || publish.isPending}
                icon={<Check className="size-4" />}
              >
                Review {changes.length || ""} {changes.length === 1 ? "change" : "changes"}
              </Button>
            </>
          ) : (
            q.data?.can_publish &&
            version && (
              <Button
                icon={<Pencil className="size-4" />}
                onClick={() => {
                  if (latest) {
                    setEditing({
                      base: structuredClone(latest),
                      definition: structuredClone(latest.definition),
                    });
                    setReason("");
                    intent.current = null;
                    publish.reset();
                  }
                }}
              >
                {version.id === latest?.id ? "Edit policy" : "Edit latest version"}
              </Button>
            )
          )
        }
      />
      {!d || !version || !schema ? (
        <Skeleton className="h-80" />
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-3">
            <div className="flex min-w-0 items-center gap-2 text-xs text-muted">
              <History className="size-4 shrink-0" />
              <span>
                {editing
                  ? "Published rules stay in place while you edit."
                  : `Published ${dateTime(version.published_at)}`}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <label htmlFor="policy-version" className="shrink-0 font-semibold text-ink">
                Version history
              </label>
              <Select
                id="policy-version"
                value={version.id}
                disabled={!!editing}
                onChange={(e) => setSelected(e.target.value)}
                className="h-8 max-w-[190px] text-xs"
              >
                {q.data?.policies.map((p) => (
                  <option key={p.id} value={p.id}>
                    Version {p.version}
                    {p.id === latest?.id ? " · Current" : " · Previous"}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          {stale && (
            <Callout tone="amber" title="A newer version has been published" className="mb-5">
              Your draft is kept here for comparison. Copy any changes you need, discard this draft,
              then edit the latest version.
            </Callout>
          )}
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["First reminder", `${d.timers.reminder_after_hours} h`],
              ["After reminder", `${d.timers.stop_after_reminder_hours} h to escalate`],
              ["Time per run", `${d.limits.active_seconds_per_invocation} sec`],
              ["AI budget / case", `USD ${Number(d.limits.case_budget_usd).toFixed(2)}`],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-teal-100 bg-teal-50/70 px-4 py-3"
              >
                <p className="text-[11px] text-muted">{label}</p>
                <p className="mt-1 text-sm font-semibold text-teal-800 tabular">{value}</p>
              </div>
            ))}
          </div>
          <form
            id="policy-editor"
            onSubmit={(e) => {
              e.preventDefault();
              setReview(true);
            }}
            onInvalidCapture={(e) => {
              let parent: HTMLElement | null = e.target as HTMLElement;
              while (parent) {
                if (parent instanceof HTMLDetailsElement) parent.open = true;
                parent = parent.parentElement;
              }
            }}
          >
            <fieldset
              disabled={publish.isPending}
              className="grid items-start gap-4 lg:grid-cols-2 disabled:opacity-60"
            >
              <Section
                title="Overview and checklist"
                summary={`${d.requirements.length} rules · core checks and published review criteria`}
                icon={<ListChecks className="size-4" />}
                open
                wide
              >
                {editing ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field
                      label="Policy name"
                      htmlFor="policy-name"
                      hint="Shown to reviewers and in the review summary."
                    >
                      <Input
                        id="policy-name"
                        value={d.name}
                        required
                        maxLength={200}
                        onChange={(e) =>
                          edit((n) => {
                            n.name = e.target.value;
                          })
                        }
                      />
                    </Field>
                    <Field
                      label="Short description"
                      htmlFor="policy-notice"
                      hint="Describe the purpose and scope of this review policy."
                    >
                      <Input
                        id="policy-notice"
                        value={d.notice}
                        required
                        maxLength={500}
                        onChange={(e) =>
                          edit((n) => {
                            n.notice = e.target.value;
                          })
                        }
                      />
                    </Field>
                  </div>
                ) : (
                  <div>
                    <p className="text-base font-semibold text-ink">{d.name}</p>
                    <p className="mt-1 text-xs text-muted">{d.notice}</p>
                  </div>
                )}
                <PolicyRules
                  rules={d.requirements}
                  editing={!!editing}
                  maximum={schema.max_requirements}
                  onChange={(rules) =>
                    edit((n) => {
                      n.requirements = rules;
                    })
                  }
                />
                <p className="text-xs leading-relaxed text-muted">
                  <span className="font-semibold text-ink">Supported documents: </span>English text
                  PDFs, one goods line in SGD, whole-number quantities, no tax or extra charges.
                  Receipts must acknowledge receipt by the buyer. Additional criteria are assessed
                  by Gemini against document text; uncertain findings require a reviewer.
                </p>
              </Section>
              <Section
                title="Timers and allowances"
                summary={`${d.limits.automatic_wakeups_per_case} agent runs · ${d.limits.request_rounds} request rounds · ${d.limits.model_calls_per_invocation} AI calls per run`}
                icon={<Clock3 className="size-4" />}
              >
                {editing ? (
                  <div className="grid gap-x-4 gap-y-5 sm:grid-cols-2">
                    {schema.settings.map((s) => (
                      <Field
                        key={s.key}
                        label={`${s.label} (${s.unit})`}
                        htmlFor={`policy-${s.key}`}
                        hint={`${s.hint} Range: ${s.min.toLocaleString()}–${s.max.toLocaleString()}.`}
                      >
                        <Input
                          id={`policy-${s.key}`}
                          type="number"
                          required
                          min={s.min}
                          max={s.max}
                          step={s.step}
                          value={d[s.section][s.key]}
                          onChange={(e) =>
                            edit((n) => {
                              n[s.section][s.key] = e.target.value;
                            })
                          }
                        />
                      </Field>
                    ))}
                  </div>
                ) : (
                  <dl className="divide-y divide-line-soft">
                    {schema.settings.map((s) => (
                      <div
                        key={s.key}
                        className="flex items-start justify-between gap-4 py-2 first:pt-0"
                      >
                        <dt className="text-xs text-muted" title={s.hint}>
                          {s.label}
                        </dt>
                        <dd className="shrink-0 text-xs font-semibold text-ink tabular">
                          {Number(d[s.section][s.key]).toLocaleString()} {s.unit}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
                <p className="flex items-start gap-2 border-t border-line-soft pt-3 text-xs leading-relaxed text-muted">
                  <LockKeyhole className="mt-0.5 size-3.5 shrink-0" />
                  One reminder per request is built in. The organisation’s daily AI budget (USD{" "}
                  {Number(d.limits.environment_daily_budget_usd).toFixed(2)}) is managed in server
                  settings.
                </p>
              </Section>
              <Section
                title="Request wording"
                summary={`${Object.keys(d.templates).length} approved templates · filled with document facts`}
                icon={<Mail className="size-4" />}
              >
                <p className="text-xs text-muted">
                  Choose a template to view or edit. Words in braces are filled automatically from
                  the case.
                </p>
                <div className="divide-y divide-line-soft">
                  {Object.entries(d.templates).map(([key, t]) => (
                    <details key={key} className="py-2 first:pt-0">
                      <summary className="cursor-pointer text-[13px] font-semibold text-ink">
                        {t.label}
                      </summary>
                      <div className="mt-3 space-y-3 pb-2">
                        {editing ? (
                          <>
                            <Field
                              label="Template title"
                              htmlFor={`template-${key}-label`}
                              hint="A short name that helps reviewers identify this request."
                            >
                              <Input
                                id={`template-${key}-label`}
                                value={t.label}
                                required
                                maxLength={200}
                                onChange={(e) =>
                                  edit((n) => {
                                    n.templates[key].label = e.target.value;
                                  })
                                }
                              />
                            </Field>
                            <Field
                              label="Request wording"
                              htmlFor={`template-${key}-text`}
                              hint="Keep every existing placeholder, such as {invoice_number}. You can change the wording around them."
                            >
                              <Textarea
                                id={`template-${key}-text`}
                                value={t.text}
                                required
                                maxLength={2400}
                                rows={5}
                                onChange={(e) =>
                                  edit((n) => {
                                    n.templates[key].text = e.target.value;
                                  })
                                }
                              />
                            </Field>
                          </>
                        ) : (
                          <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted">
                            {t.text}
                          </p>
                        )}
                      </div>
                    </details>
                  ))}
                </div>
              </Section>
              <Section
                title="Documents and corrections"
                summary="Who supplies evidence and which fields a correction may change"
                icon={<FileText className="size-4" />}
              >
                <div className="divide-y divide-line-soft">
                  {Object.entries(d.source_roles).map(([key, role]) => (
                    <div key={key} className="space-y-2 py-3 first:pt-0">
                      <p className="text-[13px] font-semibold text-ink">{role.label}</p>
                      <p className="text-xs leading-relaxed text-muted">
                        {role.permitted_issuer
                          ? `Supplied by ${role.permitted_issuer === "seller" ? "the seller" : "the buyer / permitted receipt issuer"}. A correction must explicitly replace the earlier version and keep the same issuer.`
                          : role.requires_human_disposition
                            ? "Each written message needs a recorded human decision."
                            : "Structured updates report progress; they do not prove receipt of goods."}
                      </p>
                      {d.replacement_rules[key] &&
                        (editing ? (
                          <fieldset>
                            <legend className="mb-2 text-xs font-medium text-ink">
                              Fields a correction may change
                            </legend>
                            <div className="flex flex-wrap gap-x-4 gap-y-2">
                              {schema.replacement_fields[key].map((field) => (
                                <label
                                  key={field}
                                  className="flex items-center gap-2 text-xs text-muted"
                                >
                                  <input
                                    type="checkbox"
                                    className="accent-teal-700"
                                    checked={d.replacement_rules[key].may_change.includes(field)}
                                    onChange={(e) =>
                                      edit((n) => {
                                        n.replacement_rules[key].may_change =
                                          schema.replacement_fields[key].filter((f) =>
                                            f === field
                                              ? e.target.checked
                                              : n.replacement_rules[key].may_change.includes(f),
                                          );
                                      })
                                    }
                                  />
                                  {field === "basis"
                                    ? "Quantity basis (cumulative or per delivery)"
                                    : humanize(field)}
                                </label>
                              ))}
                            </div>
                          </fieldset>
                        ) : (
                          <div className="flex flex-wrap gap-1.5">
                            {d.replacement_rules[key].may_change.length ? (
                              d.replacement_rules[key].may_change.map((f) => (
                                <Badge key={f}>{humanize(f)}</Badge>
                              ))
                            ) : (
                              <Badge>No fields may change automatically</Badge>
                            )}
                          </div>
                        ))}
                    </div>
                  ))}
                </div>
              </Section>
              <Section
                title="Reviewer decisions"
                summary="Choose which supported decisions are available for each task"
                icon={<UserRound className="size-4" />}
              >
                <p className="text-xs text-muted">
                  Keeping a case on hold always remains available. Other choices can be enabled or
                  disabled for new tasks under this policy.
                </p>
                <div className="divide-y divide-line-soft">
                  {Object.entries(d.task_decisions).map(([kind, choices]) => (
                    <div key={kind} className="py-3 first:pt-0">
                      <p className="mb-2 text-[13px] font-semibold text-ink">{TASKS[kind]}</p>
                      {editing ? (
                        <div className="grid gap-2">
                          {schema.task_decisions[kind].map((choice) => (
                            <label
                              key={choice}
                              className="flex items-center gap-2 text-xs text-muted"
                            >
                              <input
                                type="checkbox"
                                className="accent-teal-700"
                                disabled={choice === "keep_on_hold"}
                                checked={choices.includes(choice)}
                                onChange={(e) =>
                                  edit((n) => {
                                    n.task_decisions[kind] = schema.task_decisions[kind].filter(
                                      (v) =>
                                        v === choice
                                          ? e.target.checked
                                          : n.task_decisions[kind].includes(v),
                                    );
                                  })
                                }
                              />
                              {DECISIONS[choice]}
                              {choice === "keep_on_hold" && (
                                <LockKeyhole className="size-3 text-subtle" />
                              )}
                            </label>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs leading-relaxed text-muted">
                          {choices.map((v) => DECISIONS[v]).join(" · ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
              <Section
                title="Agent authority"
                summary="Supported actions and the boundaries of this application"
                icon={<ShieldCheck className="size-4" />}
                fixed
                wide
              >
                <div className="grid gap-5 sm:grid-cols-2">
                  <div>
                    <p className="mb-2 text-xs font-semibold text-ink">Available actions</p>
                    <div className="flex flex-wrap gap-1.5">
                      {d.authority.agent_may.map((action) => (
                        <Badge key={action} tone="teal">
                          {humanize(action)}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold text-ink">
                      Outside the agent’s authority
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {d.authority.agent_may_not.map((action) => (
                        <Badge key={action}>{humanize(action)}</Badge>
                      ))}
                    </div>
                  </div>
                </div>
                <p className="text-xs text-muted">
                  Changing these capabilities requires an application change. Editing this policy
                  cannot add lending approval, payments or access to another case.
                </p>
              </Section>
            </fieldset>
          </form>
          {!q.data?.can_publish && (
            <p className="mt-4 text-xs text-muted">
              Supervisors can edit and publish policy versions. Your role can view them.
            </p>
          )}
          <Dialog
            open={review}
            onOpenChange={(open) => !publish.isPending && setReview(open)}
            title={`Publish policy v${version.version + 1}`}
            description="Review the changes below. New cases will use this version; existing cases keep their current policy."
            wide
            footer={
              <>
                <Button
                  variant="secondary"
                  disabled={publish.isPending}
                  onClick={() => setReview(false)}
                >
                  Back to editing
                </Button>
                <Button
                  type="submit"
                  form="publish-policy"
                  loading={publish.isPending}
                  disabled={stale || reason.trim().length < 5}
                >
                  Publish version
                </Button>
              </>
            }
          >
            <div className="space-y-4">
              <div className="space-y-2">
                {changes.map((change) => (
                  <details
                    key={change.label}
                    className="rounded-xl border border-line-soft bg-canvas/50 p-3"
                  >
                    <summary className="cursor-pointer text-[13px] font-semibold text-ink">
                      {change.label}
                    </summary>
                    <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                      <div>
                        <p className="mb-1 font-semibold text-muted">Current</p>
                        <p className="whitespace-pre-wrap break-words text-muted">
                          {change.before}
                        </p>
                      </div>
                      <div>
                        <p className="mb-1 font-semibold text-teal-700">New version</p>
                        <p className="whitespace-pre-wrap break-words text-ink">{change.after}</p>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
              <form
                id="publish-policy"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (reason.trim().length >= 5 && !stale) publish.mutate();
                }}
              >
                <Field
                  label="Reason for this version"
                  htmlFor="policy-reason"
                  hint="A short explanation saved with the publication, so other supervisors can understand the change."
                >
                  <Textarea
                    id="policy-reason"
                    value={reason}
                    required
                    minLength={5}
                    maxLength={1200}
                    disabled={publish.isPending}
                    onChange={(e) => {
                      setReason(e.target.value);
                      intent.current = null;
                      publish.reset();
                    }}
                    placeholder="For example: Allow longer agent runs to handle slower AI responses."
                  />
                </Field>
              </form>
              {publish.error && (
                <div role="alert">
                  <Callout tone="red" title="Policy was not published">
                    {publish.error.message} Your draft is still available.
                  </Callout>
                </div>
              )}
            </div>
          </Dialog>
        </>
      )}
    </div>
  );
}
