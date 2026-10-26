import { useEffect, useState } from "react";
import { PipelineStatus } from "../components/PipelineStatus";
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
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "live" | "saved">("all");

  useEffect(() => {
    let alive = true;
    let loading = false;
    const controller = new AbortController();
    const load = () => {
      if (loading) return;
      loading = true;
      fetchMatches(controller.signal)
        .then((m) => {
          if (alive) {
            setMatches(m);
            setError(null);
          }
        })
        .catch((e) => {
          if (alive) setError(String(e.message ?? e));
        }).finally(() => { loading = false; });
    };
    load();
    const timer = setInterval(load, 4000); // live list refresh
    return () => {
      alive = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  const visible = (matches ?? []).filter((match) => {
    const isLive = match.source !== "saved" && (match.status === "live" || match.status === "half_time");
    const search = `${match.home?.name ?? ""} ${match.away?.name ?? ""} ${match.competition ?? ""}`.toLowerCase();
    return search.includes(query.trim().toLowerCase())
      && (filter === "all" || (filter === "live" ? isLive : match.source === "saved"));
  });
  const live = visible.filter(
    (m) => m.status === "live" || m.status === "half_time",
  );
  const finished = visible.filter((m) => m.status === "full_time");
  const upcoming = visible.filter(
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

      <div className="value-strip" aria-label="What makes Matchday different">
        <span>Catch up in seconds</span><span>Understand the numbers</span><span>Read the law, not a verdict</span>
      </div>
      <PipelineStatus />
      <div className="match-toolbar">
        <label className="match-search"><span className="sr-only">Search teams or competitions</span>
          <input type="search" placeholder="Search teams or competitions" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div className="chip-tabs" role="group" aria-label="Filter matches">
          {([['all', 'All matches'], ['live', 'Live now'], ['saved', 'Saved files']] as const).map(([value, label]) => (
            <button key={value} className={`chip-tab${filter === value ? " is-active" : ""}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>
          ))}
        </div>
      </div>

      {matches === null && !error && <p className="page-note" role="status">Loading matches…</p>}

      {error && (
        <p className="page-note">
          Can't reach the match state API ({error}). Is the backend running?
        </p>
      )}

      {matches && matches.length > 0 && visible.length === 0 && <p className="page-note">No matches match this search or filter.</p>}

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
