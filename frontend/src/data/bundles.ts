/**
 * Derived view models per match (list card, detail bundle).
 * Everything here currently reads from dummy specs; pointing these
 * functions at the backend is the only change needed later.
 */
import {
  lawDetails,
  statExplanations,
} from "./explanations";
import { matchSpecs } from "./matchData";
import type { EventLike, MatchSpec, StatSpec } from "./matches-types";
import type { Match, MatchBundle, MatchDetail } from "../types";

export interface MatchCard {
  match: Match;
}

export const matchCards: MatchCard[] = matchSpecs.map((spec) => ({
  match: toMatch(spec),
}));

function toMatch(spec: MatchSpec): Match {
  return {
    id: spec.id,
    competition: spec.competition,
    home: spec.home,
    away: spec.away,
    status: spec.status,
    minute: spec.minute,
    homeScore: spec.homeScore,
    awayScore: spec.awayScore,
    kickoff: spec.kickoff,
  };
}

export function getMatchCard(id: string): MatchCard | undefined {
  return matchCards.find((c) => c.match.id === id);
}

const STAT_NAMES: Record<string, { label: string; name: string }> = {
  possession: { label: "Possession", name: "Ball possession" },
  xg: { label: "xG", name: "expected goals" },
  shots: { label: "Shots", name: "shots on goal" },
  fouls: { label: "Fouls", name: "fouls conceded" },
};

const bundles = new Map<string, MatchBundle>(
  matchSpecs.map((spec) => [spec.id, toBundle(spec)]),
);

function toBundle(spec: MatchSpec): MatchBundle {
  return { match: toMatch(spec), detail: toDetail(spec) };
}

function toDetail(spec: MatchSpec): MatchDetail {
  return {
    matchId: spec.id,
    statRows: statRowsFor(spec),
    statExplanations: statExplanations.map((ex) => ({
      ...ex,
      whatItIs: { ...ex.whatItIs },
      inThisMatchOverride:
        spec.inThisMatch?.[ex.statId] ?? inMatchLine(ex.statId, spec),
    })),
    events: spec.events.map((ev, i) => ({
      id: `${spec.id}-e${i}`,
      minute: ev.minute,
      type: ev.type,
      label: ev.label,
      side: ev.side,
      sentence: ev.sentence,
    })),
    laws: lawDetails,
    joinedAt: spec.joinedAt,
  };
}

function statRowsFor(spec: MatchSpec) {
  const rows = Object.entries(spec.stats) as Array<
    [string, StatSpec]
  >;
  return rows.map(([id, s]) => ({
    id,
    label: STAT_NAMES[id]?.label ?? id,
    name: STAT_NAMES[id]?.name ?? id,
    homeValue: s.home,
    awayValue: s.away,
    format: s.format,
  }));
}

function inMatchLine(statId: string, spec: MatchSpec): string {
  const s = spec.stats[statId];
  if (!s) return "";
  const h = spec.home.name;
  const a = spec.away.name;
  switch (statId) {
    case "possession":
      return `${h} have had ${s.home}% of the ball to ${a}'s ${s.away}%.`;
    case "xg": {
      const total = Math.round((s.home + s.away) * 100) / 100;
      const goals = spec.homeScore + spec.awayScore;
      const tail =
        goals > total
          ? ` ${goals} goals have gone in — more than the chances alone suggest.`
          : " The goals so far line up with the quality of the chances.";
      return `Together the teams have ${total} xG.${tail}`;
    }
    case "shots":
      return `The shot count is ${s.home} to ${s.away} between ${h} and ${a}.`;
    case "fouls":
      return `Fouls so far: ${s.home} for ${h}, ${s.away} for ${a}.`;
    default:
      return `${s.home} to ${s.away}.`;
  }
}

export function getBundle(id: string): MatchBundle | undefined {
  return bundles.get(id);
}

export const eventsUpTo = (events: EventLike[], minute: number) =>
  events.filter((ev) => ev.minute <= minute);
