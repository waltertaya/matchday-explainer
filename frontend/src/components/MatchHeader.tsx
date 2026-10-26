import type { LiveState } from "../lib/live";
import { statusLabel } from "../lib/live";

/** Dark green scoreboard header from the product screens, now live. */
export function MatchHeader({ state }: { state: LiveState }) {
  const badge =
    state.status === "full_time"
      ? "FT"
      : state.status === "half_time"
        ? "HT"
        : statusLabel(state.status) === "LIVE"
          ? state.display
          : state.display;

  return (
    <section className="match-header" aria-label="Match score">
      <p className="match-header__competition">{state.competition ?? "Football"}</p>
      {state.source === "saved" && <p className="match-header__competition">Saved match file · not a live stream</p>}
      <div className="match-header__names">
        <span>{state.home?.name ?? "Home team"}</span>
        <span>{state.away?.name ?? "Away team"}</span>
      </div>
      <div className="match-header__score">
        <span className="score" aria-live="polite">
          {state.score.home} – {state.score.away}
        </span>
        <span className="minute">{badge}</span>
      </div>
    </section>
  );
}
