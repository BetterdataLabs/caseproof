"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BookCheck,
  ChevronsUpDown,
  Globe,
  Inbox,
  LayoutList,
  LogOut,
  Menu as MenuIcon,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useState } from "react";
import { toast } from "sonner";
import { post } from "@/lib/api";
import { SessionGate, useSession } from "@/lib/session";
import { Avatar, Menu, Skeleton, cx } from "@/components/ui/primitives";

const NAV = [
  { href: "/queue", label: "Work queue", icon: LayoutList },
  { href: "/decisions", label: "Decisions", icon: Inbox, countKey: "open_tasks" as const },
  { href: "/research", label: "Research", icon: Globe },
  { href: "/operations", label: "Operations", icon: Activity },
  { href: "/policy", label: "Policy", icon: BookCheck },
];

export function Brand({ inverted = true }: { inverted?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={cx(
          "grid size-8 place-items-center rounded-[9px]",
          inverted ? "bg-teal-700" : "bg-navy-900",
        )}
      >
        <ShieldCheck className="size-[18px] text-white" aria-hidden />
      </span>
      <span
        className={cx(
          "text-[17px] font-extrabold tracking-[-0.03em]",
          inverted ? "text-white" : "text-ink",
        )}
      >
        Case<span className={inverted ? "text-teal-300" : "text-teal-700"}>Proof</span>
      </span>
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const session = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();

  async function switchOrg(orgId: string) {
    await post("/v1/session/organisation", { org_id: orgId });
    qc.clear();
    router.push("/queue");
    toast.success("Organisation switched");
  }
  async function signOut() {
    await post("/v1/session/logout", {});
    qc.clear();
    router.push("/login");
  }

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pb-4 pt-5">
        <Brand />
      </div>
      <div className="px-3">
        <Menu
          align="start"
          trigger={
            <button className="flex w-full items-center gap-2.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-left hover:bg-white/10">
              <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-white/10 text-[11px] font-bold text-white">
                {session.organisation.short_name.slice(0, 2).toUpperCase()}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-white">
                  {session.organisation.short_name}
                </span>
                <span className="block truncate text-[11.5px] text-white/55">Trade operations</span>
              </span>
              <ChevronsUpDown className="size-4 text-white/50" aria-hidden />
            </button>
          }
          items={session.memberships.map((m) => ({
            label: m.name,
            onSelect: () => m.org_id !== session.organisation.id && switchOrg(m.org_id),
            disabled: m.org_id === session.organisation.id,
          }))}
        />
      </div>
      <nav aria-label="Main" className="mt-5 flex-1 space-y-0.5 px-3">
        {NAV.map((item) => {
          const active =
            pathname === item.href ||
            pathname.startsWith(item.href + "/") ||
            (item.href === "/queue" && pathname.startsWith("/cases"));
          const Icon = item.icon;
          const count = item.countKey ? session.counts[item.countKey] : 0;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "group flex items-center gap-3 rounded-[10px] px-3 py-2 text-[14px] font-medium transition-colors",
                active
                  ? "bg-white/[0.12] text-white"
                  : "text-white/70 hover:bg-white/[0.06] hover:text-white",
              )}
            >
              <Icon
                className={cx(
                  "size-[18px]",
                  active ? "text-teal-300" : "text-white/50 group-hover:text-white/80",
                )}
                aria-hidden
              />
              <span className="flex-1">{item.label}</span>
              {count > 0 && (
                <span className="rounded-full bg-amber-600 px-1.5 py-px text-[11px] font-bold text-white tabular">
                  {count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mx-3 mb-3 rounded-xl border border-white/10 bg-white/[0.04] p-3">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-white/85">
          <Sparkles className="size-3.5 text-teal-300" aria-hidden />
          {session.model.provider === "vertex" ? "Gemini on Vertex AI" : "Model stub (labelled)"}
        </div>
        <p className="mt-1 text-[11.5px] leading-relaxed text-white/50">
          {session.model.name} ·{" "}
          {session.model.location === "asia-southeast1" ? "Singapore" : session.model.location}
          <br />
          Agent framework: Google ADK
        </p>
        {!session.automation_enabled && (
          <p className="mt-2 rounded-md bg-red-600 px-2 py-1 text-[11px] font-bold text-white">
            Emergency stop active
          </p>
        )}
      </div>
      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-2.5 px-2 py-2">
          <Avatar name={session.user.name} size={32} tone="teal" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-white">
              {session.user.name}
            </span>
            <span className="block truncate text-[11.5px] text-white/55">
              {session.workspace === "viewer"
                ? "Viewer · read-only access"
                : session.roles.map((r) => r.replace(/_/g, " ")).join(" · ")}
            </span>
          </span>
        </div>
        <div className="mt-1 space-y-0.5">
          {session.dev_identity && (
            <button
              type="button"
              onClick={() => router.push("/login?pick=1")}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] font-semibold text-white/80 hover:bg-white/10"
            >
              Switch persona
            </button>
          )}
          <button
            type="button"
            onClick={signOut}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] font-semibold text-white/80 hover:bg-white/10"
          >
            <LogOut className="size-4" aria-hidden />
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

function ShellFallback() {
  return (
    <div className="flex min-h-screen">
      <div className="hidden w-[248px] bg-navy-900 lg:block" />
      <div className="flex-1 space-y-4 p-8">
        <p className="text-[13px] text-muted" role="status">
          Loading CaseProof…
        </p>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    </div>
  );
}

function MobileSignOut() {
  const qc = useQueryClient();
  const router = useRouter();
  async function signOut() {
    await post("/v1/session/logout", {});
    qc.clear();
    router.push("/login");
  }
  return (
    <button
      type="button"
      onClick={signOut}
      className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[13px] font-semibold text-ink hover:bg-teal-50"
    >
      <LogOut className="size-4" aria-hidden />
      Sign out
    </button>
  );
}

function ViewerNotice() {
  const session = useSession();
  if (session.workspace !== "viewer") return null;
  return (
    <div className="border-b border-line bg-teal-50 px-4 py-2.5 text-[13px] text-teal-800 sm:px-6">
      <strong>Viewer access.</strong> You can inspect cases, documents and history. Uploads, replies
      and review decisions are available to the other personas.
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <SessionGate fallback={<ShellFallback />}>
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-white px-3 py-2 focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <div className="flex min-h-screen">
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] bg-navy-900 lg:block">
          <SidebarContent />
        </aside>
        {open && (
          <div
            className="fixed inset-0 z-40 lg:hidden"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
          >
            <button
              className="absolute inset-0 bg-navy-950/50"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            />
            <aside className="absolute inset-y-0 left-0 w-[272px] bg-navy-900 shadow-[var(--shadow-pop)] animate-[var(--animate-slide-in)]">
              <button
                onClick={() => setOpen(false)}
                className="absolute right-3 top-4 rounded-lg p-1.5 text-white/70 hover:bg-white/10"
                aria-label="Close navigation"
              >
                <X className="size-5" />
              </button>
              <SidebarContent onNavigate={() => setOpen(false)} />
            </aside>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col lg:pl-[248px]">
          <div className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-paper/95 px-4 backdrop-blur lg:hidden">
            <button
              onClick={() => setOpen(true)}
              className="rounded-lg p-2 text-ink hover:bg-teal-50"
              aria-label="Open navigation"
            >
              <MenuIcon className="size-5" />
            </button>
            <Brand inverted={false} />
            <MobileSignOut />
          </div>
          <main id="main" className="min-w-0 flex-1">
            <ViewerNotice />
            {children}
          </main>
        </div>
      </div>
    </SessionGate>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 pb-6">
      <div className="min-w-0">
        {eyebrow && <div className="mb-2">{eyebrow}</div>}
        <h1 className="text-[26px] font-bold tracking-[-0.03em] text-ink sm:text-[28px]">
          {title}
        </h1>
        {description && <p className="mt-1.5 max-w-3xl text-[14.5px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
