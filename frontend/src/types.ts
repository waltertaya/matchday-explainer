/**
 * Domain types for Matchday Explainer.
 *
 * These intentionally mirror what a match-state / events backend would
 * expose (see architecture: match events -> match state -> fan experience),
 * so swapping the dummy data in `src/data/` for real API calls later
 * should not require touching the components.
 */

export type TeamSide = "home" | "away";

export interface Team {
  name: string;
  short: string;
}

export type MatchStatus = "live" | "scheduled" | "finished";

export interface Match {
  id: string;
  competition: string;
  home: Team;
  away: Team;
  status: MatchStatus;
  /** Current minute of play (live / finished matches) */
  minute: number;
  homeScore: number;
  awayScore: number;
  /** Kick-off time as a display string, e.g. "18:30" */
  kickoff: string;
}

export type EventType =
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

export interface MatchEvent {
  id: string;
  minute: number;
  type: EventType;
  /** Short label shown in the "Match events" list */
  label: string;
  /** Which side of the fixture this event is for */
  side: TeamSide;
  /**
   * Pre-written plain-language sentence used by the summariser.
   * (Later this is what the summary service would stream; for now it is dummy copy.)
   */
  sentence: string;
}

/** A single row in the "Tap any stat" screen */
export interface StatRow {
  id: string;
  /** Short label, e.g. "xG" */
  label: string;
  /** Longer name used in the explainer title, e.g. "expected goals" */
  name: string;
  homeValue: number;
  awayValue: number;
  /** Format hint: "percent" renders 46%, "number" renders plain */
  format: "percent" | "number";
}

export type Audience = "new-fan" | "regular" | "analyst";

export interface StatExplanation {
  statId: string;
  /** "What it is" copy, per audience level */
  whatItIs: Record<Audience, string>;
  /** "In this match" copy tied to the current match */
  inThisMatchOverride?: string;
}

/**
 * The law explanation behind a referee decision (Referee RAG output).
 */
export interface LawDetail {
  /** Question-style title, e.g. "Why a free kick?" */
  title: string;
  body: string;
  /** Optional severity table (Careless / Reckless / Excessive force) */
  legend?: Array<{ swatch: string; term: string; outcome: string }>;
  /** Citation, e.g. "IFAB Laws of the Game, Law 12" */
  source: string;
}

export type SummaryWindow = "since-kickoff" | "last-10" | "since-joined";

export interface MatchSummary {
  title: string;
  paragraphs: string[];
  claims: { verified: number; total: number };
}

export interface TimelineMarker {
  minute: number;
  kind: "goal" | "stoppage";
}

export interface MatchDetail {
  matchId: string;
  statRows: StatRow[];
  statExplanations: StatExplanation[];
  events: MatchEvent[];
  laws: Record<EventType, LawDetail>;
  /** Minute the viewer "joined" the stream (drives the "Since I joined" window) */
  joinedAt: number;
}

export interface MatchBundle {
  match: Match;
  detail: MatchDetail;
}
