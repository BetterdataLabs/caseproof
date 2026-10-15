"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import React, { createContext, useContext, useEffect } from "react";
import { ApiError, getJson, setCsrfToken } from "./api";
import type { SessionInfo } from "./types";

const SessionContext = createContext<SessionInfo | null>(null);

export function useSessionQuery() {
  return useQuery({
    queryKey: ["session"],
    queryFn: async ({ signal }) => {
      const s = await getJson<SessionInfo>("/v1/session", signal);
      setCsrfToken(s.csrf_token);
      return s;
    },
    retry: (count, err) => !isAuthError(err) && count < 2,
    retryDelay: 800,
    refetchInterval: 20_000,
  });
}

function isAuthError(e: unknown) {
  return e instanceof ApiError && (e.status === 401 || e.status === 403);
}

export function SessionGate({
  children,
  fallback,
}: {
  children: React.ReactNode;
  fallback: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const q = useSessionQuery();
  const wrongWorkspace =
    !!q.data &&
    (q.data.workspace === "vendor") !== (pathname === "/vendor" || pathname.startsWith("/vendor/"));
  useEffect(() => {
    if (wrongWorkspace && q.data)
      router.replace(q.data.workspace === "vendor" ? "/vendor" : "/queue");
    if (isAuthError(q.error)) {
      const status = (q.error as ApiError).status;
      router.replace(
        `/login?next=${encodeURIComponent(pathname)}${status === 403 ? "&revoked=1" : ""}`,
      );
    }
  }, [q.error, q.data, wrongWorkspace, router, pathname]);
  if (!q.data && q.error && !isAuthError(q.error)) {
    // Authentication errors redirect; service failures offer a retry without discarding the session.
    return (
      <div className="grid min-h-screen place-items-center bg-canvas px-6">
        <div
          role="alert"
          className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-6 text-center shadow-[var(--shadow-card)]"
        >
          <p className="text-[17px] font-semibold text-ink">
            CaseProof could not load your session
          </p>
          <p className="mt-2 text-[14px] text-muted">
            {q.error instanceof Error ? q.error.message : "The service did not answer."}
          </p>
          <p className="mt-1 text-[13px] text-subtle">
            Try again in a moment, or return to sign-in.
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <button
              onClick={() => q.refetch()}
              className="h-10 rounded-[10px] bg-teal-700 px-4 text-sm font-semibold text-white hover:bg-teal-800"
            >
              Retry
            </button>
            <a
              href="/login"
              className="inline-flex h-10 items-center rounded-[10px] border border-line px-4 text-sm font-semibold text-ink hover:bg-teal-50"
            >
              Go to sign-in
            </a>
          </div>
        </div>
      </div>
    );
  }
  if (!q.data || wrongWorkspace) return <>{fallback}</>;
  return <SessionContext.Provider value={q.data}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionInfo {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession outside SessionGate");
  return s;
}

export function useRoles() {
  const s = useSession();
  const has = (...roles: string[]) => roles.some((r) => s.roles.includes(r));
  return {
    has,
    canDecide: has("reviewer", "supervisor"),
    canSupervise: has("supervisor"),
    canSimulate: has("simulation_operator") && s.demo_mode,
    isAdmin: has("environment_admin"),
  };
}
