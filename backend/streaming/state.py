"""Match-state projection + Redis persistence.

This is the "Match state" box in the architecture:

    Event Hubs events ──► apply_event() ──► Redis ──► Flask SSE ──► React

The projection is pure: `apply_event(state, event)` folds one stream event
into the rolling state (score, stats, timeline). Both the Event Hubs
consumer (consumer group `start-builder`) and the local JSONL replay use
the exact same code, so local testing exercises the real logic.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MATCH_TTL = int(os.getenv("MATCH_STATE_TTL", str(60 * 60 * 24)))  # 24h

MATCH_KEY = "match:{match_id}"
INDEX_KEY = "matches:index"
CHANNEL = "match:{match_id}:updates"

_pool = redis.ConnectionPool.from_url(
    REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=2,
)


def r() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


def new_state(match_id: str) -> Dict[str, Any]:
    return {
        "match_id": match_id,
        "home": None,
        "away": None,
        "competition": None,
        "venue": None,
        "referee": None,
        "weather": None,
        "attendance": None,
        "status": "pre_match",  # pre_match | live | half_time | full_time
        "period": None,
        "minute": 0,
        "display": "0'",
        "score": {"home": 0, "away": 0},
        "stats": {
            "possession": {"home": 50, "away": 50},
            "shots": {"home": 0, "away": 0},
            "shots_on_target": {"home": 0, "away": 0},
            "xg": {"home": 0.0, "away": 0.0},
            "fouls": {"home": 0, "away": 0},
            "corners": {"home": 0, "away": 0},
            "yellow_cards": {"home": 0, "away": 0},
            "red_cards": {"home": 0, "away": 0},
            "offsides": {"home": 0, "away": 0},
        },
        "timeline": [],
        "last_seq": 0,
        "updated_at": None,
    }


# ----------------------------------------------------------------------
# Label helpers (display copy for the timeline / events list)
# ----------------------------------------------------------------------
def _team(payload: Dict[str, Any]) -> str:
    return payload.get("team") or ""


def _player(payload: Dict[str, Any]) -> str:
    return payload.get("player") or ""


def _event_label(etype: str, p: Dict[str, Any]) -> str:
    team = _team(p)
    player = _player(p)
    if etype == "shot":
        outcome = p.get("outcome")
        if outcome == "goal":
            return f"Goal, {team}"
        if outcome == "saved":
            return f"Shot saved, {player} ({team})"
        if outcome == "blocked":
            return f"Shot blocked, {player} ({team})"
        if outcome == "post":
            return f"Shot off the post, {player} ({team})"
        return f"Shot off target, {player} ({team})"
    if etype == "foul":
        c = p.get("consequence")
        if c == "penalty":
            return f"Penalty conceded, {team}"
        return f"Foul by {player}, {team}"
    if etype == "card":
        card = (p.get("card") or "yellow").capitalize()
        return f"{card} card, {team}" + (f" — {player}" if player else "")
    if etype == "injury":
        return f"Injury delay, {team}"
    if etype == "substitution":
        return (f"Substitution, {team} — {p.get('player_on')} "
                f"for {p.get('player_off')}")
    if etype == "corner":
        return f"Corner, {team}"
    if etype == "offside":
        return f"Offside, {team}"
    if etype == "var":
        return f"VAR check: {p.get('check')} — {p.get('outcome')}"
    return etype.replace("_", " ").capitalize()


# Timeline entries the fan experience shows (design's "Match events" list);
# shots that are not goals and raw stats snapshots stay out of the timeline.
TIMELINE_TYPES = {
    "shot", "foul", "card", "injury", "substitution",
    "corner", "offside", "var",
}


def apply_event(state: Dict[str, Any], event: Dict[str, Any]) -> bool:
    """Fold one stream event into the state. Returns True if state changed."""
    etype = event.get("type")
    p = event.get("payload", {})
    clock = event.get("match_clock", {})
    match_id = event.get("match_id")

    if state["match_id"] == "?" and match_id:
        state["match_id"] = match_id
    if event.get("seq", 0) <= state.get("last_seq", 0):
        return False  # duplicate / out-of-order — idempotent fold

    state["last_seq"] = event.get("seq", state["last_seq"] + 1)
    state["minute"] = clock.get("minute", state["minute"])
    state["display"] = clock.get("display", state["display"])
    state["period"] = clock.get("period", state["period"])
    state["updated_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds",
    )

    if etype == "match_status":
        status = p.get("status")
        if status == "kickoff":
            state["status"] = "live"
            state["home"] = p.get("home")
            state["away"] = p.get("away")
            state["competition"] = p.get("competition")
            state["venue"] = p.get("venue")
            state["referee"] = p.get("referee")
            state["weather"] = p.get("weather")
            state["attendance"] = p.get("attendance")
        elif status == "half_time":
            state["status"] = "half_time"
        elif status == "second_half_kickoff":
            state["status"] = "live"
        elif status == "full_time":
            state["status"] = "full_time"
            final = p.get("final_stats")
            if final:
                state["stats"] = final
        return True

    side = p.get("side")
    if etype == "shot":
        state["stats"]["shots"][side] = state["stats"]["shots"].get(side, 0) + 1
        if p.get("outcome") in ("goal", "saved", "post"):
            state["stats"]["shots_on_target"][side] = \
                state["stats"]["shots_on_target"].get(side, 0) + 1
        state["stats"]["xg"][side] = round(
            state["stats"]["xg"].get(side, 0.0) + p.get("xg", 0.0), 2,
        )
        if p.get("outcome") == "goal":
            score_after = p.get("score_after")
            if score_after:
                h, a = score_after.split("-")
                state["score"] = {"home": int(h), "away": int(a)}
            else:
                state["score"][side] += 1

    elif etype == "foul":
        state["stats"]["fouls"][side] = state["stats"]["fouls"].get(side, 0) + 1
    elif etype == "card":
        key = "yellow_cards" if p.get("card") == "yellow" else "red_cards"
        state["stats"][key][side] = state["stats"][key].get(side, 0) + 1
    elif etype == "corner":
        state["stats"]["corners"][side] = \
            state["stats"]["corners"].get(side, 0) + 1
    elif etype == "offside":
        state["stats"]["offsides"][side] = \
            state["stats"]["offsides"].get(side, 0) + 1
    elif etype == "stats_snapshot":
        # Authoritative resync from the producer's own projection.
        incoming = p.get("possession")
        for stat, values in p.items():
            if stat == "possession" and isinstance(values, dict):
                state["stats"]["possession"] = {
                    "home": int(values.get("home", 50)),
                    "away": int(values.get("away", 50)),
                }
            elif isinstance(values, dict) and stat in state["stats"]:
                state["stats"][stat] = values
        return True

    if etype in TIMELINE_TYPES:
        et = p.get("event_type", etype)
        state["timeline"].append({
            "seq": event["seq"],
            "minute": state["minute"],
            "display": state["display"],
            "event_type": et,
            "side": side,
            "team": _team(p),
            "player": _player(p),
            "label": _event_label(etype, p),
            "detail": {
                k: p[k] for k in (
                    "outcome", "consequence", "card", "reason", "xg",
                    "score_after", "assist", "is_penalty", "player_on",
                    "player_off", "check", "treatment_seconds",
                ) if k in p
            },
        })
        if len(state["timeline"]) > 300:
            state["timeline"] = state["timeline"][-300:]
    return True


# ----------------------------------------------------------------------
# Redis persistence
# ----------------------------------------------------------------------
def save_state(state: Dict[str, Any]) -> None:
    client = r()
    key = MATCH_KEY.format(match_id=state["match_id"])
    client.set(key, json.dumps(state), ex=MATCH_TTL)
    client.sadd(INDEX_KEY, state["match_id"])
    client.publish(
        CHANNEL.format(match_id=state["match_id"]),
        json.dumps({"match_id": state["match_id"], "seq": state["last_seq"]}),
    )


def load_state(match_id: str) -> Optional[Dict[str, Any]]:
    raw = r().get(MATCH_KEY.format(match_id=match_id))
    return json.loads(raw) if raw else None


def list_matches() -> list[Dict[str, Any]]:
    client = r()
    summaries = []
    for match_id in client.smembers(INDEX_KEY):
        raw = client.get(MATCH_KEY.format(match_id=match_id))
        if raw is None:
            client.srem(INDEX_KEY, match_id)  # expired
            continue
        s = json.loads(raw)
        summaries.append({
            "match_id": s["match_id"],
            "home": s["home"],
            "away": s["away"],
            "competition": s["competition"],
            "status": s["status"],
            "minute": s["minute"],
            "display": s["display"],
            "score": s["score"],
            "updated_at": s["updated_at"],
        })
    summaries.sort(key=lambda m: m.get("updated_at") or "", reverse=True)
    return summaries


def ingest_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Project one stream event and persist. Returns the new state or None."""
    match_id = event.get("match_id")
    if not match_id:
        return None
    state = load_state(match_id) or new_state(match_id)
    if apply_event(state, event):
        save_state(state)
        return state
    return None
