"""Replay a synthetic JSONL match into the pipeline.

Two modes:
  --to-redis (default)  Feed the local match-state projection directly —
                        lets you test Redis + SSE + front end end-to-end
                        without any Azure credentials.
  --to-eventhub         Send the events to the real `match-events` hub
                        (needs EVENTHUB_CONNECTION_STRING in .env) so the
                        `start-builder` consumer picks them up.

Pacing: events are sent in near real time by default (--speed 1). Use
--speed 30 to compress ~45 minutes of match time into ~90 seconds.
--speed 0 sends everything as fast as possible.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from streaming.state import ingest_event


def load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def replay_speed(value: str) -> float:
    speed = float(value)
    if not math.isfinite(speed) or speed < 0:
        raise argparse.ArgumentTypeError("speed must be a finite number greater than or equal to 0")
    return speed


def paced_events(lines: list[dict], speed: float):
    """Yield kickoff immediately, then pace publication, not just batch filling."""
    if not math.isfinite(speed) or speed < 0:
        raise ValueError("speed must be finite and non-negative")
    previous = None
    for line in lines:
        timestamp = datetime.fromisoformat(line["recorded_at"].replace("Z", "+00:00")).timestamp()
        if previous is not None and speed > 0:
            delay = (timestamp - previous) / speed
            if delay > 0:
                time.sleep(delay)
        previous = timestamp
        yield line


def send_to_eventhub(lines: list[dict], speed: float) -> None:
    from azure.eventhub import EventHubProducerClient, EventData

    conn = os.getenv("EVENTHUB_CONNECTION_STRING")
    name = os.getenv("EVENTHUB_NAME", "match-events")
    if not conn:
        print("EVENTHUB_CONNECTION_STRING not set in backend/.env",
              file=sys.stderr)
        sys.exit(1)

    producer = EventHubProducerClient.from_connection_string(
        conn, eventhub_name=name,
    )
    print(f"Streaming {len(lines)} events to hub '{name}' "
          f"{'as fast as possible' if speed == 0 else f'at {speed}x'}…", flush=True)
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


def send_to_redis(lines: list[dict], speed: float) -> None:
    label = "as fast as possible" if speed == 0 else f"at {speed}x"
    print(f"Replaying into local Redis {label}…", flush=True)
    for line in paced_events(lines, speed):
        state = ingest_event(line)
        if state and line["type"] in ("match_status", "shot"):
            print(f"  [{line['match_clock']['display']}] "
                  f"{state['score']['home']}-{state['score']['away']} "
                  f"({line['type']})", flush=True)
    print("Replay finished — state is in Redis, SSE endpoint is live.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, help="path to a .jsonl match")
    parser.add_argument("--to-eventhub", action="store_true",
                        help="send to Azure Event Hubs instead of local Redis")
    parser.add_argument("--speed", type=replay_speed, default=1.0,
                        help="replay speed multiplier (0 = no pacing)")
    args = parser.parse_args()

    lines = load_jsonl(args.file)
    print(f"{len(lines)} events loaded from {args.file}")

    if args.to_eventhub:
        send_to_eventhub(lines, args.speed)
        return 0

    send_to_redis(lines, args.speed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
