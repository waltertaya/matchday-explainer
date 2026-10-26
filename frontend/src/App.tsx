import { useEffect, useState } from "react";
import { MatchesPage } from "./pages/MatchesPage";
import { MatchPage } from "./pages/MatchPage";

function FootballIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zm0 2.5 3 2.2-1.1 3.6h-3.8L9 8.7zm-5.1 7 .1 1.7a6.5 6.5 0 0 0 1.9 2.4l1.6-1.4h3l1.6 1.4a6.5 6.5 0 0 0 1.9-2.4l.1-1.7-2.2-1-4.8 0z" />
    </svg>
  );
}

export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  const routeMatch = /^#\/matches\/([^/]+)$/.exec(hash);
  let matchId: string | null = null;
  try { matchId = routeMatch ? decodeURIComponent(routeMatch[1]) : null; } catch { /* invalid link returns to list */ }
  const goBack = () => { window.location.hash = "/"; };

  useEffect(() => {
    const change = () => setHash(window.location.hash);
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [matchId]);

  return (
    <div className="page">
      <header className="app-bar">
        <div className="app-bar__inner">
          {matchId ? (
            <button
              type="button"
              className="back-btn"
              onClick={goBack}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M15.4 4.6 14 3.2 5.2 12l8.8 8.8 1.4-1.4L8 12z" />
              </svg>
              All matches
            </button>
          ) : (
            <span className="brand">
              <span className="brand__crest">
                <FootballIcon />
              </span>
              Matchday Explainer
            </span>
          )}
        </div>
      </header>

      <main className="page-main">
        {!matchId && (
          <MatchesPage
            onOpenMatch={(id) => {
              window.location.hash = `/matches/${encodeURIComponent(id)}`;
            }}
          />
        )}
        {matchId && (
          <MatchPage
            key={matchId}
            matchId={matchId}
            onBack={goBack}
          />
        )}
      </main>
    </div>
  );
}
