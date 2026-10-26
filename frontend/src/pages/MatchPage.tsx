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

  useEffect(() => {
    let alive = true;
    let unsubscribe: (() => void) | undefined;

    fetchMatchState(matchId)
      .then((initial) => {
        if (!alive) return;
        setError(null);
        // "Since I joined" starts at the minute the screen was opened.
        setJoinedAt((prev) => prev ?? initial.minute);
        setState(initial);
        // Live updates: every state change in Redis is pushed over SSE.
        unsubscribe = subscribeMatch(matchId, (next) => {
          setState(next);
        });
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
    <>
      <MatchHeader state={state} />
      <MatchTabs active={tab} onChange={setTab} />

      {tab === "catch-up" && (
        <SummaryTab state={state} joinedAt={joinedAt ?? state.minute} />
      )}
      {tab === "stats" && <StatsTab state={state} />}
      {tab === "whistle" && <EventsTab state={state} />}

      <p className="colophon">
        Every claim is checked against the event stream. Explains the rule, not
        a verdict on the call.
      </p>
    </>
  );
}
