import { useState } from "react";
import { BottomSheet } from "./BottomSheet";
import { eventTitles } from "../data/explanations";
import { useExplanation, type LawResponse } from "../lib/explanations";
import {
  lawForEvent,
  whistleEvents,
  type LiveState,
} from "../lib/live";

/* Explanations are requested only after selecting an event. */
export function EventsTab({ state }: { state: LiveState }) {
  const events = whistleEvents(state);

  const [openEventId, setOpenEventId] = useState<string | null>(null);

  const openEvent =
    events.find((ev) => String(ev.seq) === openEventId) ?? null;
  const title = openEvent ? eventTitles[lawForEvent(openEvent)] : undefined;
  const { data, loading, error, retry } = useExplanation<LawResponse>(
    openEvent
      ? `/rag/matches/${encodeURIComponent(state.match_id)}/events/${openEvent.seq}/explanation`
      : null,
    {},
  );

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Match events</h2>
        <span className="hint">Tap an event to explore the law</span>
      </div>

      <div className="event-rows">
        {events.map((ev) => (
          <button
            key={ev.seq}
            type="button"
            className={`event-row${String(ev.seq) === openEventId ? " is-selected" : ""}`}
            onClick={() => setOpenEventId(String(ev.seq))}
            aria-haspopup="dialog"
          >
            <span className="event-row__minute">{ev.display}</span>
            <span className="event-row__label">{ev.label}</span>
          </button>
        ))}
        {events.length === 0 && (
          <p className="page-note">No whistle-worthy events yet.</p>
        )}
      </div>

      {openEvent && (
        <BottomSheet open onClose={() => setOpenEventId(null)} title={title ?? "What does the law say?"}>
          <p className="explanation-context">{openEvent.display} · {openEvent.label}</p>
          {loading && <p className="explanation-status" role="status">Looking up the IFAB Laws…</p>}
          {error && (
            <div className="explanation-status" role="alert">
              <p>{error}</p>
              <button className="retry-btn" onClick={retry}>Try again</button>
            </div>
          )}
          {data && (
            <>
              <p className="sheet-sub">{data.answer.answerable ? "What the law says" : "Not enough evidence"}</p>
              <p className="sheet-prose">{data.answer.explanation}</p>
              {data.answer.data_limits && (
                <p className="data-limits">{data.answer.data_limits}</p>
              )}
              <hr className="law-legend__divider" />
              {data.answer.law_reference && <p className="law-source">Source: {data.answer.law_reference}</p>}
              {data.answer.citations.map((id, index) => {
                const passage = data.passages.find((p) => p.id === id);
                const chunk = data.chunks?.find((p) => p.id === id);
                return (
                  <details className="source-passage" key={id}>
                    <summary>Passage {index + 1} · {passage?.source ?? id}</summary>
                    <p>{chunk?.content ?? "Source passage unavailable."}</p>
                    {passage && <a className="source-document" href={`/api/v1/ifabs/${encodeURIComponent(passage.source)}`} target="_blank" rel="noreferrer">Open original IFAB document ↗</a>}
                  </details>
                );
              })}
            </>
          )}
          <span className="law-disclaimer">
            Explains the rule, not a verdict on the call
          </span>
        </BottomSheet>
      )}
    </div>
  );
}
