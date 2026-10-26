# Matchday Explainer backend

The backend generates synthetic football match events, processes live events
into a rolling match state, and exposes that state to the frontend through
Flask and Server-Sent Events (SSE).

## Architecture

```text
synth.generator ──► JSONL / Azure Event Hubs (match-events)
                                  │
                                  ▼
                       streaming.consumer
                                  │
                       match-state projection
                                  │
                                  ▼
                               Redis
                                  │
                   Flask API / SSE endpoints
                                  │
                                  ▼
                          React frontend
```

The broader application uses the projected state for:

```text
Match state
    ├── Match summary       (Azure OpenAI)
    ├── Stat explainer      (Azure OpenAI)
    └── Referee RAG         (Azure AI Search)
                 │
                 ▼
          Fan experience (React)
```

## Synthetic match event stream

The generator creates a full 90-minute football match as JSONL: one immutable
fact per line, shaped for Azure Event Hubs streaming.

```bash
./venv/bin/python -m synth.generator
./venv/bin/python -m synth.generator --seed 42
./venv/bin/python -m synth.generator --stream
./venv/bin/python -m synth.generator --stream --speed 30
./venv/bin/python -m synth.generator --to-redis --speed 30
```

- Without options, each run creates a new random match.
- `--seed 42` makes the generated match reproducible.
- `--stream` generates and immediately starts a paced Event Hubs replay
  (30x by default). No separate replay command is needed. Keep the state
  consumer running to project published events into Redis.
- `--to-redis` generates and immediately replays into local Redis without Azure
  or a separate consumer. `--speed 0` intentionally sends everything instantly.
- With neither flag, generation only saves a file; it does not publish events.

Generated files are written to `data/synth/synth-<date>-<home>-<away>-<run>.jsonl`
and contain approximately 100–110 events.
Each generation gets a unique match ID, even for the same teams on the same
day. This prevents file overwrites and stops Redis's sequence deduplication
from discarding a new match as an old replay.

### Event schema principles

Every record has an envelope containing:

- `schema_version`
- `event_id`
- `match_id`
- `seq` — strictly increasing sequence number
- `recorded_at` — match-time timestamp used to pace replays
- `match_clock` — `minute`, `second`, `period`, `added_time`, and `display`
- `type`
- `payload`

The stream follows these rules:

1. **One fact per event.** A goal is a `shot` with `outcome: "goal"` and
   `score_after`; it is not duplicated as a separate goal event.
2. **Statistics are projections.** `stats_snapshot` records are derived from
   events emitted so far. They are produced every five minutes and at
   half-time and full-time. The generator validates that the final snapshot
   agrees with the event totals.
3. **Frontend-compatible vocabulary.** `payload.event_type` uses the
   frontend's `EventType` values: `yellow-card`, `foul`, `injury`, `corner`,
   `offside`, `substitution`, `penalty`, and `var`, plus `shot`.

### Event types

| Type | Payload highlights |
|---|---|
| `match_status` | `kickoff` (venue, referee, weather, attendance), `half_time`, or `full_time` (final stats) |
| `shot` | Side, player, outcome (`goal`, `saved`, `off_target`, `blocked`, `post`), xG, body part, distance, and penalty flag |
| `foul` | Fouling side/player, consequence (`free_kick`, `penalty`, `yellow_card`, or `red_card`), and zone |
| `card` | Yellow/red card and reason |
| `injury` | Treatment duration in seconds |
| `substitution` | Player off/on and reason |
| `corner`, `offside` | Side and player |
| `var` | Check type (`goal`, `penalty`, or `red_card`), outcome, and delay |
| `stats_snapshot` | Possession, shots, shots on target, xG, fouls, corners, cards, and offsides |

## Live streaming pipeline

```text
synth generator ──► Azure Event Hubs (match-events) ──► consumer (start-builder)
                                                        │
                                                        ├── checkpoints ──► Azure Blob Storage
                                                        ▼
                                                    Redis (match state)
                                                        ▼
                              Flask API /api/v1/matches[/id/state | /id/stream SSE]
                                                        ▼
                                              React frontend (EventSource)
```

The state consumer reads events from the `match-events` hub, projects each
event into the score, statistics, and timeline, and persists the resulting
state in Redis. The frontend receives full state snapshots over SSE.

### Environment

Create `backend/.env` with the values needed for the mode you are running:

```dotenv
EVENTHUB_CONNECTION_STRING=Endpoint=sb://...
EVENTHUB_NAME=match-events
EVENTHUB_CONSUMER_GROUP=start-builder
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=...
BLOB_CONTAINER_NAME=match-events-checkpoints
REDIS_URL=redis://localhost:6379/0
```

The Blob Storage container must exist before starting the consumer. The
`archiver` consumer group, if configured, is unaffected because each consumer
group has its own cursor.

The Event Hub's **consumer group must also exist in Azure**. Setting
`EVENTHUB_CONSUMER_GROUP=start-builder` does not create it. In Azure Portal,
open the Event Hub → Consumer groups → create `start-builder`. A process can
remain running while Azure rejects its receive requests. `amqp:not-found`
with `...|start-builder` means the group is missing; a producer's successful
send does not prove the consumer is connected. The consumer now reports this
with explicit setup instructions.

Saved-file cards are labelled **Saved**, and their scoreboard says they are
not a live stream. This distinguishes archive visibility from successful
Event Hubs → consumer → Redis delivery.

### Run the live pipeline

1. Start the state consumer and leave it running:

   ```sh
   ./venv/bin/python -m streaming.consumer
   ```

   Checkpoints in Blob Storage allow a restart to resume from the last
   processed event.

2. Replay a synthetic match into Event Hubs:

   ```sh
   ./venv/bin/python -m streaming.replay \
     --file data/synth/<match>.jsonl \
     --to-eventhub \
     --speed 20
   ```

   `--speed 20` compresses approximately 45 minutes of match time into about
   2.5 minutes. `--speed 1` is real time, and `--speed 0` sends events as fast
   as possible.

3. Start the API:

   ```sh
   ./venv/bin/python app.py
   ```

   The API listens on port 8080.

4. Start the frontend from the repository's `frontend` directory:

   ```sh
   cd ../frontend && npm run dev
   ```

### Local test without Azure

The same state projection can be driven directly into Redis, skipping Event
Hubs and Azure credentials:

```sh
./venv/bin/python -m streaming.replay \
  --file data/synth/<match>.jsonl \
  --speed 20
```

This still exercises the Redis, SSE, API, and frontend path.

### Replay modes

The replay utility supports two destinations:

- **Local Redis (default):** feeds events directly to `ingest_event()`.
- **Azure Event Hubs (`--to-eventhub`):** sends events to the
  `match-events` hub for the `start-builder` consumer to process.

Events are paced using the difference between their `recorded_at` timestamps.
With `--speed 0`, pacing is disabled. The generator and replay utility share
the same publisher: kickoff is published immediately, then each event is sent
before waiting for the next event. A match-specific partition key preserves
ordering. Each successful publication is printed in the terminal. Publication
does not confirm that the consumer has processed the event.

For an already processed file, sequence deduplication intentionally ignores
events Redis has seen. Generate a fresh match for a new live demo, or explicitly
clear only that match's Redis state before replaying from the start.

## State projection and reliability

The projection folds each event into the rolling state:

```text
previous state + one event = new state
```

It updates match status, clock, score, teams, statistics, and the visible
timeline. Events are idempotent by `seq`: duplicate or out-of-order events are
ignored, so redelivery does not double-count a goal or statistic.

`stats_snapshot` events provide authoritative resynchronization from the
producer's projection. This allows a consumer that joined partway through a
match to converge on the current numbers.

The timeline is limited to the most recent 300 entries. Match state expires
from Redis after 24 hours by default.

To replay a match from scratch, clear its existing Redis state first:

```sh
redis-cli del "match:<match_id>"
redis-cli srem matches:index "<match_id>"
```

The second command removes only that match from the match index. Use
`FLUSHDB` only when clearing the entire local Redis database is intended.

## API streaming behavior

The API provides:

- `GET /api/v1/matches` — available matches
- `GET /api/v1/matches/<match_id>/state` — current state snapshot
- `GET /api/v1/matches/<match_id>/stream` — SSE stream

The SSE endpoint sends an initial full snapshot immediately, then checks for
changes once per second. It emits a heartbeat comment every
15 seconds to keep quiet connections open. The browser's `EventSource`
automatically reconnects if the connection drops.

The catalogue also projects saved `data/synth/*.jsonl` files, so generated
matches are visible without first replaying them. Redis state wins for the
same match ID. Saved files are never ingested into Redis by the API. Set
`MATCH_DATA_DIR` to use another directory. Saved matches remain readable when
Redis is unavailable; the catalogue does not fetch external fixture feeds.

## AI explanations and IFAB RAG

Configure these values in `backend/.env`:

```dotenv
OPENAI_API_KEY=...
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
DB_URI=postgresql+psycopg://user:password@localhost/matchday
```

The existing IFAB document index uses PostgreSQL with pgvector. Once the
database/schema and PDFs are ready, `POST /api/v1/rag/index` builds the index.
Indexing uses the embedding API. `OPENAI_BASE_URL` may be set for a compatible
provider. Do not put AI keys in frontend environment variables.

- `POST /api/v1/matches/<id>/summary`: `window` (`since-kickoff`, `last-10`,
  `since-joined`), optional integer `minute` and `joined_at`. AI selects source
  fact IDs; displayed sentences and numbers are rendered from match data.
  Responses include the source evidence and real counts of rendered facts.
  Historical windows exclude current aggregate stats. A source-data summary
  is returned with an explicit notice when AI is unavailable.
- `POST /api/v1/matches/<id>/stats/<stat>/explanation`: `audience` (`new-fan`,
  `regular`, `analyst`). AI explains the definition; match values come from
  state. A labelled reference-definition fallback is available offline.
- `POST /api/v1/rag/matches/<id>/events/<seq>/explanation`: retrieves IFAB
  passages using the server's event, then returns a cited rule explanation,
  event-data limits and source passages. Unknown citation IDs are rejected.
  No supporting passages produces an explicit unanswerable response; retrieval
  failures produce a retryable 503 instead of an ungrounded rule explanation.
- `POST /api/v1/rag/search`: general law lookup using `query`, optional
  `context`, `event`, `audience`, `limit` (1–10), and `include_chunks`.

Stat and event explanations are requested only after clicking a row. Catch-up
summaries refresh every 30 seconds during live play to let AI requests finish
even in accelerated replays. Scrubbing and changing windows request a new
summary. AI requests have a 20-second timeout and a bounded response cache.

### Regression tests

```sh
./venv/bin/python -m unittest discover -s tests -v
```

Tests mock AI, Redis and retrieval: no external credentials, running database,
or paid AI calls are required.

## Streaming directly to Event Hubs

Install the Event Hubs client and configure the connection details:

```bash
pip install azure-eventhub
export EVENTHUB_CONNECTION_STRING="Endpoint=sb://..."
export EVENTHUB_NAME="match-events"
./venv/bin/python -m synth.generator --stream
```

The generator saves the match and starts streaming at 30x, flushing events
individually. Keep `python -m streaming.consumer` running in another terminal.
The frontend match list refreshes every four seconds; open matches get SSE
updates checked every second. No manual page reload is needed.
