"use client";

import { Plus, Trash2 } from "lucide-react";
import { Badge, Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";

export interface PolicyRule {
  key: string;
  label: string;
  description: string;
  depends_on_roles: string[];
}

const CORE = new Set(["invoice_total", "delivery_receipts"]);

export function PolicyRules({
  rules,
  editing,
  maximum,
  onChange,
}: {
  rules: PolicyRule[];
  editing: boolean;
  maximum: number;
  onChange: (rules: PolicyRule[]) => void;
}) {
  const update = (key: string, changes: Partial<PolicyRule>) =>
    onChange(rules.map((r) => (r.key === key ? { ...r, ...changes } : r)));
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {rules.map((rule, i) => (
          <div
            key={rule.key}
            className="space-y-3 rounded-xl border border-line-soft bg-canvas/50 p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <Badge tone={CORE.has(rule.key) ? "neutral" : "teal"}>
                {CORE.has(rule.key) ? "Core check" : "Gemini review"}
              </Badge>
              {editing && !CORE.has(rule.key) && (
                <button
                  type="button"
                  aria-label={`Remove ${rule.label || `rule ${i + 1}`}`}
                  onClick={() => onChange(rules.filter((r) => r.key !== rule.key))}
                  className="rounded-md p-1.5 text-subtle hover:bg-red-50 hover:text-red-700"
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </div>
            {editing ? (
              <>
                <Field label={`${i + 1}. Rule title`} htmlFor={`rule-title-${rule.key}`}>
                  <Input
                    id={`rule-title-${rule.key}`}
                    value={rule.label}
                    required
                    maxLength={200}
                    placeholder="For example: Payment terms are stated"
                    onChange={(e) => update(rule.key, { label: e.target.value })}
                  />
                </Field>
                <Field
                  label="Review criteria"
                  htmlFor={`rule-criteria-${rule.key}`}
                  hint={
                    CORE.has(rule.key)
                      ? "The core calculation remains mandatory. Changes to these criteria also receive a Gemini review."
                      : "State what the document must show. Gemini checks these criteria and cites the evidence."
                  }
                >
                  <Textarea
                    id={`rule-criteria-${rule.key}`}
                    value={rule.description}
                    required
                    rows={3}
                    maxLength={2000}
                    placeholder="The invoice must state when payment is due, either as a due date or a number of days."
                    onChange={(e) => update(rule.key, { description: e.target.value })}
                  />
                </Field>
                {!CORE.has(rule.key) && (
                  <Field label="Documents to check" htmlFor={`rule-scope-${rule.key}`}>
                    <Select
                      id={`rule-scope-${rule.key}`}
                      value={rule.depends_on_roles.length > 1 ? "both" : rule.depends_on_roles[0]}
                      onChange={(e) =>
                        update(rule.key, {
                          depends_on_roles:
                            e.target.value === "both"
                              ? ["invoice", "delivery_receipt"]
                              : [e.target.value],
                        })
                      }
                    >
                      <option value="invoice">Invoice</option>
                      <option value="delivery_receipt">Delivery receipts</option>
                      <option value="both">Invoice and delivery receipts</option>
                    </Select>
                  </Field>
                )}
              </>
            ) : (
              <>
                <p className="text-[13px] font-semibold text-ink">
                  {i + 1}. {rule.label}
                </p>
                <p className="text-xs leading-relaxed text-muted">{rule.description}</p>
                {!CORE.has(rule.key) && (
                  <p className="text-[11px] text-subtle">
                    Applies to:{" "}
                    {rule.depends_on_roles
                      .map((r) => (r === "invoice" ? "invoice" : "delivery receipts"))
                      .join(" and ")}
                  </p>
                )}
              </>
            )}
          </div>
        ))}
      </div>
      {editing && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            icon={<Plus className="size-4" />}
            disabled={rules.length >= maximum}
            onClick={() =>
              onChange([
                ...rules,
                {
                  key: `rule_${crypto.randomUUID().replaceAll("-", "")}`,
                  label: "",
                  description: "",
                  depends_on_roles: ["invoice"],
                },
              ])
            }
          >
            Add policy rule
          </Button>
          <span className="text-xs text-muted">
            {rules.length} of {maximum} rules
          </span>
        </div>
      )}
    </div>
  );
}
