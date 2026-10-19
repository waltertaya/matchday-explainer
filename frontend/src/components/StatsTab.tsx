import { useState } from "react";
import { BottomSheet } from "./BottomSheet";
import { AUDIENCES } from "../data/explanations";
import type { Audience, StatRow } from "../types";

const AUDIENCE_LABELS: Record<Audience, string> = {
  "new-fan": "New fan",
  regular: "Regular",
  analyst: "Analyst",
};

function formatValue(value: number, format: StatRow["format"]) {
  return format === "percent" ? `${value}%` : String(value);
}

export function StatsTab({
  statRows,
  explanations,
}: {
  statRows: StatRow[];
  explanations: MatchDetailExplanations;
}) {
  const [openStatId, setOpenStatId] = useState<string | null>(null);
  const [audience, setAudience] = useState<Audience>("new-fan");

  const openRow = statRows.find((r) => r.id === openStatId) ?? null;
  const openExplanation = openStatId
    ? explanations.find((e) => e.statId === openStatId)
    : undefined;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Stats</h2>
        <span className="hint">Tap a stat to learn more</span>
      </div>

      <div className="stat-rows">
        {statRows.map((row) => (
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
              {formatValue(row.homeValue, row.format)}
            </span>
            <span className="stat-row__label">
              {row.label}
              <span className="help-dot" aria-hidden="true">
                ?
              </span>
            </span>
            <span className="stat-row__value stat-row__value--away">
              {formatValue(row.awayValue, row.format)}
            </span>
          </button>
        ))}
      </div>

      {openRow && openExplanation && (
        <BottomSheet
          open
          onClose={() => setOpenStatId(null)}
          title={`${openRow.label} (${openRow.name})`}
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
          <p className="sheet-prose">{openExplanation.inThisMatchOverride}</p>
        </BottomSheet>
      )}
    </div>
  );
}

type MatchDetailExplanations = {
  statId: string;
  whatItIs: Record<Audience, string>;
  inThisMatchOverride?: string;
}[];
