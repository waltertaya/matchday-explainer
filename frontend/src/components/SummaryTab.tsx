import { useEffect, useRef, useState } from "react";
import { TimelineScrubber } from "./TimelineScrubber";
import type { SummaryWindow } from "../lib/summary";
import { useExplanation, type SummaryResponse } from "../lib/explanations";
import { timelineMarkers, type LiveState } from "../lib/live";

const WINDOWS: Array<{ id: SummaryWindow; label: string }> = [
  { id: "since-kickoff", label: "Since kick-off" },
  { id: "last-10", label: "Last 10 min" },
  { id: "since-joined", label: "Since I joined" },
];

/* "Catch me up" screen: window chips, plain-language story,
   a time scrubber with Goal/Stoppage markers, and the
   grounding badge — all driven by the live event timeline. */
export function SummaryTab({
  state,
  joinedAt,
}: {
  state: LiveState;
  joinedAt: number;
}) {
  const [win, setWin] = useState<SummaryWindow>("since-kickoff");
  // null = follow the live clock; a number = the user has scrubbed
  const [scrubbed, setScrubbed] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState(state);
  const latest = useRef(state);
  useEffect(() => { latest.current = state; }, [state]);
  useEffect(() => {
    // Let an AI request finish even during accelerated event replays. Sampling
    // every 30 seconds avoids cancelling it on every incoming SSE frame.
    const timer = setInterval(() => setSnapshot(latest.current), 30_000);
    return () => clearInterval(timer);
  }, []);
  const minute = Math.min(scrubbed ?? snapshot.minute, state.minute);

  const { data: summary, loading, error, retry } = useExplanation<SummaryResponse>(
    `/matches/${encodeURIComponent(state.match_id)}/summary`,
    { minute, window: win, joined_at: Math.min(joinedAt, state.minute) },
    snapshot.last_seq,
  );
  const markers = timelineMarkers(state);

  return (
    <div className="panel">
      <div className="chip-tabs" role="tablist" aria-label="Summary window">
        {WINDOWS.map((w) => (
          <button
            key={w.id}
            role="tab"
            aria-selected={win === w.id}
            className={`chip-tab${win === w.id ? " is-active" : ""}`}
            onClick={() => { setWin(w.id); setSnapshot(state); }}
          >
            {w.label}
          </button>
        ))}
      </div>

      <article className="summary-card">
        <p className="summary-card__title">{summary?.title ?? "Your match catch-up"}</p>
        <div className="summary-card__story">
          {loading && <p role="status">Preparing a summary from the match events…</p>}
          {error && <div role="alert"><p>{error}</p><button className="retry-btn" onClick={retry}>Try again</button></div>}
          {summary?.paragraphs.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </article>
      {summary && <p className="explanation-status">{summary.notice ?? "AI-selected highlights · checked against match data"}</p>}

      {markers.length > 0 && state.minute > 0 && (
        <TimelineScrubber
          min={0}
          max={state.minute}
          value={minute}
          markers={markers}
          onChange={setScrubbed}
        />
      )}
      {scrubbed !== null && (
        <button className="retry-btn follow-live" onClick={() => { setScrubbed(null); setSnapshot(state); }}>
          {state.status === "full_time" ? "Back to full-time" : "Back to live"}
        </button>
      )}

      {summary && summary.claims.total > 0 && (
        <div className="claims-badge">
          <span className="dot" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M9.6 16.6 4.8 11.8l1.4-1.4 3.4 3.4 8-8 1.4 1.4z" />
            </svg>
          </span>
          {summary.claims.verified} of {summary.claims.total} facts linked to match data
        </div>
      )}
      {summary && <details className="source-passage summary-evidence">
        <summary>View supporting match data</summary>
        <ul>{summary.evidence.map((fact) => <li key={fact.id}><code>{fact.id}</code> — {fact.text}</li>)}</ul>
      </details>}

      {state.timeline.length === 0 && (
        <p className="page-note">
          Waiting for the first events of this match…
        </p>
      )}
    </div>
  );
}
