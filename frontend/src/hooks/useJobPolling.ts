import { useEffect, useRef, useState } from "react";
import { client, formatError } from "../graphql/client";
import { ANALYSIS_JOB_STATUS_QUERY, type AnalysisJob } from "../graphql/operations";

const POLL_INTERVAL_MS = 2000;

/**
 * Polls analysisJob(id) until it reaches "completed" or "failed", or the
 * poll itself fails network-side (handled explicitly so a dropped request
 * surfaces an error instead of silently hanging forever -- the original
 * landing-page-only version of this logic had no such fallback).
 */
export function useJobPolling(jobId: string | null, onSettled: (job: AnalysisJob) => void) {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSettledRef = useRef(onSettled);

  useEffect(() => {
    onSettledRef.current = onSettled;
  }, [onSettled]);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    setJob(null);
    setPollError(null);

    function poll() {
      timeoutRef.current = setTimeout(async () => {
        const result = await client
          .query<{ analysisJob: AnalysisJob | null }>(ANALYSIS_JOB_STATUS_QUERY, { id: jobId })
          .toPromise();
        if (cancelled) return;

        if (result.error) {
          setPollError(formatError(result.error));
          return;
        }
        const latest = result.data?.analysisJob;
        if (!latest) {
          setPollError("Analysis job not found.");
          return;
        }
        setJob(latest);
        if (latest.status === "completed" || latest.status === "failed") {
          onSettledRef.current(latest);
        } else {
          poll();
        }
      }, POLL_INTERVAL_MS);
    }

    poll();
    return () => {
      cancelled = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [jobId]);

  return { job, pollError };
}
