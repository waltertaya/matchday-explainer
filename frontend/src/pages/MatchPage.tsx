import { useState } from "react";
import { getBundle } from "../data/bundles";
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
  const bundle = getBundle(matchId);
  const [tab, setTab] = useState<MatchTab>("catch-up");

  if (!bundle) {
    return (
      <>
        <p className="hero__tagline">Match not found.</p>
        <button className="back-btn" onClick={onBack}>Back to live matches</button>
      </>
    );
  }

  const { match, detail } = bundle;

  return (
    <>
      <MatchHeader match={match} />
      <MatchTabs active={tab} onChange={setTab} />

      {tab === "catch-up" && <SummaryTab bundle={bundle} detail={detail} />}
      {tab === "stats" && (
        <StatsTab
          statRows={detail.statRows}
          explanations={detail.statExplanations}
        />
      )}
      {tab === "whistle" && (
        <EventsTab events={detail.events} laws={detail.laws} />
      )}

      <p className="colophon">
        Every claim is checked against the event stream. Explains the rule, not
        a verdict on the call.
      </p>
    </>
  );
}
