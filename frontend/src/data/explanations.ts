import type { Audience } from "../types";

// UI labels only. Rule content must come from the retrieved IFAB passages.
export const eventTitles: Record<string, string> = {
  goal: "When is a goal awarded?",
  foul: "Why a free kick?",
  "yellow-card": "Why a yellow card?",
  "red-card": "Why a red card?",
  "free-kick": "Why a free kick?",
  injury: "Why the delay?",
  corner: "Why a corner?",
  offside: "Why offside?",
  substitution: "How do substitutions work?",
  penalty: "Why a penalty?",
  var: "Why the wait?",
};

export const AUDIENCES: Audience[] = ["new-fan", "regular", "analyst"];
