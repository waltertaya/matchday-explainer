# Hackathon demo runbook

## The story, in one sentence

**“A late-arriving football fan can catch up, understand a statistic, and read
the law behind a whistle—without asking an AI to invent the score or judge a referee.”**

Lead with the fan's problem. The streaming and retrieval architecture explains
how the experience works; it should not be the first 90 seconds of the demo.

## Before judging

1. Start the backend and frontend. Confirm Redis is reachable. For the full
   story, initialise/index PostgreSQL and configure actual model access.
2. Run `python -m streaming.doctor` and the automated checks in the root README.
   The doctor checks configuration/readiness, **not** paid AI or Azure access.
3. Manually open one stat explanation and one event's cited law answer. Expand
   a passage and open its original PDF. Do this before going on stage: provider
   quotas, billing and network access are not proven by a configured API key.
4. If showing Azure, create/check `start-builder` and the Blob checkpoint
   container, then run `python -m streaming.consumer`. Look for received events,
   not just a process banner or producer completion message.
5. Keep a working saved match and original PDFs available as a **labelled**
   backup. Do not claim archive data is live Azure consumption.

Do not start a second Redis/PostgreSQL container over services already using
those ports. Do not expose demo credentials or `.env` in a screen share.

## Pick your pace

From `backend`, in the active virtual environment:

```sh
# Five-minute local presentation; football clock gaps are scaled.
python -m synth.generator --seed 42 --to-redis --duration 300

# Ten-minute version with more room for questions.
python -m synth.generator --seed 42 --to-redis --duration 600

# Steady, deliberately slow rhythm: five seconds per fact.
python -m synth.generator --seed 42 --to-redis --event-interval 5

# Same paced presentation through Azure, with consumer running separately.
python -m synth.generator --seed 42 --stream --duration 600
```

Open the printed match link. Seed 42 produces repeatable match content with
cards, goals and a VAR check; it gets a fresh ID each run. Expect the first goal
around football minute 24, not immediately at kick-off. At a 300-second target,
that is roughly the first quarter of the presentation. Event counts vary with
seed; fixed event intervals therefore vary in total duration.

**Higher `--speed` is faster.** Do not increase it to slow down. Use exactly one
of `--speed`, `--duration` or `--event-interval`. Default is real-time match-clock
pacing, not the old implicit 30× replay. Network/processing add overhead, and
clock-based pacing can cluster facts recorded at the same football time.

## Five-minute walkthrough

### 0:00–0:40 — Fan problem and live arrival

“I joined late. I can see the score, but I don't know the story.”

Open the newly generated match. Show that the score starts at kick-off and
changes from the stream, rather than revealing the saved full-time result.
The full recovery log remains `.pending` during the live replay.

### 0:40–1:40 — Catch me up

Compare **Since kick-off** and **Last 10 min** as events arrive. Show the
source-linked fact count and expand supporting data. Scrub to an earlier
minute, then return to live.

Explain precisely: AI chooses which recorded facts to highlight; the server
renders the facts and numbers. The app does not run an independent semantic
verifier over unrestricted generated match prose.

### 1:40–2:40 — A number that teaches

Tap **xG**. Change **New fan → Analyst**. Show that the explanation adapts while
the actual match values remain separately tied to state. xG is chance quality,
not a deserved score or a promise about the next goal.

### 2:40–3:50 — A rule, not a referee verdict

Open **Why that whistle?**. Nothing should auto-open. Choose a recorded foul,
card or VAR event. Expand a cited passage and open its original IFAB PDF.

Point out the distinction: recorded event facts, retrieved law, and missing
details. A synthetic label does not prove contact, intent or video evidence.
If retrieval cannot support an answer, show the abstention—not a fallback
presented as a citation.

### 3:50–5:00 — Explain the engineering and close

Show the local pipeline details and describe the chosen route:

- Local: event projection → Redis → Flask SSE → React.
- Azure: Event Hubs → consumer/Blob checkpoints → the same projection and UI.
- RAG: IFAB PDFs → embeddings → PostgreSQL/pgvector → cited answer.

“The useful part is not just generating text. It's keeping the match facts,
the law sources and the limits of the evidence visible to a new fan.”

## Recovery without destroying data

| Problem on stage | Recovery |
| --- | --- |
| Azure group/consumer unavailable | State the issue; switch to a new `--to-redis` match and label it local streaming. |
| AI/provider unavailable | Show the explicit source-data/stat fallback. Do not claim RAG worked if it did not. |
| Original producer interrupted | Ctrl+C preserves `.jsonl.pending`; use a fresh replay below. The old state stays last-known, not automatically full-time. |
| Replay looks finished immediately | Use fresh IDs; verify the card is not a Saved archive and pacing is not zero. |
| Network/model takes longer | Keep discussing evidence and current stats; do not repeatedly change tabs and cancel the request. |

```sh
python -m streaming.replay --file data/synth/<match>.jsonl.pending --new-match --duration 600
```

This starts from the beginning under new IDs. It is recovery, **not** in-place
resume. Never use `FLUSHDB`, remove all matches or drop the vector table as a
demo shortcut.

## Likely judging questions

**“Where is the AI?”** Fact selection for summaries, audience-adapted stat
definitions, and rule explanations grounded in retrieved IFAB passages.

**“What prevents hallucinated scores?”** The model does not author the displayed
score/stat values. Summary IDs are checked against available facts; invalid
selections fall back to source-rendered text.

**“Do citations prove the answer is correct?”** No. The app rejects unknown IDs
and exposes the actual passages, but semantic entailment still needs evaluation.
Don't present ID validation as an independent factual-verification benchmark.

**“Is this real football data?”** No. It's a seeded synthetic stream with a
validated event/stat projection. A production feed adapter is future work.

**“Is all of this Azure?”** Event Hubs and Blob checkpoints are implemented.
The current AI client is OpenAI-compatible and the vector index is PostgreSQL/
pgvector. Do not say Azure AI Search is running when it is only on a slide.

**“What would you improve next?”** Evaluate law-answer support with a labelled
set; test with new fans; add production auth/rate limits and browser E2E tests;
integrate a licensed event feed. Report measured quality/user results only after
actually running those studies.

## Submission checklist

- [ ] Repository quick start works from a fresh environment.
- [ ] Build, lint and tests pass; no credentials in the submission.
- [ ] Short recorded demo shows all three fan journeys and one original source.
- [ ] Slides distinguish implemented components from planned services.
- [ ] Synthetic data, fallback behavior and deployment limits are disclosed.
- [ ] Explain the fan benefit and trust boundary before listing cloud products.
