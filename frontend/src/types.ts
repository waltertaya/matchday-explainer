/**
 * Domain types still owned by the front end: the stat-explainer
 * audience levels and event vocabulary. Match/state types
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
