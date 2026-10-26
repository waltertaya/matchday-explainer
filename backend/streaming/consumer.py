"""Azure Event Hubs consumer — the `start-builder` consumer group.

Reads match events from the `match-events` hub, projects each event into
the match state (streaming/state.py) and persists it to Redis, from where
the Flask SSE endpoint streams it to the front end.

Checkpoints live in Azure Blob Storage so a restart resumes where the
consumer left off (the `archiver` consumer group is unaffected — each
group has its own cursor).

Env vars:
    EVENTHUB_CONNECTION_STRING   the hub's listen connection string
    EVENTHUB_NAME                default: match-events
    EVENTHUB_CONSUMER_GROUP      default: start-builder
    AZURE_STORAGE_CONNECTION_STRING
    BLOB_CONTAINER_NAME          default: match-events-checkpoints
    REDIS_URL                    default: redis://localhost:6379/0

Run:
    ./venv/bin/python -m streaming.consumer
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from azure.eventhub import EventHubConsumerClient
from azure.eventhub.extensions.checkpointstoreblob import BlobCheckpointStore

from streaming.state import ingest_event

EVENTHUB_CONNECTION_STRING = os.getenv("EVENTHUB_CONNECTION_STRING")
EVENTHUB_NAME = os.getenv("EVENTHUB_NAME", "match-events")
CONSUMER_GROUP = os.getenv("EVENTHUB_CONSUMER_GROUP", "start-builder")
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER_NAME", "match-events-checkpoints")

_checkpoint_every = 25
_counter = {"n": 0}


def on_error(partition_context, error):
    partition = getattr(partition_context, "partition_id", "connection")
    print(f"Consumer error [{partition}]: {error}", file=sys.stderr, flush=True)
    message = str(error).lower()
    if "amqp:not-found" in message or "could not be found" in message:
        print(
            f"The Event Hub '{EVENTHUB_NAME}' or consumer group '{CONSUMER_GROUP}' "
            "does not exist. In Azure Portal, open your Event Hub > Consumer groups "
            f"and create '{CONSUMER_GROUP}', then restart this consumer. "
            "A running process does not mean events are being received.",
            file=sys.stderr, flush=True,
        )


def on_partition_initialize(partition_context):
    print(f"Receiving partition {partition_context.partition_id} "
          f"as consumer group '{CONSUMER_GROUP}'", flush=True)


def on_event(partition_context, event):
    try:
        payload = json.loads(event.body_as_str(encoding="utf-8"))
        state = ingest_event(payload)
        if state:
            print(
                f"[{payload.get('match_clock', {}).get('display', '?')}] "
                f"{state['home']['name'] if state['home'] else '?'} "
                f"{state['score']['home']}-{state['score']['away']} "
                f"{state['away']['name'] if state['away'] else '?'} "
                f"({payload['type']})",
                flush=True,
            )
    except Exception as exc:  # keep the consumer alive on bad records
        print(f"Failed to process event: {exc}", file=sys.stderr, flush=True)

    _counter["n"] += 1
    if _counter["n"] % _checkpoint_every == 0:
        partition_context.update_checkpoint(event)


def main() -> int:
    if not EVENTHUB_CONNECTION_STRING or not STORAGE_CONNECTION_STRING:
        print(
            "Missing EVENTHUB_CONNECTION_STRING / AZURE_STORAGE_CONNECTION_STRING "
            "in backend/.env — for a local test without Azure use "
            "`python -m streaming.replay --file data/synth/<match>.jsonl` instead.",
            file=sys.stderr,
        )
        return 1

    checkpoint_store = BlobCheckpointStore.from_connection_string(
        STORAGE_CONNECTION_STRING, BLOB_CONTAINER,
    )
    client = EventHubConsumerClient.from_connection_string(
        EVENTHUB_CONNECTION_STRING,
        consumer_group=CONSUMER_GROUP,
        eventhub_name=EVENTHUB_NAME,
        checkpoint_store=checkpoint_store,
    )

    print(
        f"Consuming '{EVENTHUB_NAME}' as group '{CONSUMER_GROUP}' "
        f"(checkpoints in blob container '{BLOB_CONTAINER}')…",
        flush=True,
    )

    try:
        # starting_position="-1" = read from the beginning when a partition
        # has no checkpoint yet; owned checkpoints always win afterwards.
        client.receive(
            on_event=on_event,
            on_error=on_error,
            on_partition_initialize=on_partition_initialize,
            starting_position="-1",
        )
    except KeyboardInterrupt:
        print("Consumer stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
