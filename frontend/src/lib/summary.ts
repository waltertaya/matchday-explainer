/**
 * "Catch me up" summary windows, built from the live event timeline
 * arriving over SSE. The Azure OpenAI summary service will replace this
 * text generation later; the window/minute/claims shape stays the same.
 */
import { eventsUpTo, type LiveState, type TimelineEvent } from "./live";

export type SummaryWindow = "since-kickoff" | "last-10" | "since-joined";

export interface MatchSummary {
  title: string;
  paragraphs: string[];
  claims: { verified: number; total: number };
}

const teamOf = (state: LiveState, side: string) =>
  side === "home" ? state.home?.name : state.away?.name;

const goalsUpTo = (events: TimelineEvent[]) =>
  events.filter(
    (ev) => ev.event_type === "shot" && ev.detail?.outcome === "goal",
  );

export function buildSummary(
  state: LiveState,
  minute: number,
  win: SummaryWindow,
  joinedAt: number,
): MatchSummary {
  const all = state.timeline;
  const upTo = eventsUpTo(state, minute);

  const paragraphs =
    win === "last-10"
      ? lastTen(state, all, minute)
      : win === "since-joined"
        ? sinceJoined(state, all, minute, joinedAt)
        : sinceKickoff(state, upTo, minute);

  const total = Math.min(upTo.length, 8);
  return {
    title: titleFor(win, minute, joinedAt),
    paragraphs,
    claims: { verified: total, total },
  };
}

function titleFor(win: SummaryWindow, minute: number, joinedAt: number) {
  switch (win) {
    case "last-10":
      return `The last ten minutes, to ${minute}'`;
    case "since-joined":
      return `Everything since ${joinedAt}', when you joined`;
    default:
      return `The match so far, to ${minute}'`;
  }
}

/* --- windows --------------------------------------------------------- */

function sinceKickoff(
  state: LiveState,
  upTo: TimelineEvent[],
  minute: number,
): string[] {
  const goals = goalsUpTo(upTo);
  const h = state.home?.name ?? "the home side";
  const a = state.away?.name ?? "the away side";

  let scored: string;
  if (goals.length >= 2) {
    const [first, second] = goals;
    const gap = second.minute - first.minute;
    const gapText =
      gap === 1
        ? "a minute later"
        : gap === 2
          ? "two minutes later"
          : `${gap} minutes later`;
    scored = `${teamOf(state, first.side)} scored first, on ${first.minute}'. ${teamOf(
      state,
      second.side,
    )} levelled ${gapText}.`;
  } else if (goals.length === 1) {
    scored = `${teamOf(state, goals[0].side)} lead through their ${goals[0].minute}' strike.`;
  } else {
    scored = `It is still ${state.score.home}–${state.score.away} at ${minute}'.`;
  }

  const s = state.stats;
  const leader = s.possession.home >= s.possession.away ? h : a;
  const other = leader === h ? a : h;
  const poss = Math.round(
    leader === h ? s.possession.home : s.possession.away,
  );
  const shotLine =
    leader === h
      ? `${h} have had more of the ball (${poss}%), but ${a} have had more shots (${s.shots.away} to ${s.shots.home}).`
      : `${a} have had more of the ball (${poss}%), but ${h} have had more shots (${s.shots.home} to ${s.shots.away}).`;
  void other;

  const stoppages = upTo.filter(
    (ev) => ev.event_type === "injury" || ev.event_type === "var",
  );
  const lastStoppage = stoppages[stoppages.length - 1];
  const stoppageLine =
    lastStoppage && minute - lastStoppage.minute <= 15
      ? ` Play was paused on ${lastStoppage.minute}' — ${lastStoppage.label.toLowerCase()}.`
      : "";

  return [scored, `${shotLine}${stoppageLine}`.trim()];
}

function lastTen(
  state: LiveState,
  all: TimelineEvent[],
  minute: number,
): string[] {
  const from = Math.max(0, minute - 10);
  const slice = all.filter((ev) => ev.minute > from && ev.minute <= minute);

  const story =
    slice.length > 0
      ? slice.map((ev) => `On ${ev.display} — ${ev.label.toLowerCase()}.`).join(" ")
      : `The last ten minutes, to ${minute}', brought no major stoppages or goals.`;

  return [
    story,
    `The clock reads ${minute}' and the ${state.competition ?? "match"} continues.`,
  ];
}

function sinceJoined(
  state: LiveState,
  all: TimelineEvent[],
  minute: number,
  joinedAt: number,
): string[] {
  const goalsAtJoin = goalsUpTo(all.filter((ev) => ev.minute <= joinedAt));
  const joinHome = goalsAtJoin.filter((ev) => ev.side === "home").length;
  const joinAway = goalsAtJoin.length - joinHome;

  const slice = all.filter((ev) => ev.minute > joinedAt && ev.minute <= minute);
  const story =
    slice.length > 0
      ? slice.map((ev) => `On ${ev.display} — ${ev.label.toLowerCase()}.`).join(" ")
      : "Since then the game has settled into a steady rhythm.";

  return [
    `You joined on ${joinedAt}' with the score at ${state.home?.name} ${joinHome}–${joinAway} ${state.away?.name}.`,
    story,
  ];
}
