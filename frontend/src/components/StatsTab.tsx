import { useState } from "react";
import { BottomSheet } from "./BottomSheet";
import { AUDIENCES, statExplanations } from "../data/explanations";
import {
  formatStat,
  inMatchLine,
  statRowsFromState,
  type LiveState,
} from "../lib/live";
import type { Audience } from "../types";

const AUDIENCE_LABELS: Record<Audience, string> = {
  "new-fan": "New fan",
  regular: "Regular",
  analyst: "Analyst",
};

/* "Tap any stat" screen — rows come from the live match state and
   update in place as SSE frames arrive. */
export function StatsTab({ state }: { state: LiveState }) {
  const [openStatId, setOpenStatId] = useState<string | null>(null);
  const [audience, setAudience] = useState<Audience>("new-fan");

  const rows = statRowsFromState(state);
  const openRow = rows.find((r) => r.id === openStatId) ?? null;
  const openExplanation = statExplanations.find(
    (e) => e.statId === openStatId,
  );

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Stats</h2>
        <span className="hint">Tap a stat to learn more</span>
      </div>

      <div className="stat-rows">
        {rows.map((row) => (
          <button
            key={row.id}
            type="button"
            className={`stat-row${openStatId === row.id ? " is-selected" : ""}`}
            onClick={() => {
              setAudience("new-fan");
              setOpenStatId(row.id);
            }}
            aria-haspopup="dialog"
          >
            <span className="stat-row__value">
              {formatStat(row.home, row.format)}
            </span>
            <span className="stat-row__label">
              {row.label}
              <span className="help-dot" aria-hidden="true">
                ?
              </span>
            </span>
            <span className="stat-row__value stat-row__value--away">
              {formatStat(row.away, row.format)}
            </span>
          </button>
        ))}
      </div>

      {openRow && openExplanation && (
        <BottomSheet
          open
          onClose={() => setOpenStatId(null)}
          title={`${openRow.label}${openRow.id === "xg" ? " (expected goals)" : ""}`}
        >
          <div className="audience" role="tablist" aria-label="Explanation level">
            {AUDIENCES.map((a) => (
              <button
                key={a}
                role="tab"
                aria-selected={audience === a}
                className={`audience__btn${audience === a ? " is-active" : ""}`}
                onClick={() => setAudience(a)}
              >
                {AUDIENCE_LABELS[a]}
              </button>
            ))}
          </div>

          <p className="sheet-sub">What it is</p>
          <p className="sheet-prose">{openExplanation.whatItIs[audience]}</p>

          <p className="sheet-sub">In this match</p>
          <p className="sheet-prose">{inMatchLine(openRow.id, state)}</p>
        </BottomSheet>
      )}
    </div>
  );
}
