"""Read-only catalogue of saved matches, overlaid with live Redis state.

Never import saved events into Redis: a replay must still start at sequence 1.
"""
import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from redis.exceptions import RedisError

from streaming import state as mstate

log = logging.getLogger(__name__)


@lru_cache(maxsize=128)
def _project_file(filename, mtime, size):
    states = {}
    with open(filename, encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            event = json.loads(line)
            match_id = event.get("match_id")
            if not match_id:
                continue
            state = states.setdefault(match_id, mstate.new_state(match_id))
            mstate.apply_event(state, event)
    for state in states.values():
        state["updated_at"] = datetime.fromtimestamp(
            mtime / 1e9, timezone.utc,
        ).isoformat()
    return states


def saved_states():
    directory = Path(os.getenv(
        "MATCH_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "synth"),
    ))
    states = {}
    for path in sorted(directory.glob("*.jsonl")):
        try:
            stat = path.stat()
            states.update(_project_file(str(path), stat.st_mtime_ns, stat.st_size))
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Could not read saved match %s", path.name, exc_info=True)
    return deepcopy(states)


def get_state(match_id):
    try:
        live = mstate.load_state(match_id)
        if live is not None:
            return {**live, "source": "live"}
    except RedisError:
        log.warning("Redis unavailable; using saved match state")
    saved = saved_states().get(match_id)
    return {**saved, "source": "saved"} if saved else None


def list_matches():
    fields = ("match_id", "home", "away", "competition", "status", "minute",
              "display", "score", "updated_at")
    matches = {
        match_id: {**{field: state.get(field) for field in fields}, "source": "saved"}
        for match_id, state in saved_states().items()
    }
    try:
        for match in mstate.list_matches():
            matches[match["match_id"]] = {**match, "source": "live"}
    except RedisError:
        log.warning("Redis unavailable; listing saved matches only")
    return sorted(matches.values(), key=lambda m: m.get("updated_at") or "", reverse=True)
