"""Replay a synthetic JSONL match into the pipeline.

Two modes:
  --to-redis (default)  Feed the local match-state projection directly —
                        lets you test Redis + SSE + front end end-to-end
                        without any Azure credentials.
  --to-eventhub         Send the events to the real `match-events` hub
                        (needs EVENTHUB_CONNECTION_STRING in .env) so the
                        `start-builder` consumer picks them up.

Pacing: --speed 1 follows the football match clock; larger means FASTER.
Use --duration 600 for a ten-minute demo, or --event-interval 5 for a
five-second gap between every event. --speed 0 deliberately disables waits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from streaming.state import ingest_event, load_state
from streaming.pacing import ReplayTiming, add_timing_arguments, replay_speed


def load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def paced_events(lines: list[dict], speed: float | ReplayTiming):
    """Yield kickoff immediately, then pace publication, not just batch filling."""
    timing = speed if isinstance(speed, ReplayTiming) else ReplayTiming(speed=speed)
    for line, delay in zip(lines, timing.delays(lines)):
        if delay > 0:
            time.sleep(delay)
        yield line


def send_to_eventhub(lines: list[dict], speed: float | ReplayTiming) -> None:
    from azure.eventhub import EventHubProducerClient, EventData

    conn = os.getenv("EVENTHUB_CONNECTION_STRING")
    name = os.getenv("EVENTHUB_NAME", "match-events")
    if not conn:
        print("EVENTHUB_CONNECTION_STRING not set in backend/.env",
              file=sys.stderr)
        raise ValueError("Event Hubs is not configured")

    producer = EventHubProducerClient.from_connection_string(
        conn, eventhub_name=name,
    )
    timing = speed if isinstance(speed, ReplayTiming) else ReplayTiming(speed=speed)
    print(f"Streaming {len(lines)} events to hub '{name}'…", flush=True)
    print(timing.describe(lines), flush=True)
    with producer:
        for line in paced_events(lines, speed):
            # Flush EACH event before waiting for the next one. Keeping one
            # growing batch here delays the entire match until full-time.
            # A match-specific partition key also preserves sequence order.
            batch = producer.create_batch(partition_key=line["match_id"])
            batch.add(EventData(json.dumps(line, separators=(",", ":"))))
            producer.send_batch(batch)
            print(f"  sent #{line['seq']} [{line['match_clock']['display']}] "
                  f"{line['type']}", flush=True)
    print("Done — all events published. The running streaming.consumer "
          "must project them into Redis for live API updates.", flush=True)


def send_to_redis(lines: list[dict], speed: float | ReplayTiming) -> None:
    timing = speed if isinstance(speed, ReplayTiming) else ReplayTiming(speed=speed)
    print("Replaying into local Redis…", flush=True)
    print(timing.describe(lines), flush=True)
    for line in paced_events(lines, speed):
        state = ingest_event(line)
        if state and line["type"] in ("match_status", "shot"):
            print(f"  [{line['match_clock']['display']}] "
                  f"{state['score']['home']}-{state['score']['away']} "
                  f"({line['type']})", flush=True)
    print("Replay finished — state is in Redis, SSE endpoint is live.")


def fresh_replay(lines):
    """Clone IDs, not match facts; never clear an existing Redis match."""
    copied = deepcopy(lines)
    ids = {match_id: f"{match_id}-replay-{uuid4().hex[:8]}"
           for match_id in dict.fromkeys(line["match_id"] for line in lines)}
    for line in copied:
        line["match_id"] = ids[line["match_id"]]
        line["event_id"] = f"{line['match_id']}-{line['seq']:04d}"
    return copied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, help="path to a .jsonl match")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--to-eventhub", action="store_true",
                             help="send to Azure Event Hubs instead of local Redis")
    destination.add_argument("--to-redis", action="store_true",
                             help="send directly to local Redis (the default)")
    parser.add_argument("--new-match", action="store_true",
                        help="replay under fresh IDs so existing Redis state is not skipped or deleted")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the timing plan without publishing events")
    add_timing_arguments(parser)
    args = parser.parse_args(argv)

    lines = load_jsonl(args.file)
    if not lines:
        parser.error("The match file contains no events")
    if args.new_match:
        lines = fresh_replay(lines)
    print(f"{len(lines)} events loaded from {args.file}")
    print(f"Match ID: {lines[0]['match_id']}", flush=True)
    timing = ReplayTiming.from_args(args)
    if args.dry_run:
        print(timing.describe(lines))
        print("Dry run: no events published and no state changed.")
        return 0

    try:
        if args.to_eventhub:
            send_to_eventhub(lines, timing)
        else:
            existing = load_state(lines[0]['match_id'])
            if existing and existing.get('last_seq', 0) >= lines[0].get('seq', 0):
                parser.error("This match already has projected state. Add --new-match for a fresh demo; no Redis data was deleted.")
            send_to_redis(lines, timing)
    except KeyboardInterrupt:
        print("\nReplay stopped. Existing archives and projected state were preserved.")
        return 130
    except Exception as error:
        print(f"Replay failed ({type(error).__name__}). Check service connectivity and configuration. "
              "No existing match data was cleared.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
