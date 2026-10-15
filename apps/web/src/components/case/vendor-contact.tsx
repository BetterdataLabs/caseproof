"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getJson } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { CaseDetail } from "@/lib/types";
import { useCaseCommand } from "@/lib/use-case";
import { Button, Dialog, Field, Select } from "@/components/ui/primitives";

type Member = { id: string; name: string; roles: string[] };

export function VendorContactField({
  defaultValue,
  onChange,
}: {
  defaultValue?: string;
  onChange?: (value: string) => void;
}) {
  const session = useSession();
  const members = useQuery({
    queryKey: ["members"],
    queryFn: ({ signal }) => getJson<{ members: Member[] }>("/v1/members", signal),
  });
  const vendors =
    members.data?.members.filter((m) => m.roles.length === 1 && m.roles.includes("vendor")) ?? [];
  const suggested =
    defaultValue ?? (session.demo_mode && vendors.length === 1 ? vendors[0].id : "");
  return (
    <Field
      label="Vendor contact"
      htmlFor="vendor-contact"
      hint="This person can see the case documents and bank requests, then reply and upload corrections in their vendor workspace."
    >
      {members.isPending ? (
        <p role="status" className="text-xs text-muted">
          Loading vendor contacts…
        </p>
      ) : (
        <Select
          id="vendor-contact"
          name="vendor_contact_id"
          defaultValue={suggested}
          onChange={(e) => onChange?.(e.target.value)}
        >
          <option value="">Bank review only — no vendor contact</option>
          {vendors.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </Select>
      )}
      {members.isError && (
        <p role="alert" className="mt-1 text-xs text-amber-700">
          Contacts could not be loaded. You can set the contact from the case later.
        </p>
      )}
    </Field>
  );
}

export function VendorContactPanel({ detail }: { detail: CaseDetail }) {
  const [open, setOpen] = useState(false);
  const contact = detail.case.vendor_contact;
  const save = useCaseCommand<string | null>(
    detail.case.id,
    () => `/v1/cases/${detail.case.id}/vendor-contact`,
    (userId) => ({ user_id: userId, expected_revision: detail.case.revision }),
    { success: "Vendor contact updated", onSuccess: () => setOpen(false) },
  );
  return (
    <>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-ink">
            Vendor contact: {contact?.name ?? "Not assigned"}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {contact
              ? `Bank requests for this case appear in ${contact.name}’s vendor workspace.`
              : "Choose a vendor contact so the business can see requests and send documents."}
          </p>
        </div>
        {detail.permissions.decide && detail.case.lifecycle !== "archived" && (
          <Button
            variant="secondary"
            onClick={() => {
              save.reset();
              setOpen(true);
            }}
          >
            {contact ? "Change contact" : "Choose vendor contact"}
          </Button>
        )}
      </div>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Vendor contact"
        description="Share this case’s documents and issued requests with the person who will reply for the business."
      >
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            const value = new FormData(e.currentTarget).get("vendor_contact_id");
            if (value !== null) save.mutate(String(value) || null);
          }}
        >
          <fieldset disabled={save.isPending} className="space-y-4">
            <VendorContactField defaultValue={contact?.id ?? ""} />
            {contact && (
              <p className="text-xs text-muted">
                Changing or removing this contact ends the previous contact’s access to this case.
              </p>
            )}
            {save.error && (
              <p role="alert" className="text-sm text-red-700">
                {save.error.message}
              </p>
            )}
            <Button type="submit" loading={save.isPending}>
              Save contact
            </Button>
          </fieldset>
        </form>
      </Dialog>
    </>
  );
}
