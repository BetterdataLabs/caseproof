"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Repeat2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { post } from "@/lib/api";
import { SessionGate, useSession } from "@/lib/session";
import { Brand } from "@/components/shell/app-shell";
import { Avatar, Button } from "@/components/ui/primitives";

function Workspace({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const qc = useQueryClient();
  const router = useRouter();
  async function signOut() {
    await post("/v1/session/logout", {});
    qc.clear();
    router.push("/login");
  }
  return (
    <div className="min-h-dvh bg-canvas">
      <header className="border-b border-line bg-paper">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/vendor" aria-label="CaseProof · My submissions">
            <Brand inverted={false} />
          </Link>
          <div className="flex items-center gap-3">
            <Avatar name={session.user.name} size={32} tone="teal" />
            <div className="mr-1 text-xs">
              <p className="font-semibold text-ink">{session.user.name}</p>
              <p className="text-muted">Vendor workspace</p>
            </div>
            {session.dev_identity && (
              <Button
                variant="ghost"
                size="sm"
                icon={<Repeat2 className="size-4" />}
                onClick={() => router.push("/login?pick=1")}
              >
                Switch persona
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              aria-label="Sign out"
              icon={<LogOut className="size-4" />}
              onClick={signOut}
            />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-7 sm:px-6 sm:py-9">
        {children}
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-6 text-xs text-subtle sm:px-6">
        Messages and documents are shared with {session.organisation.short_name} in this workspace.
        No external email is sent.
      </footer>
    </div>
  );
}

export function VendorShell({ children }: { children: React.ReactNode }) {
  return (
    <SessionGate
      fallback={
        <p className="p-8 text-sm text-muted" role="status">
          Opening your workspace…
        </p>
      }
    >
      <Workspace>{children}</Workspace>
    </SessionGate>
  );
}
