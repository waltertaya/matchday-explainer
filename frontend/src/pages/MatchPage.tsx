import { useEffect, useState } from "react";
import {
  fetchMatchState,
  subscribeMatch,
  type LiveState,
} from "../lib/live";
import { MatchHeader } from "../components/MatchHeader";
import { MatchTabs, type MatchTab } from "../components/MatchTabs";
import { SummaryTab } from "../components/SummaryTab";
import { StatsTab } from "../components/StatsTab";
import { EventsTab } from "../components/EventsTab";

export function MatchPage({
  matchId,
  onBack,
}: {
  matchId: string;
  onBack: () => void;
}) {
  const [state, setState] = useState<LiveState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<MatchTab>("catch-up");
  const [joinedAt, setJoinedAt] = useState<number | null>(null);
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    let alive = true;
    let unsubscribe: (() => void) | undefined;

    fetchMatchState(matchId)
      .then((initial) => {
        if (!alive) return;
        setError(null);
        // "Since I joined" starts at the minute the screen was opened.
        setJoinedAt(initial.minute);
        setState(initial);
        // Live updates: every state change in Redis is pushed over SSE.
        unsubscribe = subscribeMatch(matchId, (next) => {
          if (!alive) return;
          setConnected(true);
          // A new replay can legitimately restart at a lower sequence number.
          setState(next);
        }, () => { if (alive) setConnected(false); });
      })
      .catch((e) => {
        if (alive) setError(String(e.message ?? e));
      });

    return () => {
      alive = false;
      unsubscribe?.();
    };
  }, [matchId]);

  if (error) {
    return (
      <>
        <p className="hero__tagline">
          No live state for this match ({error}). It may not have streamed
          through the pipeline yet.
        </p>
        <button className="back-btn" onClick={onBack}>
          All live matches
        </button>
      </>
    );
  }

  if (!state) {
    return <p className="hero__tagline">Loading live match…</p>;
  }

  return (
    <div className="match-experience">
      <header className="experience-heading">
        <h1>{tab === "catch-up" ? "Catch me up" : tab === "stats" ? "Tap any stat" : "Why that whistle?"}</h1>
        <p>{tab === "catch-up" ? "A summary for any minute of the match" : tab === "stats" ? "Plain-language explanations for every number" : "The law behind each referee decision"}</p>
      </header>
      <MatchHeader state={state} />
      {!connected && <p className="explanation-status" role="status">Live connection interrupted. Reconnecting automatically…</p>}
      <MatchTabs active={tab} onChange={setTab} />

      {tab === "catch-up" && (
        <SummaryTab state={state} joinedAt={joinedAt ?? state.minute} />
      )}
      {tab === "stats" && <StatsTab state={state} />}
      {tab === "whistle" && <EventsTab state={state} />}

      <p className="colophon">
        Match facts from the event stream. Rules from the IFAB Laws.
        Explains the rule, not a verdict on the call.
      </p>
    </div>
  );
}
