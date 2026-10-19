import { useState } from "react";
import { BottomSheet } from "./BottomSheet";
import type { LawDetail, MatchEvent } from "../types";

export function EventsTab({
  events,
  laws,
}: {
  events: MatchEvent[];
  laws: Record<string, LawDetail>;
}) {
  // Default to a referee decision (foul / card) like the product screens;
  // fall back to the second event, then the first.
  const defaultEvent =
    events.find((ev) => ev.type === "foul") ??
    events.find((ev) => ev.type === "yellow-card") ??
    events[1] ??
    events[0];
  const [openEventId, setOpenEventId] = useState<string | null>(
    defaultEvent?.id ?? null,
  );

  const openEvent = events.find((ev) => ev.id === openEventId) ?? null;
  const law = openEvent ? laws[openEvent.type] : undefined;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Match events</h2>
      </div>

      <div className="event-rows">
        {events.map((ev) => (
          <button
            key={ev.id}
            type="button"
            className={`event-row${openEventId === ev.id ? " is-selected" : ""}`}
            onClick={() => setOpenEventId(ev.id)}
            aria-haspopup="dialog"
          >
            <span className="event-row__minute">{ev.minute}'</span>
            <span className="event-row__label">{ev.label}</span>
          </button>
        ))}
      </div>

      {openEvent && law && (
        <BottomSheet
          open
          onClose={() => setOpenEventId(null)}
          title={law.title}
        >
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
