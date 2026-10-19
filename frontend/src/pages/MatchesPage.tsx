import { matchCards } from "../data/bundles";

function initials(name: string) {
  return name
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
  const live = matchCards.filter((c) => c.match.status === "live");
  const upcoming = matchCards.filter((c) => c.match.status === "scheduled");

  return (
    <>
      <header className="hero">
        <h1 className="hero__title">Live matches</h1>
        <p className="hero__tagline">
          Tap a match for plain-language summaries, stat explainers and the law
          behind every whistle.
        </p>
      </header>

      {live.length > 0 && (
        <section aria-labelledby="live-heading">
          <div className="section-head">
            <h2 id="live-heading">Live now</h2>
            <span className="count">{live.length}</span>
          </div>
          <div className="match-grid">
            {live.map(({ match }) => (
              <button
                key={match.id}
                type="button"
                className="match-card"
                onClick={() => onOpenMatch(match.id)}
              >
                <div className="match-card__top">
                  <span className="match-card__comp">
                    {match.competition}
                  </span>
                  <span className="live-pill">
                    <span className="live-dot" aria-hidden="true" />
                    LIVE
                  </span>
                </div>

                <div className="match-card__teams">
                  <div className="team-line">
                    <span className="crest crest--home" aria-hidden="true">
                      {initials(match.home.name)}
                    </span>
                    <span className="team-line__name">{match.home.name}</span>
                    <span className="team-line__score">
                      {match.homeScore}
                    </span>
                  </div>
                  <div className="team-line">
                    <span className="crest crest--away" aria-hidden="true">
                      {initials(match.away.name)}
                    </span>
                    <span className="team-line__name">{match.away.name}</span>
                    <span className="team-line__score">
                      {match.awayScore}
                    </span>
                  </div>
                </div>

                <div className="match-card__foot">
                  <span className="minute-chip">{match.minute}'</span>
                  <span className="cta">Catch me up &rarr;</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {upcoming.length > 0 && (
        <section aria-labelledby="upcoming-heading">
          <div className="section-head">
            <h2 id="upcoming-heading">Starting soon</h2>
          </div>
          <div className="fixture-lines">
            {upcoming.map(({ match }) => (
              <div key={match.id} className="fixture-line">
                <time>{match.kickoff}</time>
                <span className="teams">
                  {match.home.name} vs {match.away.name}
                </span>
                <span className="comp">{match.competition}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <p className="page-note">
        Illustrative mock-ups using synthetic match data.
      </p>
    </>
  );
}
