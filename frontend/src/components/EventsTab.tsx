import { useState } from "react";
import { BottomSheet } from "./BottomSheet";
import { lawDetails } from "../data/explanations";
import {
  lawForEvent,
  whistleEvents,
  type LiveState,
  type TimelineEvent,
} from "../lib/live";

/* "Why that whistle?" screen — the match events list is the live
   timeline projected by the state builder; the sheet explains the law
   behind each decision (static IFAB glossary until Referee RAG lands). */
export function EventsTab({ state }: { state: LiveState }) {
  const events = whistleEvents(state);

  const defaultEvent =
    events.find((ev) => ev.event_type === "foul") ??
    events.find((ev) => ev.event_type === "card") ??
    events[0];
  const [openEventId, setOpenEventId] = useState<string | null>(
    defaultEvent ? String(defaultEvent.seq) : null,
  );

  const openEvent =
    events.find((ev) => String(ev.seq) === openEventId) ?? null;
  const law = openEvent ? lawDetails[lawForEvent(openEvent)] : undefined;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Match events</h2>
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

      {openEvent && law && (
        <BottomSheet open onClose={() => setOpenEventId(null)} title={law.title}>
          <p className="sheet-prose">{law.body}</p>

          {law.legend && (
            <table className="law-legend">
              <tbody>
                {law.legend.map((row) => (
                  <tr key={row.term}>
                    <td>
                      <span className="term">
                        <span
                          className="swatch"
                          style={{ background: row.swatch }}
                          aria-hidden="true"
                        />
                        {row.term}
                      </span>
                    </td>
                    <td className="outcome">{row.outcome}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <hr className="law-legend__divider" />
          <p className="law-source">Source: {law.source}</p>
          <span className="law-disclaimer">
            Explains the rule, not a verdict on the call
          </span>
        </BottomSheet>
      )}
    </div>
  );
}

// keep the TimelineEvent type referenced for consumers of this module
export type { TimelineEvent };
