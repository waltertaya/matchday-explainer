# Matchday Explainer frontend

React 19, TypeScript and Vite. The UI uses the **real Flask API**, not dummy
fixture bundles. See the root [README](../README.md) for full setup.

## Development

```sh
npm ci
npm run dev
npm run build
npm run lint
```

Use Node 24. Vite serves port 5173 and proxies `/api` to Flask on 8080. Start
the backend separately. The preview server is a static build preview; a real
deployment must forward `/api` to the backend as well.

## Screens and behavior

- **Match list:** refreshes every four seconds without overlapping requests.
  Search teams/competitions; filter all matches, live matches or saved files.
  Saved files are explicitly labelled and do not prove streaming is working.
- **Pipeline details:** checks local Redis, IFAB index availability and AI-key
  configuration every 30 seconds. AI model access and Azure consumption are
  not probed. Service failures do not prevent browsing available match data.
- **Match links:** `/#/matches/<match_id>` survives refresh and can be shared.
  Browser back/forward works. The generator prints a link for each live demo.
- **Catch me up:** backend-generated summary windows and a time scrubber. AI
  selects evidence IDs; source text and values are rendered by the backend.
  Supporting data can be expanded below the fact badge. Requests refresh at 30-second samples
  so accelerated SSE updates do not continually cancel an AI request.
- **Stats:** nine rows, all driven by match state. Clicking a row opens an AI
  definition for New fan / Regular / Analyst, with live values shown separately.
- **Why that whistle?:** nothing opens or requests a law explanation until a
  row is selected. Retrieved passages, data limits and original PDF links are
  exposed. Unavailable or unsupported answers show clear retry/abstention UI.

An open match receives full snapshots over SSE, checked by the backend once
per second. EventSource reconnects automatically. Source-data and glossary
fallbacks are labelled; they are not misrepresented as AI/RAG output.

## Code map

| Path | Responsibility |
| --- | --- |
| `src/App.tsx` | Hash routing and app shell |
| `src/lib/live.ts` | API state types, fetching, SSE and live value formatting |
| `src/lib/explanations.ts` | Typed explanation responses, cancellation, debounce, retry and bounded client cache |
| `src/pages/` | Match discovery and match subscriptions |
| `src/components/` | Summary, stats, events, readiness, scrubber and accessible sheets |
| `src/data/explanations.ts` | UI titles and audience labels only; no canned law answers |
| `src/index.css` | Design tokens and responsive styles |

Requests are aborted on unmount; obsolete explanation results are hidden.
Dialogs support Escape, Tab focus containment, close buttons and focus return.
Styles respect reduced-motion preferences. The mobile sheet becomes a centred
dialog on desktop; colors and spacing follow `presentations/03-product-screens.png`.

Build and lint run in GitHub Actions. Backend tests cover API contracts and
failure behavior. Browser interaction checks are manual; there is currently
no committed browser end-to-end test suite.
