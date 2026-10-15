"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getJson } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
import { useCaseCommand } from "@/lib/use-case";
import { Button, Dialog, Field, Textarea } from "@/components/ui/primitives";

export function PolicyVersionAction({ detail }: { detail: CaseDetail }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const policies = useQuery({
    queryKey: ["policies"],
    queryFn: ({ signal }) =>
      getJson<{
        policies: { id: string; version: number; status: string; definition: { name: string } }[];
      }>("/v1/policies", signal),
    enabled: detail.permissions.supervise,
  });
  const latest = policies.data?.policies.find((p) => p.status === "published");
  const save = useCaseCommand<{ id: string; reason: string }>(
    detail.case.id,
    () => `/v1/cases/${detail.case.id}/policy`,
    (value) => ({
      policy_id: value.id,
      reason: value.reason,
      expected_revision: detail.case.revision,
    }),
    {
      success: "Policy updated. Documents will be reviewed again.",
      onSuccess: () => setOpen(false),
    },
  );
  if (
    !detail.permissions.supervise ||
    !latest ||
    latest.version <= detail.case.policy.version ||
    detail.case.lifecycle === "archived"
  )
    return null;
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Apply policy v{latest.version}
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={`Apply policy v${latest.version}`}
        description="Re-evaluate this case under the updated rules. Previous requests and review summaries remain in history; any new requests use the updated policy."
      >
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate({ id: latest.id, reason });
          }}
        >
          <p className="text-sm font-semibold text-ink">{latest.definition.name}</p>
          <Field label="Reason for updating this case" htmlFor="policy-change-reason">
            <Textarea
              id="policy-change-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              minLength={5}
              maxLength={1000}
            />
          </Field>
          {save.error && (
            <p role="alert" className="text-sm text-red-700">
              {save.error.message}
            </p>
          )}
          <Button type="submit" loading={save.isPending}>
            Apply and re-evaluate
          </Button>
        </form>
      </Dialog>
    </>
  );
}
