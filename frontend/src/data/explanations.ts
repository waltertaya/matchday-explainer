import type {
  Audience,
  EventType,
  LawDetail,
  StatExplanation,
} from "../types";

/**
 * Stat explainer glossary ("Tap any stat").
 * One entry per stat row; the copy is per audience level and each
 * match contributes the "In this match" context from its own data.
 */
export const statExplanations: StatExplanation[] = [
  {
    statId: "possession",
    whatItIs: {
      "new-fan":
        "The share of time each team controlled the ball while it was in play. The two sides always add up to 100%.",
      regular:
        "Ball control measured while play is live. More possession usually means more attacking chances, but a team can win while having less of it.",
      analyst:
        "Live-share estimate of ball control, weighted toward open-play sequences. Pair with field tilt and passes per defensive action to judge whether control is productive.",
    },
    inThisMatchOverride:
      "placeholder — replaced per match in data/matches.ts",
  },
  {
    statId: "xg",
    whatItIs: {
      "new-fan":
        "A score from 0 to 1 for how likely each shot was to become a goal. Add them up for a team's total.",
      regular:
        "Expected goals: every chance gets a 0–1 likelihood of scoring based on where and how it was taken. Totals show how good a team's chances were, not just how many.",
      analyst:
        "xG sums shot conversion probabilities from chance history. Compare team xG against actual goals to read over- or under-performance of the finishing, as this match demonstrates.",
    },
    inThisMatchOverride: "placeholder — replaced per match in data/matches.ts",
  },
  {
    statId: "shots",
    whatItIs: {
      "new-fan":
        "How many attempts each team has had at goal. Shots from promising positions are more likely to score than shots from far out.",
      regular:
        "Any attempt on goal counts. Watch shots along with xG: 4 shots from close range can outweigh 7 from distance.",
      analyst:
        "Shot volume without location is noisy. Compare against shot-on-target share and xG per shot to see quality: this match shows a lower-volume, higher-quality pattern.",
    },
    inThisMatchOverride: "placeholder — replaced per match in data/matches.ts",
  },
  {
    statId: "fouls",
    whatItIs: {
      "new-fan":
        "How many times each team was called for breaking the rules. The referee gives a free kick against the team that fouled.",
      regular:
        "A foul is play stopped for an unfair challenge. One-sided foul counts often mean the team committing them is chasing the game or under sustained pressure.",
      analyst:
        "Foul count is pressure- and game-state dependent. A large skew usually tracks possession conceded; check card timing to see whether challenges are getting more desperate.",
    },
    inThisMatchOverride: "placeholder — replaced per match in data/matches.ts",
  },
];

/**
 * Referee explanations ("Why that whistle?"), per event type.
 * Sourced from the IFAB Laws of the Game — this is where Referee RAG
 * (Azure AI Search over the Laws) would return the law behind each call.
 */
export const lawDetails: Record<EventType, LawDetail> = {
  goal: {
    title: "Was that a good goal?",
    body: "A goal is awarded when the whole of the ball crosses the whole of the goal line, between the posts and under the crossbar, provided no offence was committed in the build-up.",
    source: "IFAB Laws of the Game, Law 10",
  },
  foul: {
    title: "Why a free kick?",
    body: "A direct free kick is given when a player challenges an opponent carelessly, recklessly or with excessive force.",
    legend: [
      { swatch: "#8fb3a4", term: "Careless", outcome: "Free kick" },
      { swatch: "#e7b737", term: "Reckless", outcome: "Yellow card" },
      { swatch: "#c94f42", term: "Excessive force", outcome: "Red card" },
    ],
    source: "IFAB Laws of the Game, Law 12",
  },
  "yellow-card": {
    title: "Why a yellow card?",
    body: "A player is cautioned (yellow card) for unsporting behaviour such as a reckless challenge, delaying the restart, dissent or tactical fouls that stop a promising attack.",
    legend: [
      { swatch: "#8fb3a4", term: "Careless", outcome: "Free kick" },
      { swatch: "#e7b737", term: "Reckless", outcome: "Yellow card" },
      { swatch: "#c94f42", term: "Excessive force", outcome: "Red card" },
    ],
    source: "IFAB Laws of the Game, Law 12",
  },
  "free-kick": {
    title: "Why a free kick?",
    body: "A free kick restarts play after an offence. Direct free kicks may result in a goal at once; indirect free kicks need the ball touched by another player first.",
    source: "IFAB Laws of the Game, Law 13",
  },
  injury: {
    title: "Why the delay?",
    body: "Play is stopped while a player receives treatment on the field, and that lost time is added back at the end of the half or match by the referee or the fourth official.",
    source: "IFAB Laws of the Game, Law 7",
  },
  corner: {
    title: "Why a corner?",
    body: "A corner kick is awarded when the ball goes over the goal line after last being touched by a player from the defending team.",
    source: "IFAB Laws of the Game, Law 16",
  },
  offside: {
    title: "Why offside?",
    body: "A player is offside if they are nearer to the opponents' goal line than both the ball and the second-last opponent at the moment the ball is played to them, and then become involved in play.",
    source: "IFAB Laws of the Game, Law 11",
  },
  substitution: {
    title: "Why a substitution?",
    body: "A team may replace players from its bench with the referee's permission. Play restarts after the replaced player has left the field.",
    source: "IFAB Laws of the Game, Law 3",
  },
  penalty: {
    title: "Why a penalty?",
    body: "A penalty kick is awarded when a team commits a direct free kick offence inside its own penalty area.",
    source: "IFAB Laws of the Game, Law 14",
  },
  var: {
    title: "Why the wait?",
    body: "In a VAR review, the referee checks the pitchside monitor or watches a replay to confirm or overturn a decision on goals, penalties, red cards and mistaken identity.",
    source: "IFAB Laws of the Game, VAR protocol",
  },
};

export const AUDIENCES: Audience[] = ["new-fan", "regular", "analyst"];
