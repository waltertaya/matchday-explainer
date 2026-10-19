/**
 * Dummy text generator for the "Catch me up" summary window —
 * deterministic copy assembled from the event stream and stat line.
 * The summary service (Azure OpenAI + grounding verifier) replaces
 * this later; components only rely on the `MatchSummary` shape.
 */
import { eventsUpTo } from "../data/bundles";
import type {
  MatchBundle,
  MatchDetail,
  MatchEvent,
  MatchSummary,
  SummaryWindow,
} from "../types";

export const eventsUpToMinute = (detail: MatchDetail, minute: number) =>
  eventsUpTo(detail.events, minute);

export function timelineMarkers(detail: MatchDetail) {
  return detail.events
    .filter((ev) => ev.type === "goal" || ev.type === "injury" || ev.type === "var")
    .map((ev) => ({
      minute: ev.minute,
      kind: ev.type === "goal" ? ("goal" as const) : ("stoppage" as const),
    }))
    .filter((m, i, arr) => arr.findIndex((x) => x.minute === m.minute) === i)
    .sort((a, b) => a.minute - b.minute);
}

const teamName = (bundle: MatchBundle, side: "home" | "away") =>
  side === "home" ? bundle.match.home.name : bundle.match.away.name;

export function buildSummary(
  bundle: MatchBundle,
  detail: MatchDetail,
  minute: number,
  win: SummaryWindow,
): MatchSummary {
  const { match } = bundle;
  const all = detail.events;

  const paragraphs =
    win === "last-10"
      ? lastTen(match, all, minute)
      : win === "since-joined"
        ? sinceJoined(bundle, all, minute, detail.joinedAt)
        : sinceKickoff(bundle, detail, all, minute);

  return {
    title: titleFor(win, minute, detail.joinedAt),
    paragraphs,
    claims: upToClaims(minute, all),
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

/* --- window builders ------------------------------------------------ */

function sinceKickoff(
  bundle: MatchBundle,
  detail: MatchDetail,
  all: MatchEvent[],
  minute: number,
): string[] {
  const { match } = bundle;
  const upTo = eventsUpTo(all, minute);
  const goals = upTo.filter((ev) => ev.type === "goal");

  let scored: string;
  if (goals.length >= 2) {
    const [first, second] = goals;
    const gap = second.minute - first.minute;
    scored = `${teamName(bundle, first.side)} scored first, on ${first.minute}'. ${teamName(
      bundle,
      second.side,
    )} ${gap === 2 ? "levelled two minutes later" : `${gap === 1 ? "levelled a minute later" : `levelled ${gap} minutes later`}`}.`;
  } else if (goals.length === 1) {
    const g = goals[0];
    scored = `${teamName(bundle, g.side)} lead through their ${g.minute}' strike.`;
  } else {
    scored = `It is still ${match.homeScore}–${match.awayScore} at ${minute}'.`;
  }

  const possessionLine =
    detail.statExplanations.find((ex) => ex.statId === "possession")
      ?.inThisMatchOverride ?? "";

  const stoppage = [...upTo]
    .reverse()
    .find((ev) => ev.type === "injury" || ev.type === "var");
  const stoppageLine =
    stoppage && minute - stoppage.minute <= 15 ? ` ${stoppage.sentence}` : "";

  return [scored, `${possessionLine}${stoppageLine}`.trim()].filter(Boolean);
}

function lastTen(
  match: MatchBundle["match"],
  all: MatchEvent[],
  minute: number,
): string[] {
  const from = Math.max(0, minute - 10);
  const slice = eventsUpTo(all, minute).filter((ev) => ev.minute > from);

  const story =
    slice.length > 0
      ? slice.map((ev) => ev.sentence).join(" ")
      : `The last ten minutes, to ${minute}', brought no major stoppages or goals.`;

  return [story, `The clock reads ${minute}' and ${match.competition} play continues.`];
}

function sinceJoined(
  bundle: MatchBundle,
  all: MatchEvent[],
  minute: number,
  joinedAt: number,
): string[] {
  const upTo = eventsUpTo(all, minute);
  const slice = upTo.filter((ev) => ev.minute > joinedAt);
  const goalCount = (side: "home" | "away") =>
    eventsUpTo(all, joinedAt).filter((ev) => ev.type === "goal" && ev.side === side).length;

  const story =
    slice.length > 0
      ? slice.map((ev) => ev.sentence).join(" ")
      : `Since then the game has settled into a steady rhythm, with ${bundle.match.away.name} seeing more of the ball.`;

  return [
    `You joined on ${joinedAt}' with the score at ${bundle.match.home.name} ${goalCount("home")}–${goalCount("away")} ${bundle.match.away.name}.`,
    story,
  ];
}

/* --- claims ---------------------------------------------------------- */

function upToClaims(minute: number, events: MatchEvent[]) {
  const upTo = eventsUpTo(events, minute);
  const total = Math.min(upTo.length, 8);
  // Every generated sentence is grounded on an event, so all claims verify.
  return { verified: total, total };
}
