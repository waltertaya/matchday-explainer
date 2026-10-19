import type { EventLike, MatchSpec } from "./matches-types";

/* ------------------------------------------------------------------
   Dummy fixtures. All copy here (scores, stat lines, plain-language
   sentences) is illustrative mock data that will be replaced by the
   match-state service.
------------------------------------------------------------------ */

const e = (
  minute: number,
  type: EventLike["type"],
  side: EventLike["side"],
  label: string,
  sentence: string,
): EventLike => ({ minute, type, side, label, sentence });

export const matchSpecs: MatchSpec[] = [
  // ---- Flagship match (matches the design copy) ---------------------
  {
    id: "northgate-harbour",
    competition: "Premier North",
    home: { name: "Northgate FC", short: "NFC" },
    away: { name: "Harbour United", short: "HBU" },
    status: "live",
    minute: 43,
    homeScore: 1,
    awayScore: 1,
    kickoff: "15:00",
    joinedAt: 23,
    stats: {
      possession: { home: 46, away: 54, format: "percent" },
      xg: { home: 0.57, away: 0.49, format: "number" },
      shots: { home: 7, away: 4, format: "number" },
      fouls: { home: 3, away: 11, format: "number" },
    },
    events: [
      e(
        10,
        "goal",
        "away",
        "Goal, Harbour United",
        "Harbour United scored first, on 10'.",
      ),
      e(
        12,
        "goal",
        "home",
        "Goal, Northgate FC",
        "Northgate levelled two minutes later.",
      ),
      e(
        27,
        "yellow-card",
        "home",
        "Yellow card, Northgate FC",
        "Northgate picked up a yellow card on 27' for a late challenge.",
      ),
      e(
        39,
        "free-kick",
        "away",
        "Free kick won, Harbour United",
        "Harbour United won a free kick on 39'.",
      ),
      e(
        41,
        "foul",
        "away",
        "Foul by a Harbour player",
        "On 41' a Harbour player was penalised for a challenge, and Northgate had a free kick.",
      ),
      e(
        43,
        "injury",
        "away",
        "Injury delay, Harbour United",
        "Play paused on 43' for an injury to a Harbour player.",
      ),
    ],
    inThisMatch: {
      possession:
        "Harbour United have had more of the ball (54%), but Northgate have had more shots (7 to 4).",
      xg: "Together the teams have 1.06 xG, but two goals have gone in. That is more than the chances alone suggest.",
      shots: "Northgate lead the shot count 7 to 4, though Harbour's chances came from better positions.",
      fouls:
        "Harbour United have been penalised 11 times to Northgate's 3, which is why free kicks have kept coming.",
    },
  },

  // ---- More live matches (dummy) ------------------------------------
  {
    id: "riverside-kingsbridge",
    competition: "Premier North",
    home: { name: "Riverside Athletic", short: "RSA" },
    away: { name: "Kingsbridge Town", short: "KBT" },
    status: "live",
    minute: 67,
    homeScore: 2,
    awayScore: 0,
    kickoff: "14:30",
    joinedAt: 51,
    stats: {
      possession: { home: 58, away: 42, format: "percent" },
      xg: { home: 1.84, away: 0.31, format: "number" },
      shots: { home: 14, away: 5, format: "number" },
      fouls: { home: 6, away: 9, format: "number" },
    },
    events: [
      e(21, "goal", "home", "Goal, Riverside Athletic", "Riverside Athletic went ahead on 21'."),
      e(38, "goal", "home", "Goal, Riverside Athletic", "Riverside added a second on 38'."),
      e(52, "penalty", "away", "Penalty check, VAR", "On 52' the referee checked a possible Kingsbridge penalty on the screen, and play continued."),
      e(60, "substitution", "home", "Substitution, Riverside Athletic", "Riverside made a change on 60' to freshen up midfield."),
      e(65, "corner", "away", "Corner, Kingsbridge Town", "Kingsbridge won their first corner on 65'."),
    ],
  },

  {
    id: "vale-ashford",
    competition: "Premier North",
    home: { name: "Vale Rovers", short: "VLR" },
    away: { name: "Ashford City", short: "ASH" },
    status: "live",
    minute: 12,
    homeScore: 0,
    awayScore: 0,
    kickoff: "15:15",
    joinedAt: 6,
    stats: {
      possession: { home: 49, away: 51, format: "percent" },
      xg: { home: 0.22, away: 0.18, format: "number" },
      shots: { home: 2, away: 1, format: "number" },
      fouls: { home: 2, away: 1, format: "number" },
    },
    events: [
      e(4, "offside", "home", "Offside, Vale Rovers", "Vale Rovers had an early goal disallowed for offside on 4'."),
      e(9, "corner", "home", "Corner, Vale Rovers", "Vale Rovers forced a corner on 9'."),
      e(11, "foul", "home", "Foul by a Vale player", "A Vale player conceded a free kick on 11' for a trailing arm in a challenge."),
    ],
  },

  {
    id: "eastmoor-stonebrook",
    competition: "Championship",
    home: { name: "Eastmoor Wanderers", short: "EMW" },
    away: { name: "Stonebrook United", short: "STU" },
    status: "live",
    minute: 55,
    homeScore: 1,
    awayScore: 2,
    kickoff: "14:00",
    joinedAt: 40,
    stats: {
      possession: { home: 61, away: 39, format: "percent" },
      xg: { home: 1.12, away: 1.4, format: "number" },
      shots: { home: 11, away: 6, format: "number" },
      fouls: { home: 8, away: 12, format: "number" },
    },
    events: [
      e(14, "goal", "away", "Goal, Stonebrook United", "Stonebrook United struck first on 14'."),
      e(29, "goal", "home", "Goal, Eastmoor Wanderers", "Eastmoor Wanderers pulled level on 29'."),
      e(33, "goal", "away", "Goal, Stonebrook United", "Stonebrook went back in front on 33'."),
      e(47, "yellow-card", "away", "Yellow card, Stonebrook United", "Stonebrook were booked on 47' to slow down the restart."),
      e(54, "injury", "home", "Injury delay, Eastmoor Wanderers", "Play paused on 54' while an Eastmoor player was treated."),
    ],
  },

  // ---- Not live yet --------------------------------------------------
  {
    id: "redcliffe-fallowford",
    competition: "Premier North",
    home: { name: "Redcliffe Rangers", short: "RCR" },
    away: { name: "Fallowford FC", short: "FWF" },
    status: "scheduled",
    minute: 0,
    homeScore: 0,
    awayScore: 0,
    kickoff: "20:00",
    joinedAt: 0,
    stats: {
      possession: { home: 0, away: 0, format: "percent" },
      xg: { home: 0, away: 0, format: "number" },
      shots: { home: 0, away: 0, format: "number" },
      fouls: { home: 0, away: 0, format: "number" },
    },
    events: [],
  },
  {
    id: "highgate-marsh",
    competition: "Championship",
    home: { name: "Highgate Comets", short: "HGC" },
    away: { name: "Marsh End", short: "MRE" },
    status: "scheduled",
    minute: 0,
    homeScore: 0,
    awayScore: 0,
    kickoff: "18:30",
    joinedAt: 0,
    stats: {
      possession: { home: 0, away: 0, format: "percent" },
      xg: { home: 0, away: 0, format: "number" },
      shots: { home: 0, away: 0, format: "number" },
      fouls: { home: 0, away: 0, format: "number" },
    },
    events: [],
  },
];
