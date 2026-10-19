import { useState } from "react";
import { TimelineScrubber } from "./TimelineScrubber";
import { buildSummary, timelineMarkers } from "../lib/summary";
import type { MatchBundle, MatchDetail, SummaryWindow } from "../types";

const WINDOWS: Array<{ id: SummaryWindow; label: string }> = [
  { id: "since-kickoff", label: "Since kick-off" },
  { id: "last-10", label: "Last 10 min" },
  { id: "since-joined", label: "Since I joined" },
];

/* "Catch me up" screen: window chips, plain-language story,
   a time scrubber with Goal/Stoppage markers, and the
   grounding badge (claims verified against the event stream). */
export function SummaryTab({
  bundle,
  detail,
}: {
  bundle: MatchBundle;
  detail: MatchDetail;
}) {
  const [win, setWin] = useState<SummaryWindow>("since-kickoff");
  const [minute, setMinute] = useState(bundle.match.minute);

  const summary = buildSummary(bundle, detail, minute, win);
  const markers = timelineMarkers(detail);

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

      {markers.length > 0 && (
        <TimelineScrubber
          min={0}
          max={bundle.match.minute}
          value={minute}
          markers={markers}
          onChange={setMinute}
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
    </div>
  );
}
