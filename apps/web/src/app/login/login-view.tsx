"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Eye, FileCheck2, FileUp, MessagesSquare, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { getJson } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { Brand } from "@/components/shell/app-shell";
import { Avatar, Badge, Button, Callout, ErrorState, Skeleton } from "@/components/ui/primitives";

function accountDescription(person: Persona) {
  if (person.roles.includes("vendor"))
    return {
      label: "Vendor",
      icon: FileUp,
      description:
        "Submit invoices and receipts, read requests from the bank, and reply with the information needed.",
      access: "Your submissions and conversations",
      home: "/vendor",
      order: 1,
    };
  if (person.roles.includes("auditor"))
    return {
      label: "Viewer",
      icon: Eye,
      description:
        "Follow every case, inspect documents and read the review history. Nothing can be uploaded or changed.",
      access: "Read-only access to the bank workspace",
      home: "/queue",
      order: 2,
    };
  return {
    label: "Alex · full access",
    icon: ShieldCheck,
    description: "Review cases, resolve decisions, manage policy and oversee automation.",
    access: "Bank review and administration",
    home: "/queue",
    order: 0,
  };
}

export function LoginView() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const personas = useQuery({
    queryKey: ["personas"],
    queryFn: ({ signal }) => getJson<{ personas: Persona[] }>("/v1/dev/personas", signal),
  });

  async function signIn(person: Persona) {
    if (pending) return;
    setPending(person.subject);
    setError(null);
    try {
      const response = await fetch("/api/v1/dev/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ subject: person.subject }),
        signal: AbortSignal.timeout(20_000),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Sign-in failed. Please try again.");
      }
      qc.clear();
      const home = accountDescription(person).home;
      const next = params.get("next");
      const safeNext =
        next?.startsWith("/") &&
        !next.startsWith("//") &&
        !next.includes("\\") &&
        (home === "/vendor"
          ? next === "/vendor" || next.startsWith("/vendor/")
          : !next.startsWith("/vendor"));
      router.replace(safeNext ? next! : home);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not connect. Please try again.");
      setPending(null);
    }
  }

  const people = [...(personas.data?.personas ?? [])].sort(
    (a, b) => accountDescription(a).order - accountDescription(b).order,
  );

  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <section className="relative hidden overflow-hidden bg-navy-900 px-10 py-9 text-white lg:sticky lg:top-0 lg:flex lg:h-dvh lg:min-h-[660px] lg:flex-col xl:px-14">
        <div className="pointer-events-none absolute -right-48 -top-32 size-[580px] rounded-full bg-teal-700/20 blur-3xl" />
        <div className="relative">
          <Brand />
        </div>
        <div className="relative my-auto max-w-lg py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-300">
            Invoice financing · document review
          </p>
          <h1 className="mt-5 text-[clamp(2.2rem,3.1vw,3rem)] font-semibold leading-[1.12] tracking-[-0.045em]">
            One case.
            <br />
            <span className="text-teal-300">A clear conversation.</span>
          </h1>
          <p className="mt-6 max-w-sm text-[15px] leading-relaxed text-white/70">
            The business supplies the documents. The agent follows up. The bank makes the decisions.
          </p>
          <ol className="mt-10 space-y-6">
            {[
              {
                icon: FileUp,
                title: "Submit",
                text: "The vendor uploads an invoice and delivery evidence.",
              },
              {
                icon: MessagesSquare,
                title: "Reply",
                text: "Requests and answers stay together in one conversation.",
              },
              {
                icon: FileCheck2,
                title: "Review",
                text: "Alex handles exceptions. The viewer follows the record.",
              },
            ].map(({ icon: Icon, title, text }, i) => (
              <li key={title} className="flex gap-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10">
                  <Icon className="size-5 text-teal-300" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-semibold">
                    {i + 1}. {title}
                  </p>
                  <p className="mt-1 max-w-xs text-[13px] leading-relaxed text-white/65">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <p className="relative text-xs text-white/45">CaseProof · Gemini & Google ADK</p>
      </section>
      <section
        aria-labelledby="sign-in-heading"
        className="flex flex-col justify-center bg-canvas px-5 py-8 sm:px-10 lg:px-12 xl:px-20"
      >
        <div className="mx-auto w-full max-w-xl">
          <div className="mb-8 lg:hidden">
            <Brand inverted={false} />
          </div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-700">
            Choose your workspace
          </p>
          <h2
            id="sign-in-heading"
            className="mt-2 text-3xl font-semibold tracking-[-0.035em] text-ink"
          >
            Welcome to CaseProof
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Three personas, one connected review. Choose what you want to do.
          </p>
          {params.get("revoked") && (
            <Callout tone="red" className="mt-4" title="Access revoked">
              That account no longer has access. Choose another account.
            </Callout>
          )}
          {error && (
            <div role="alert">
              <Callout tone="red" className="mt-4" title="Could not sign in">
                {error}
              </Callout>
            </div>
          )}
          <div className="mt-7 space-y-3" aria-label="Personas">
            {personas.isLoading && [1, 2, 3].map((i) => <Skeleton key={i} className="h-40" />)}
            {personas.error && (
              <ErrorState error={personas.error} onRetry={() => personas.refetch()} />
            )}
            {people.map((person) => {
              const role = accountDescription(person);
              const Icon = role.icon;
              return (
                <article
                  key={person.subject}
                  className="rounded-2xl border border-line bg-paper p-5 shadow-[var(--shadow-card)]"
                >
                  <div className="flex items-center gap-3">
                    <Avatar
                      name={person.name}
                      size={40}
                      tone={role.order === 0 ? "navy" : "teal"}
                    />
                    <div className="flex-1">
                      <h3 className="text-base font-semibold text-ink">{person.name}</h3>
                      <p className="mt-0.5 text-xs text-muted">{role.access}</p>
                    </div>
                    <Badge
                      tone={role.order === 0 ? "teal" : "neutral"}
                      icon={<Icon className="size-3" />}
                    >
                      {role.order === 0 ? "Full access" : role.label}
                    </Badge>
                  </div>
                  <p className="mt-3 text-[13px] leading-relaxed text-muted">
                    {person.revoked ? "Access to this account has been revoked." : role.description}
                  </p>
                  <Button
                    variant={role.order === 0 ? "primary" : "secondary"}
                    className="mt-4 w-full"
                    disabled={!!pending || person.revoked}
                    loading={pending === person.subject}
                    onClick={() => signIn(person)}
                  >
                    {pending === person.subject
                      ? "Opening workspace…"
                      : `Continue as ${person.name}`}
                    <ArrowRight className="ml-1 size-4" aria-hidden />
                  </Button>
                </article>
              );
            })}
          </div>
          <p className="mt-5 text-center text-xs leading-relaxed text-subtle">
            Demo sign-in · no password needed. Messages stay inside CaseProof.
          </p>
        </div>
      </section>
    </main>
  );
}
