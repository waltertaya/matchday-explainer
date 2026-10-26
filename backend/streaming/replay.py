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
          f"{'as fast as possible' if speed == 0 else f'at {speed}x'}…")
    with producer:
        batch = producer.create_batch()
        prev_ts = None
        for line in lines:
            ts = datetime.fromisoformat(
                line["recorded_at"].replace("Z", "+00:00"),
            ).timestamp()
            if prev_ts is not None and speed > 0:
                time.sleep(max(0.0, (ts - prev_ts) / speed))
            prev_ts = ts
            try:
                batch.add(EventData(json.dumps(line, separators=(",", ":"))))
            except ValueError:
                producer.send_batch(batch)  # batch full -> flush and retry
                batch = producer.create_batch()
                batch.add(EventData(json.dumps(line, separators=(",", ":"))))
        producer.send_batch(batch)
    print("Done — events are in the hub; the start-builder consumer picks them up.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, help="path to a .jsonl match")
    parser.add_argument("--to-eventhub", action="store_true",
                        help="send to Azure Event Hubs instead of local Redis")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="replay speed multiplier (0 = no pacing)")
    args = parser.parse_args()

    lines = load_jsonl(args.file)
    print(f"{len(lines)} events loaded from {args.file}")

    if args.to_eventhub:
        send_to_eventhub(lines, args.speed)
        return 0

    label = "as fast as possible" if args.speed == 0 else f"at {args.speed}x"
    print(f"Replaying into local Redis {label}…")
    fmt = "%Y-%m-%dT%H:%M:%S%z"
    prev_ts = None
    for line in lines:
        ts = datetime.strptime(line["recorded_at"], fmt).timestamp()
        if prev_ts is not None and args.speed > 0:
            time.sleep(max(0.0, (ts - prev_ts) / args.speed))
        prev_ts = ts
        state = ingest_event(line)
        if state and line["type"] in ("match_status", "shot"):
            print(f"  [{line['match_clock']['display']}] "
                  f"{state['score']['home']}-{state['score']['away']} "
                  f"({line['type']})", flush=True)
    print("Replay finished — state is in Redis, SSE endpoint is live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
