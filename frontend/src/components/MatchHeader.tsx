import type { Match } from "../types";

/** Dark green scoreboard header from the product screens. */
export function MatchHeader({ match }: { match: Match }) {
  return (
    <section className="match-header" aria-label="Match score">
      <div className="match-header__names">
        <span>{match.home.name}</span>
        <span>{match.away.name}</span>
      </div>
      <div className="match-header__score">
        <span className="score" aria-live="polite">
          {match.homeScore} – {match.awayScore}
        </span>
        <span className="minute">{match.minute}'</span>
      </div>
    </section>
  );
}
