/**
 * Shared shape used by the dummy match specs in matchData.ts.
 */

export interface EventLike {
  minute: number;
  type:
    | "goal"
    | "yellow-card"
    | "foul"
    | "free-kick"
    | "injury"
    | "corner"
    | "offside"
    | "substitution"
    | "penalty"
    | "var";
  side: "home" | "away";
  label: string;
  sentence: string;
}

export interface StatSpec {
  home: number;
  away: number;
  format: "percent" | "number";
}

export interface MatchSpec {
  id: string;
  competition: string;
  home: { name: string; short: string };
  away: { name: string; short: string };
  status: "live" | "scheduled" | "finished";
  minute: number;
  homeScore: number;
  awayScore: number;
  kickoff: string;
  joinedAt: number;
  stats: Record<string, StatSpec>;
  events: EventLike[];
  /** Optional per-stat "In this match" copy; defaults to a generated line. */
  inThisMatch?: Record<string, string>;
}
