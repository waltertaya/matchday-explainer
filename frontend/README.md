# Matchday Explainer — frontend

React + TypeScript (Vite) front end for Matchday Explainer.

All data is **dummy** and lives in `src/data/` with types in `src/types.ts`,
shaped to mirror the future match-state/event APIs, so connecting the
backend later means replacing the functions in `src/data/bundles.ts`
(`matchCards`, `getBundle`) with API calls — components don't need to change.

## Screens

1. **Live matches** (`src/pages/MatchesPage.tsx`) — the entry list. Live
   fixtures (score, minute, pulse) open a match screen on click; scheduled
   fixtures are listed under "Starting soon".
2. **Match screens** (`src/pages/MatchPage.tsx`) — three tabs:
   - **Catch me up** — plain-language summary with *Since kick-off / Last 10
     min / Since I joined* windows, a time scrubber (Goal/Stoppage markers) and
     the claims-verified grounding badge.
   - **Stats** — tappable stat rows; a sheet explains "What it is" per audience
     (New fan / Regular / Analyst) plus "In this match".
   - **Why that whistle?** — match events; a sheet explains the law behind each
     decision with the IFAB source and a "rule, not a verdict" disclaimer.

## Dev

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production build
npm run lint
```

## Layout notes

Design tokens (colors, spacing, shadows) come from the product mock-ups and
live in `src/index.css` under `:root`. Mobile-first: the match panel is a
single-centered column; cards and sheets widen at `620px / 720px / 980px`
breakpoints; explainer sheets are bottom slides on mobile and centered
dialogs on desktop.

## Connecting a backend later

- `src/data/matchData.ts` — replace the raw fixture specs with API responses.
- `src/data/bundles.ts` — swap the synchronous getters for `fetch` calls
  (consider a tiny React Query layer or context provider).
- `src/lib/summary.ts` — replace the canned summary generator with the
  summary service output (keep the `MatchSummary` shape).
- `vite.config.ts` — add a `server.proxy` entry for the backend when ready.
