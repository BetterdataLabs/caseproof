"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { toast } from "sonner";
import { ApiError, command, get, newKey } from "./api";
import type { CaseDetail } from "./types";

/** Case detail with conditional polling: 2 s while the agent works, 15 s while waiting, paused in hidden tabs.
 *  Unchanged responses return 304 against the ETag, and a stale response never replaces a newer revision. */
export function useCaseDetail(id: string) {
  const etag = useRef<string | null>(null);
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["case", id],
    queryFn: async ({ signal }) => {
      const res = await get<CaseDetail>(`/v1/cases/${id}`, {
        signal,
        etag: etag.current ?? undefined,
      });
      const previous = qc.getQueryData<CaseDetail>(["case", id]);
      if (res.status === 304 && previous) return previous;
      if (res.data && previous && res.data.case.revision < previous.case.revision) return previous;
      etag.current = res.etag;
      return res.data as CaseDetail;
    },
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return 5_000;
      if (["queued", "running"].includes(d.case.execution)) return 2_000;
      if (d.exports.some((e) => e.state === "preparing")) return 2_000;
      return 15_000;
    },
    refetchIntervalInBackground: false,
  });
}

/** A case command. The idempotency key is created once per intent and reused if the user retries. */
export function useCaseCommand<TVars, TRes = unknown>(
  caseId: string,
  path: (v: TVars) => string,
  body: (v: TVars) => unknown,
  opts?: { success?: string | ((r: TRes) => string); onSuccess?: (r: TRes) => void },
) {
  const qc = useQueryClient();
  const key = useRef<string | null>(null);
  return useMutation<TRes, ApiError, TVars>({
    mutationFn: (vars) => {
      key.current = key.current ?? newKey();
      return command<TRes>(path(vars), body(vars), key.current);
    },
    onSuccess: (res) => {
      key.current = null;
      if (opts?.success)
        toast.success(typeof opts.success === "function" ? opts.success(res) : opts.success);
      qc.invalidateQueries({ queryKey: ["case", caseId] });
      qc.invalidateQueries({ queryKey: ["cases"] });
      qc.invalidateQueries({ queryKey: ["research"] });
      qc.invalidateQueries({ queryKey: ["session"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      opts?.onSuccess?.(res);
    },
    onError: (err) => {
      if (err.isConflict) {
        key.current = null; // the user must review the new state; a resubmission is a new intent
        toast.warning("The case changed while you were working", {
          description: "Your entries are kept. Review the updated evidence, then submit again.",
        });
        qc.invalidateQueries({ queryKey: ["case", caseId] });
      } else if (err.status >= 400 && err.status < 500) {
        key.current = null;
        toast.error(err.message);
      } else {
        toast.error("Not confirmed yet", {
          description:
            "The service did not answer. Retrying uses the same request key, so nothing is duplicated.",
        });
      }
    },
  });
}
