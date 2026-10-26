/**
 * Live data layer — talks to the Flask API (Redis-backed match state)
 * and subscribes to Server-Sent Events pushed by the state builder.
 *
 * Replaces the old dummy-data module: cards and match screens render
 * from the Event Hubs -> Redis pipeline.
 */

export interface TeamRef {
  name: string;
  short: string;
}

export interface TimelineEvent {
  seq: number;
  minute: number;
  display: string;
  event_type: string;
  side: "home" | "away";
  team: string;
  player: string;
  label: string;
  detail: Record<string, unknown>;
}

export interface SideValues {
  home: number;
  away: number;
}

export interface MatchStats {
  possession: SideValues;
  shots: SideValues;
  shots_on_target: SideValues;
  xg: SideValues;
  fouls: SideValues;
  corners: SideValues;
  yellow_cards: SideValues;
  red_cards: SideValues;
  offsides: SideValues;
}

export type MatchStatus = "pre_match" | "live" | "half_time" | "full_time";

export interface LiveMatch {
  source?: "live" | "saved";
  match_id: string;
  home: TeamRef;
  away: TeamRef;
  competition: string | null;
  status: MatchStatus;
  minute: number;
  display: string;
  score: SideValues;
  updated_at: string | null;
}

export interface LiveState extends LiveMatch {
  venue: string | null;
  referee: string | null;
  weather: string | null;
  attendance: number | null;
  period: string | null;
  stats: MatchStats;
  timeline: TimelineEvent[];
  last_seq: number;
}

const API = "/api/v1";

export async function fetchMatches(): Promise<LiveMatch[]> {
  const res = await fetch(`${API}/matches`);
  if (!res.ok) throw new Error(`matches: ${res.status}`);
  const body = await res.json();
  return body.matches as LiveMatch[];
}

export async function fetchMatchState(matchId: string): Promise<LiveState> {
  const res = await fetch(`${API}/matches/${encodeURIComponent(matchId)}/state`);
  if (!res.ok) throw new Error(`state: ${res.status}`);
  return (await res.json()) as LiveState;
}

/**
 * Subscribe to live state updates via SSE. Returns a cleanup function.
 * EventSource reconnects automatically; each message is a full snapshot.
 */
export function subscribeMatch(
  matchId: string,
  onState: (state: LiveState) => void,
  onError?: (err: Event) => void,
): () => void {
  const es = new EventSource(`${API}/matches/${encodeURIComponent(matchId)}/stream`);
  es.addEventListener("state", (ev) => {
    try {
      onState(JSON.parse((ev as MessageEvent).data) as LiveState);
    } catch {
      /* ignore malformed frames */
    }
  });
  if (onError) es.onerror = onError;
  return () => es.close();
}

/* ----------------------------------------------------------------------
   View-model helpers for the three match screens
---------------------------------------------------------------------- */

export function statRowsFromState(state: LiveState) {
  const s = state.stats;
  return [
    { id: "possession", label: "Possession", home: s.possession.home, away: s.possession.away, format: "percent" as const },
    { id: "xg", label: "xG", home: s.xg.home, away: s.xg.away, format: "xg" as const },
    { id: "shots", label: "Shots", home: s.shots.home, away: s.shots.away, format: "number" as const },
    { id: "shots_on_target", label: "On target", home: s.shots_on_target.home, away: s.shots_on_target.away, format: "number" as const },
    { id: "fouls", label: "Fouls", home: s.fouls.home, away: s.fouls.away, format: "number" as const },
    { id: "corners", label: "Corners", home: s.corners.home, away: s.corners.away, format: "number" as const },
    { id: "yellow_cards", label: "Yellow cards", home: s.yellow_cards.home, away: s.yellow_cards.away, format: "number" as const },
    { id: "red_cards", label: "Red cards", home: s.red_cards.home, away: s.red_cards.away, format: "number" as const },
    { id: "offsides", label: "Offsides", home: s.offsides.home, away: s.offsides.away, format: "number" as const },
  ];
}

export function formatStat(value: number, format: "percent" | "xg" | "number") {
  if (format === "percent") return `${Math.round(value)}%`;
  if (format === "xg") return value.toFixed(2);
  return String(value);
}

/** "In this match" copy generated from the live numbers. */
export function inMatchLine(statId: string, state: LiveState): string {
  const h = state.home?.name ?? "The home side";
  const a = state.away?.name ?? "the away side";
  const row = statRowsFromState(state).find((stat) => stat.id === statId);
  if (!row) return "";
  if (statId === "xg") {
    const total = state.stats.xg.home + state.stats.xg.away;
    const goals = state.score.home + state.score.away;
    return `${h}: ${row.home.toFixed(2)} xG. ${a}: ${row.away.toFixed(2)} xG. Together: ${total.toFixed(2)} xG, with ${goals} goals recorded. Expected goals is not a prediction of the score.`;
  }
  return `${h}: ${formatStat(row.home, row.format)}. ${a}: ${formatStat(row.away, row.format)}.`;
}

/** Events shown in the "Why that whistle?" list (design's Match events). */
export function whistleEvents(state: LiveState): TimelineEvent[] {
  return state.timeline.filter(
    (ev) => ev.event_type !== "shot" || ev.detail?.outcome === "goal",
  );
}

export function lawForEvent(ev: TimelineEvent): string {
  switch (ev.event_type) {
    case "shot":
      return "goal";
    case "foul":
      return ev.detail?.consequence === "penalty" ? "penalty" : "foul";
    case "card":
      return ev.detail?.card === "red" ? "red-card" : "yellow-card";
    case "yellow-card":
    case "red-card":
    case "penalty":
    case "goal":
    case "free-kick":
      return ev.event_type;
    case "injury":
      return "injury";
    case "substitution":
      return "substitution";
    case "corner":
      return "corner";
    case "offside":
      return "offside";
    case "var":
      return "var";
    default:
      return "foul";
  }
}

export function timelineMarkers(state: LiveState) {
  const seen = new Set<number>();
  const markers: Array<{ minute: number; kind: "goal" | "stoppage" }> = [];
  for (const ev of state.timeline) {
    const kind =
      ev.event_type === "shot" && ev.detail?.outcome === "goal"
        ? ("goal" as const)
        : ev.event_type === "injury" || ev.event_type === "var"
          ? ("stoppage" as const)
          : null;
    if (kind && !seen.has(ev.minute)) {
      seen.add(ev.minute);
      markers.push({ minute: ev.minute, kind });
    }
  }
  return markers.sort((a, b) => a.minute - b.minute);
}

export function eventsUpTo(state: LiveState, minute: number): TimelineEvent[] {
  return state.timeline.filter((ev) => ev.minute <= minute);
}

export function statusLabel(status: MatchStatus): string {
  switch (status) {
    case "live":
      return "LIVE";
    case "half_time":
      return "HT";
    case "full_time":
      return "FT";
    default:
      return "SOON";
  }
}
