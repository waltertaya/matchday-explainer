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
```

- Without options, each run creates a new random match.
- `--seed 42` makes the generated match reproducible.
- `--stream` also sends the generated events to Event Hubs.

Generated files are written to `data/synth/synth-<date>-<home>-<away>.jsonl`
and contain approximately 100–110 events.

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
With `--speed 0`, pacing is disabled. The generator's `--stream` mode batches
all events into one producer send; for a paced replay, use the JSONL replay
utility.

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

The SSE endpoint sends an initial full snapshot immediately, then sends a new
full snapshot after each state change. It emits a heartbeat comment every
15 seconds to keep quiet connections open. The browser's `EventSource`
automatically reconnects if the connection drops.

The "Catch me up" summary text is currently generated client-side. An Azure
OpenAI summary service can be placed behind the same `MatchSummary` shape
later.

## Streaming directly to Event Hubs

Install the Event Hubs client and configure the connection details:

```bash
pip install azure-eventhub
export EVENTHUB_CONNECTION_STRING="Endpoint=sb://..."
export EVENTHUB_NAME="match-events"
./venv/bin/python -m synth.generator --stream
```

The generator sends the complete generated stream in one producer batch.
For a paced live replay, use `streaming.replay`; its timestamps are already
spaced according to match time.
