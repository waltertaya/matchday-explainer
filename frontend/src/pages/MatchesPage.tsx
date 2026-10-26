import { useEffect, useState } from "react";
import {
  fetchMatches,
  statusLabel,
  type LiveMatch,
} from "../lib/live";

function initials(name: string) {
  return (name ?? "")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

export function MatchesPage({
  onOpenMatch,
}: {
  onOpenMatch: (id: string) => void;
}) {
  const [matches, setMatches] = useState<LiveMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetchMatches()
        .then((m) => {
          if (alive) {
            setMatches(m);
            setError(null);
          }
        })
        .catch((e) => {
          if (alive) setError(String(e.message ?? e));
        });
    };
    load();
    const timer = setInterval(load, 4000); // live list refresh
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const live = (matches ?? []).filter(
    (m) => m.status === "live" || m.status === "half_time",
  );
  const finished = (matches ?? []).filter((m) => m.status === "full_time");
  const upcoming = (matches ?? []).filter(
    (m) => m.status !== "live" && m.status !== "half_time" && m.status !== "full_time",
  );

  return (
    <>
      <header className="hero">
        <h1 className="hero__title">Every match. A little clearer.</h1>
        <p className="hero__tagline">
          Tap a match for plain-language summaries, stat explainers and the law
          behind every whistle — updated live from the event stream.
        </p>
      </header>

      {matches === null && !error && <p className="page-note" role="status">Loading matches…</p>}

      {error && (
        <p className="page-note">
          Can't reach the match state API ({error}). Is the backend running?
        </p>
      )}

      {!error && matches !== null && matches.length === 0 && (
        <p className="page-note">
          No matches yet. Save a match file or stream events and the cards
          will appear here automatically.
        </p>
      )}

      {upcoming.length > 0 && (
        <section aria-labelledby="upcoming-heading">
          <div className="section-head">
            <h2 id="upcoming-heading">Upcoming</h2>
            <span className="count">{upcoming.length}</span>
          </div>
          <div className="match-grid">
            {upcoming.map((match) => <LiveCard key={match.match_id} match={match} onOpenMatch={onOpenMatch} />)}
          </div>
        </section>
      )}

      {live.length > 0 && (
        <section aria-labelledby="live-heading">
          <div className="section-head">
            <h2 id="live-heading">Live now</h2>
            <span className="count">{live.length}</span>
          </div>
          <div className="match-grid">
            {live.map((match) => (
              <LiveCard key={match.match_id} match={match} onOpenMatch={onOpenMatch} />
            ))}
          </div>
        </section>
      )}

      {finished.length > 0 && (
        <section aria-labelledby="finished-heading">
          <div className="section-head">
            <h2 id="finished-heading">Finished</h2>
            <span className="count">{finished.length}</span>
          </div>
          <div className="match-grid">
            {finished.map((match) => (
              <LiveCard key={match.match_id} match={match} onOpenMatch={onOpenMatch} />
            ))}
          </div>
        </section>
      )}

      <p className="page-note">
        Live updates and saved matches, all in one place. Select a match to catch up.
      </p>
    </>
  );
}

function LiveCard({
  match,
  onOpenMatch,
}: {
  match: LiveMatch;
  onOpenMatch: (id: string) => void;
}) {
  const badge = statusLabel(match.status);
  const isLive = badge === "LIVE";

  return (
    <button
      type="button"
      className="match-card"
      onClick={() => onOpenMatch(match.match_id)}
    >
      <div className="match-card__top">
        <span className="match-card__comp">{match.competition ?? "Football"}</span>
        <span className={`live-pill${isLive ? "" : " live-pill--dim"}`}>
          {isLive && <span className="live-dot" aria-hidden="true" />}
          {badge}
        </span>
      </div>

      <div className="match-card__teams">
        <div className="team-line">
          <span className="crest crest--home" aria-hidden="true">
            {initials(match.home?.name ?? "Home")}
          </span>
          <span className="team-line__name">{match.home?.name ?? "Home team"}</span>
          <span className="team-line__score">{match.status === "pre_match" ? "–" : match.score.home}</span>
        </div>
        <div className="team-line">
          <span className="crest crest--away" aria-hidden="true">
            {initials(match.away?.name ?? "Away")}
          </span>
          <span className="team-line__name">{match.away?.name ?? "Away team"}</span>
          <span className="team-line__score">{match.status === "pre_match" ? "–" : match.score.away}</span>
        </div>
      </div>

      <div className="match-card__foot">
        <span className="minute-chip">{match.source === "saved" ? "Saved" : match.status === "pre_match" ? "Soon" : match.display}</span>
        <span className="cta">Catch me up &rarr;</span>
      </div>
    </button>
  );
}
