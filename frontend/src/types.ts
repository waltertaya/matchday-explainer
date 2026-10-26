/**
 * Domain types still owned by the front end: the stat-explainer
 * audience levels and the referee-law glossary. Match/state types
 * live in `lib/live.ts` and mirror the backend's Redis projection.
 */

export type Audience = "new-fan" | "regular" | "analyst";

/** Event-type vocabulary of the live timeline (matches the stream). */
export type EventType =
  | "goal"
  | "shot"
  | "yellow-card"
  | "red-card"
  | "foul"
  | "free-kick"
  | "injury"
  | "corner"
  | "offside"
  | "substitution"
  | "penalty"
  | "var";

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

/** A single row in the "Tap any stat" screen */
export interface StatExplanation {
  statId: string;
  /** "What it is" copy, per audience level */
  whatItIs: Record<Audience, string>;
  /** "In this match" copy tied to the current match */
  inThisMatchOverride?: string;
}
