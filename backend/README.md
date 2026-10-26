# Matchday Explainer backend

Flask APIs, synthetic football events, Redis state, optional Azure delivery,
and IFAB retrieval over PostgreSQL/pgvector. See the [root setup guide](../README.md)
and [demo runbook](../docs/DEMO.md).

## Install and configure

Python 3.11+ is required. From `backend`:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Do not overwrite an existing `.env`. The example documents all service values.
Paths default to `data`, `data/synth` and `ifab` beside the backend code, not the
shell's working directory. Optional `DATA_DIR`, `MATCH_DATA_DIR` and `IFAB_DIR`
override these paths.

| Capability | Required services/configuration |
| --- | --- |
| Browse bundled JSONL archives | No external service; unset `DB_URI` uses an in-memory boot fallback |
| Source-data summaries and reference stat definitions | Match data; AI outages fall back explicitly |
| Local live replay | Redis: `REDIS_URL` |
| AI-selected summaries / adapted stat definitions | `OPENAI_API_KEY`, `LLM_MODEL`; optional compatible `OPENAI_BASE_URL` |
| Referee RAG | PostgreSQL/pgvector, indexed IFAB PDFs, AI/embedding access |
| Azure delivery | Event Hub, consumer group, Blob checkpoint container, listening consumer and Redis |

The in-memory SQLite fallback is **not** a vector index. RAG needs PostgreSQL.
From the repository root, `docker compose up -d` optionally supplies local Redis
and pgvector-enabled PostgreSQL. Its credentials are for a local demo only.

For the vector database:

```sh
python manage.py init-db
python app.py
```

`init-db` enables the installed `vector` extension and creates missing tables;
it does not drop data or run on import. The DB user needs extension privileges.
There is intentionally no implicit destructive `recreate` command.

Index PDFs once the API is running:

```sh
curl -X POST http://localhost:8080/api/v1/rag/index
```

This can make paid embedding calls. The response reports `indexed`, `unchanged`
and newly written `chunks`. Unchanged sources are skipped; changed sources are
replaced transactionally rather than duplicated. This is an index build, not a
schema migration system; changing embedding dimensions requires a deliberately
migrated/rebuilt vector table.

## Generation and replay

```sh
# Save only: no live events or API calls.
python -m synth.generator --seed 42

# Predictable slow demo: five seconds between every event.
python -m synth.generator --seed 42 --to-redis --event-interval 5

# Approximately ten-minute live demo, using football clock gaps.
python -m synth.generator --seed 42 --to-redis --duration 600

# Azure route (requires streaming.consumer in another terminal).
python -m synth.generator --seed 42 --stream --duration 600

# Existing archive, fresh IDs, no Redis reset.
python -m streaming.replay --file data/synth/<match>.jsonl --new-match --duration 600

# Existing archive to Azure instead of directly to Redis.
python -m streaming.replay --file data/synth/<match>.jsonl --new-match --to-eventhub --event-interval 5
```

Both CLIs accept exactly one timing control:

- **`--speed N`**: match-clock seconds divided by N. Higher is **faster**.
  `1` is real-time football timing, `0.5` slower, `30` faster, `0` intentionally
  instant. Default is `1` for both commands. The half-time break is omitted.
- **`--duration SECONDS`**: scale the entire clock-based schedule to this many
  seconds. Events at the same football time can still arrive in a cluster.
- **`--event-interval SECONDS`**: fixed wait between every event. Best when
  presenting slowly; simultaneous facts are separated too.

Kick-off is always immediate. The CLI prints the total scheduled waits before
publishing. Network, Redis and console work add overhead; duration is not a
hard wall-clock deadline. Invalid, negative, infinite and conflicting options
are rejected. Timing options on a save-only generation are rejected rather
than silently ignored.

Add `--dry-run` to preview a generation or replay schedule without publishing.
Generator dry runs write no files:

```sh
python -m synth.generator --seed 42 --duration 600 --dry-run
```

### Why the old stream felt too fast

Older generator files advanced `recorded_at` by random 8–45-second increments,
even when several football minutes elapsed. New timestamps follow the football
clock. Replay also prefers structured `match_clock` data, so **old archives are
paced correctly** without rewriting them. First-half added time is accounted
for when the second-half clock resets. Every published event is flushed before
the next wait; no full-match batch is held until the end.

### Archive and recovery behavior

- Each generation prints its seed and uses a unique match ID. A printed seed
  reproduces the simulation, not the UUID or calendar date.
- Live generation writes the full recovery log to `<match>.jsonl.pending`.
  The catalogue ignores it while Redis supplies the live state. After successful
  publication it is renamed to `.jsonl`; archive results do not leak early.
- Ctrl+C keeps the pending file and the last projected Redis state. It does not
  mark the match full-time. Replay the recovery file under fresh IDs if needed:

  ```sh
  python -m streaming.replay --file data/synth/<match>.jsonl.pending --new-match --duration 600
  ```

- `--new-match` clones identifiers, never changes football facts or clears
  Redis. Local replay refuses to wait through an already projected match without
  it. The projector itself ignores duplicate/lower sequences received via Azure.
- Existing `--out` files are never overwritten. Pending-file recovery and a
  fresh replay do not delete the original archive.

## Event model and projection

Each JSONL line is an immutable event with `schema_version`, `event_id`,
`match_id`, increasing `seq`, `recorded_at`, structured `match_clock`, `type`
and `payload`. Match length/event count vary; they are not fixed at 104 events.

| Type | Purpose |
| --- | --- |
| `match_status` | Kick-off metadata, half-time, second-half kick-off, full-time |
| `shot` | Attempt, outcome, xG and optional `score_after`; a goal is not duplicated as another event |
| `foul`, `card` | Offence/consequence and separate disciplinary fact |
| `corner`, `offside`, `injury`, `substitution`, `var` | Match events and recorded context |
| `stats_snapshot` | Producer-projected aggregates every five minutes and at period endings |

`streaming.state.apply_event` folds these into score, stats and timeline. The
generator validates its final aggregates against emitted facts. Both local
replay and Azure consumption use this projection. Sequence deduplication is
per match; ordered Azure publication uses a match-specific partition key.
Snapshots resynchronise aggregates, not missing historical events.

State expires after `MATCH_STATE_TTL` (default 24 hours); the timeline retains
300 events. The read-only catalogue overlays Redis state on saved JSONL matches.
Saved-file visibility is not proof that a consumer is working. The UI labels
Saved sources and distinguishes them from Redis-backed match state.

## Azure setup

Configure `EVENTHUB_CONNECTION_STRING`, `EVENTHUB_NAME`,
`EVENTHUB_CONSUMER_GROUP`, `AZURE_STORAGE_CONNECTION_STRING` and
`BLOB_CONTAINER_NAME`. Create the Event Hub, consumer group and Blob container
in Azure first. Send permissions alone are insufficient for the consumer.

```sh
python -m streaming.consumer
```

The consumer resumes owned Blob checkpoints. Counts are **per partition**;
successful full-time events flush a checkpoint even below the usual 25-event
interval. Redis failures retry the same event without advancing a checkpoint.
Malformed records are reported; a production system should add a dead-letter
and operator-recovery policy. Redelivered valid events are idempotent.

## API reference

All paths below are relative to `/api/v1`.

| Method/path | Request / response |
| --- | --- |
| `GET /health` | Process liveness, not dependency readiness |
| `GET /ready` | Redis/index/key-configuration checks; 200 ready, 503 degraded; never a paid AI request |
| `GET /matches` | Saved and projected matches, deduplicated; Redis wins |
| `GET /matches/<id>/state` | Full state snapshot and `source` (`saved` or `live`) |
| `GET /matches/<id>/stream` | SSE snapshots checked every second; initial state and 15-second heartbeat |
| `POST /matches/<id>/summary` | `window`: `since-kickoff`, `last-10`, `since-joined`; optional integer `minute`, `joined_at` |
| `POST /matches/<id>/stats/<stat>/explanation` | `audience`: `new-fan`, `regular`, `analyst` |
| `POST /rag/matches/<id>/events/<seq>/explanation` | Uses the server's recorded event; returns answer, citations, passages, chunks and data limits |
| `POST /rag/search` | `query`; optional `context`, `event`, `audience`, `limit` (1–10), `include_chunks` |
| `POST /rag/index` | Index PDFs from `IFAB_DIR`; returns counts |
| `GET /ifabs` | Available source PDFs |
| `GET /ifabs/<filename>` | Original PDF for citation inspection |

The original `/ifabs/ifabs` paths remain aliases. Local-demo document upload
and deletion routes also exist; do not expose them or indexing without auth.
Uploads are size-limited, filename-sanitised and cannot overwrite existing files.
Deleting a PDF does not automatically remove old vector rows; manage obsolete
index content deliberately before a public deployment.

## AI behavior and cost controls

- Summary AI chooses valid source-fact IDs. Only those facts are rendered; no
  generated numbers are accepted. Invalid output falls back to source data.
- Stat AI adapts a supplied definition; live numbers are displayed separately.
- RAG supplies server event facts plus retrieved IFAB passages. Citation IDs
  must belong to the retrieved set. No passages means abstention; retrieval or
  invalid-citation failures return a retryable 503, not an uncited answer.
- A 20-second model timeout and bounded in-process cache limit repeated calls.
  Frontend debounce/cancellation and 30-second summary sampling reduce churn.
- The committed embedding cache is read-only. New vectors go to gitignored
  `data/embeddings_cache.local.json`, written atomically; repeated cache reads
  reuse parsed data. Do not commit API keys or local cache artifacts.
- The SDK is OpenAI-compatible; the index is pgvector. No Azure AI Search
  integration or independent semantic-verifier service is implemented.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Increasing `--speed` makes the demo fast | Expected: higher means faster. Use `--duration 600` or `--event-interval 5`. |
| Everything jumps to full-time | Avoid `--speed 0`; choose a fresh ID. A Saved file is an archive, not a stream. |
| Producer finishes but Redis has no match | Confirm consumer event logs, Redis connectivity and the actual Azure group. Publishing is not consumption. |
| Azure `amqp:not-found` with `...\|start-builder` | Create `start-builder` under the correct Event Hub's Consumer groups, then restart the consumer. |
| Replaying an old file changes nothing | Duplicate sequences are ignored. Add `--new-match`; do not flush Redis. |
| Live replay card has not appeared yet | The list refreshes every four seconds. For Azure, first-event consumption may take longer; inspect consumer logs. |
| RAG unavailable | Check `python -m streaming.doctor`, DB schema, IFAB index, key/model access and embedding dimensions. |
| Summary/definition says fallback | AI failed or is not configured. Match facts still work; this is explicitly labelled. |
| Docker ports already in use | Reuse existing services or change host ports and `.env`. Do not stop unrelated services blindly. |
| `.jsonl.pending` remains | Publication was interrupted/failed; recovery data is preserved. Re-run under fresh IDs. |

## Checks

```sh
python -m streaming.doctor
python -m unittest discover -s tests -v
```

The doctor exits 1 when a local capability is degraded, 0 when all local checks
pass. It does not verify Azure consumption or make a paid model request.
Tests use fake services and temporary files: no credentials, running database,
Azure resources or Redis are required.
