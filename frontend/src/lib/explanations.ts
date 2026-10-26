import { useEffect, useState } from "react";
import type { MatchSummary } from "./summary";

export interface SummaryResponse extends MatchSummary {
  source: "ai" | "event-stream";
  notice: string | null;
  evidence: Array<{ id: string; text: string }>;
}

export interface StatResponse {
  what_it_is: string;
  in_this_match: string;
  source: "ai" | "glossary";
  notice: string | null;
}

export interface LawResponse {
  answer: {
    answerable: boolean;
    explanation: string;
    law_reference: string | null;
    citations: string[];
    data_limits: string | null;
  };
  passages: Array<{ id: string; source: string; similarity: number }>;
  chunks?: Array<{ id: string; source: string; content: string }>;
}

const cache = new Map<string, { data: unknown; expires: number }>();

/** Only requests when enabled. Cancels obsolete requests and hides stale results. */
export function useExplanation<T>(
  path: string | null,
  body: Record<string, unknown>,
  revision: number = 0,
) {
  const serialized = JSON.stringify(body);
  const key = path ? `${path}:${serialized}:${revision}` : "";
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    key: string; data?: T; error?: string;
  }>({ key: "" });

  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    let alive = true;
    // Debounce scrubber changes and avoid duplicate requests under StrictMode.
    const timer = setTimeout(async () => {
      const hit = cache.get(key);
      if (hit && hit.expires > Date.now()) {
        setResult({ key, data: hit.data as T });
        return;
      }
      try {
        const response = await fetch(`/api/v1${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: serialized,
          signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ?? `Request failed (${response.status})`);
        if (!alive) return;
        if (cache.size >= 100) cache.delete(cache.keys().next().value!);
        cache.set(key, { data, expires: Date.now() + 30_000 });
        setResult({ key, data: data as T });
      } catch (error) {
        if (alive) setResult({ key, error: error instanceof Error ? error.message : "Request failed" });
      }
    }, 250);
    return () => {
      alive = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [path, serialized, key, attempt]);

  const current = result.key === key ? result : null;
  return {
    data: current?.data,
    error: current?.error,
    loading: !!path && !current?.data && !current?.error,
    retry: () => {
      cache.delete(key);
      setResult({ key });
      setAttempt((value) => value + 1);
    },
  };
}
