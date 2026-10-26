import { useState } from "react";
import { TimelineScrubber } from "./TimelineScrubber";
import { buildSummary, type SummaryWindow } from "../lib/summary";
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
  const minute = scrubbed ?? state.minute;

  const summary = buildSummary(state, minute, win, joinedAt);
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
            onClick={() => setWin(w.id)}
          >
            {w.label}
          </button>
        ))}
      </div>

      <article className="summary-card">
        <p className="summary-card__title">{summary.title}</p>
        <div className="summary-card__story">
          {summary.paragraphs.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </article>

      {markers.length > 0 && state.minute > 0 && (
        <TimelineScrubber
          min={0}
          max={state.minute}
          value={minute}
          markers={markers}
          onChange={setScrubbed}
        />
      )}

      {summary.claims.total > 0 && (
        <div className="claims-badge">
          <span className="dot" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M9.6 16.6 4.8 11.8l1.4-1.4 3.4 3.4 8-8 1.4 1.4z" />
            </svg>
          </span>
          {summary.claims.verified} of {summary.claims.total} claims verified
        </div>
      )}

      {state.timeline.length === 0 && (
        <p className="page-note">
          Waiting for the first events of this match…
        </p>
      )}
    </div>
  );
}
