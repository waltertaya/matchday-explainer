"""Synthetic full-match event generator for Matchday Explainer.

Produces JSONL event streams shaped for Azure Event Hubs:

    Match events (this stream)
        -> Match state service (rolling score, stats, timeline projection)
            -> Summary / Stat explainer / Referee RAG (grounded generation)
                -> Grounding verifier -> Fan experience (React front end)

Design principles
-----------------
* One JSON object per line = one immutable fact (append-only log).
* Every record shares an envelope (schema_version, match_id, seq,
  recorded_at, match_clock, type) so consumers can order and replay.
* Stats are ALWAYS a projection of the event log: `stats_snapshot`
  records are derived from the events emitted so far, never invented
  independently. That is what lets the grounding verifier later check
  every generated sentence against the stream.
* Event-type values match the front end's EventType vocabulary
  (goal, yellow-card, foul, free-kick, injury, corner, offside,
  substitution, penalty, var) plus shot / status / stats_snapshot.
* recorded_at advances in (near) real time from kick-off, so a replay
  of the JSONL into Event Hubs can be paced at 1x speed.

Usage
-----
    python -m synth.generator                       # random match -> data/synth/*.jsonl
    python -m synth.generator --seed 42            # reproducible match
    python -m synth.generator --out path.jsonl     # explicit output file
    python -m synth.generator --stream             # also send to Event Hubs
                                                   # (needs azure-eventhub and
                                                   # EVENTHUB_CONNECTION_STRING /
                                                   # EVENTHUB_NAME env vars)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"

# Event-type vocabulary (kept compatible with the front end's EventType).
SHOT_OUTCOMES = ("goal", "saved", "off_target", "blocked", "post")
FOUL_CONSEQUENCES = ("free_kick", "penalty", "yellow_card", "red_card", "advantage")
WEATHER = ("Clear", "Overcast", "Light rain", "Windy", "Humid")

FIRST_NAMES = [
    "Marco", "Dane", "Yusuf", "Leon", "Andres", "Kwame", "Tomas", "Ravi",
    "Nikola", "Emeka", "Jude", "Santi", "Milo", "Idris", "Bruno", "Kai",
    "Owen", "Felix", "Amir", "Diego", "Jonas", "Elias", "Rafa", "Cole",
]
LAST_NAMES = [
    "Okafor", "Mercer", "Silva", "Tanaka", "Novak", "Diallo", "Reyes",
    "Kovac", "Lindqvist", "Barros", "Whitlock", "Osei", "Marchetti",
    "Duarte", "Keller", "Nakamura", "Ferreira", "Ashworth", "Sadiq",
    "Moreno", "Vidic", "Halloran", "Petrov", "Baptiste",
]

TEAMS = [
    ("Northgate FC", "NFC"), ("Harbour United", "HBU"),
    ("Riverside Athletic", "RSA"), ("Kingsbridge Town", "KBT"),
    ("Vale Rovers", "VLR"), ("Ashford City", "ASH"),
    ("Eastmoor Wanderers", "EMW"), ("Stonebrook United", "STU"),
    ("Redcliffe Rangers", "RCR"), ("Fallowford FC", "FWF"),
    ("Highgate Comets", "HGC"), ("Marsh End", "MRE"),
]
COMPETITIONS = ["Premier North", "Championship", "Cup Quarter-final"]
VENUES = [
    "Northgate Park", "Harbour Dock Arena", "Riverside Ground",
    "Kingsbridge Stadium", "The Vale", "Ashford Arena",
    "Eastmoor Fields", "Stonebrook Park",
]
REFEREES = [
    "R. Calloway", "M. Ferrand", "T. Osei", "L. Grimaldi", "S. Vance",
    "P. Lindgren", "A. Beaumont",
]

POSITIONS = [
    ("GK", 1), ("DF", 2), ("DF", 3), ("DF", 4), ("DF", 5),
    ("MF", 6), ("MF", 8), ("MF", 10), ("FW", 7), ("FW", 9), ("FW", 11),
]
BODY_PARTS = ["left foot", "right foot", "header"]


class MatchSimulator:
    """Simulates one full 90-minute match as an append-only event stream."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.seed = seed if seed is not None else self.rng.randrange(2**31)

        home, away = self.rng.sample(TEAMS, 2)
        self.home = {"name": home[0], "short": home[1]}
        self.away = {"name": away[0], "short": away[1]}
        self.match_id = "synth-{}-{}-{}".format(
            datetime.now(timezone.utc).strftime("%Y%m%d"),
            home[1].lower(), away[1].lower(),
        )
        self.competition = self.rng.choice(COMPETITIONS)
        self.venue = self.rng.choice(VENUES)
        self.referee = self.rng.choice(REFEREES)
        self.kickoff_dt = datetime.now(timezone.utc).replace(
            hour=15, minute=0, second=0, microsecond=0,
        )

        # Team strength drives possession bias and shot share.
        self.home_strength = self.rng.uniform(0.42, 0.58)

        self.squads = {s: self._make_squad() for s in ("home", "away")}

        # Rolling state — the "match state" projection.
        self.seq = 0
        self.elapsed_seconds = 0.0          # match clock for recorded_at
        self.score = {"home": 0, "away": 0}
        self.stats = {
            "possession": {"home": 50, "away": 50},
            "shots": {"home": 0, "away": 0},
            "shots_on_target": {"home": 0, "away": 0},
            "xg": {"home": 0.0, "away": 0.0},
            "fouls": {"home": 0, "away": 0},
            "corners": {"home": 0, "away": 0},
            "yellow_cards": {"home": 0, "away": 0},
            "red_cards": {"home": 0, "away": 0},
            "offsides": {"home": 0, "away": 0},
        }
        self.lines: List[Dict[str, Any]] = []
        self.foul_ids_since_card = {"home": 0, "away": 0}

    # ------------------------------------------------------------------
    # Squad / player helpers
    # ------------------------------------------------------------------
    def _make_squad(self) -> List[Dict[str, Any]]:
        used = set()
        squad = []
        for pos, number in POSITIONS:
            while True:
                name = "{} {}".format(
                    self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES),
                )
                if name not in used:
                    used.add(name)
                    break
            squad.append({"name": name, "number": number, "position": pos})
        return squad

    def _pick_player(self, side: str, weighted_attacking: bool = False) -> Dict[str, Any]:
        squad = self.squads[side]
        if weighted_attacking:
            # Forwards/mids shoot and score more; defenders foul more.
            weights = [1, 2, 2, 2, 3, 4, 5, 6, 7, 9, 6] if side == "home" else None
            if weights is None:
                weights = [1, 2, 2, 2, 3, 4, 5, 6, 7, 9, 6]
            player = self.rng.choices(squad, weights=weights, k=1)[0]
        else:
            weights = [1, 4, 4, 4, 4, 3, 3, 2, 1, 1, 1]
            player = self.rng.choices(squad, weights=weights, k=1)[0]
        return player

    def _team_of(self, side: str) -> str:
        return self.home["name"] if side == "home" else self.away["name"]

    def _other(self, side: str) -> str:
        return "away" if side == "home" else "home"

    # ------------------------------------------------------------------
    # Envelope / emission
    # ------------------------------------------------------------------
    def _clock(self, minute: int, second: int, half: str) -> Dict[str, Any]:
        added = minute > 45 if half == "FIRST_HALF" else minute > 90
        base = 45 if half == "FIRST_HALF" else 90
        display = f"{base}+{minute - base}'" if added else f"{minute}'"
        return {
            "minute": minute,
            "second": second,
            "period": half,
            "added_time": added,
            "display": display,
        }

    def _emit(
        self,
        etype: str,
        payload: Dict[str, Any],
        minute: int,
        second: int,
        half: str,
    ) -> None:
        self.seq += 1
        self.elapsed_seconds += self.rng.uniform(8, 45)  # pace the replay
        clock = self._clock(minute, second, half)
        self.lines.append({
            "schema_version": SCHEMA_VERSION,
            "event_id": f"{self.match_id}-{self.seq:04d}",
            "match_id": self.match_id,
            "seq": self.seq,
            "recorded_at": (
                self.kickoff_dt + timedelta(seconds=self.elapsed_seconds)
            ).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "match_clock": clock,
            "type": etype,
            "payload": payload,
        })

    def _emit_stats_snapshot(self, minute: int, second: int, half: str) -> None:
        pos_home = int(round(self.stats["possession"]["home"]))
        snapshot = json.loads(json.dumps(self.stats))  # deep copy
        snapshot["possession"] = {"home": pos_home, "away": 100 - pos_home}
        snapshot["xg"] = {
            s: round(self.stats["xg"][s], 2) for s in ("home", "away")
        }
        self._emit("stats_snapshot", snapshot, minute, second, half)

    # ------------------------------------------------------------------
    # Event generators
    # ------------------------------------------------------------------
    def _emit_shot(self, minute: int, second: int, half: str,
                   force_side: Optional[str] = None,
                   force_penalty: bool = False) -> None:
        side = force_side or (
            "home" if self.rng.random() < self.home_strength else "away"
        )
        player = self._pick_player(side, weighted_attacking=True)
        is_penalty = force_penalty or self.rng.random() < 0.015
        if is_penalty:
            xg = 0.76
        else:
            xg = round(self.rng.uniform(0.02, 0.20), 2)
        outcome = "goal" if self.rng.random() < xg else self.rng.choices(
            ["saved", "off_target", "blocked", "post"],
            weights=[38, 32, 22, 8], k=1,
        )[0]

        self.stats["shots"][side] += 1
        if outcome in ("goal", "saved", "post"):
            self.stats["shots_on_target"][side] += 1
        self.stats["xg"][side] += xg

        payload: Dict[str, Any] = {
            "event_type": "shot",
            "side": side,
            "team": self._team_of(side),
            "player": player["name"],
            "player_number": player["number"],
            "outcome": outcome,
            "is_penalty": is_penalty,
            "xg": xg,
            "body_part": self.rng.choice(BODY_PARTS),
            "distance_m": (
                11 if is_penalty else self.rng.randint(6, 32)
            ),
        }
        if outcome == "goal":
            self.score[side] += 1
            payload["score_after"] = f"{self.score['home']}-{self.score['away']}"
            if not is_penalty and self.rng.random() < 0.7:
                payload["assist"] = self._pick_player(side)["name"]
            self._emit("shot", payload, minute, second, half)
            # VAR check on tight goals occasionally.
            if self.rng.random() < 0.15:
                self._emit_var(minute, second, half, check="goal",
                               outcome="confirmed", side=side)
        else:
            self._emit("shot", payload, minute, second, half)

    def _emit_foul(self, minute: int, second: int, half: str) -> None:
        fouling_side = self.rng.choice(["home", "away"])
        player = self._pick_player(fouling_side)
        self.stats["fouls"][fouling_side] += 1
        self.foul_ids_since_card[fouling_side] += 1

        # Escalation: repeated fouls by the same team raise card odds.
        card_odds = min(0.08 + 0.05 * self.foul_ids_since_card[fouling_side], 0.45)
        roll = self.rng.random()
        if roll < 0.008:
            consequence = "red_card"
        elif roll < 0.008 + 0.02:
            consequence = "penalty"
        elif roll < 0.008 + 0.02 + card_odds:
            consequence = "yellow_card"
        else:
            consequence = "free_kick"

        payload = {
            "event_type": "foul",
            "side": fouling_side,
            "team": self._team_of(fouling_side),
            "player": player["name"],
            "player_number": player["number"],
            "consequence": consequence,
            "against": self._pick_player(self._other(fouling_side))["name"],
            "zone": self.rng.choice(
                ["defensive third", "middle third", "attacking third"],
            ),
        }
        self._emit("foul", payload, minute, second, half)

        if consequence == "yellow_card":
            self._emit_card(minute, second, half, fouling_side, player, "yellow")
        elif consequence == "red_card":
            self._emit_card(minute, second, half, fouling_side, player, "red")
        elif consequence == "penalty":
            # The awarded penalty is taken immediately by the fouled team.
            self._emit_shot(minute, second, half,
                            force_side=self._other(fouling_side),
                            force_penalty=True)
        self.foul_ids_since_card[fouling_side] = (
            0 if consequence in ("yellow_card", "red_card") else
            self.foul_ids_since_card[fouling_side]
        )

    def _emit_card(
        self, minute: int, second: int, half: str,
        side: str, player: Dict[str, Any], card: str,
    ) -> None:
        key = "yellow_cards" if card == "yellow" else "red_cards"
        self.stats[key][side] += 1
        self._emit(
            "card",
            {
                "event_type": f"{card}-card",
                "side": side,
                "team": self._team_of(side),
                "player": player["name"],
                "player_number": player["number"],
                "card": card,
                "reason": self.rng.choice([
                    "reckless challenge", "dissent", "tactical foul",
                    "unsporting behaviour", "delaying the restart",
                ]),
            },
            minute, second, half,
        )

    def _emit_var(
        self, minute: int, second: int, half: str,
        check: str, outcome: str, side: str,
    ) -> None:
        self._emit(
            "var",
            {
                "event_type": "var",
                "side": side,
                "team": self._team_of(side),
                "check": check,
                "outcome": outcome,
                "delay_seconds": self.rng.randint(45, 180),
            },
            minute, second, half,
        )

    def _emit_simple(
        self, etype: str, minute: int, second: int, half: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        side = self.rng.choice(["home", "away"])
        player = self._pick_player(side)
        payload: Dict[str, Any] = {
            "event_type": etype,
            "side": side,
            "team": self._team_of(side),
            "player": player["name"],
            "player_number": player["number"],
        }
        if extra:
            payload.update(extra)
        if etype == "corner":
            self.stats["corners"][side] += 1
        elif etype == "offside":
            self.stats["offsides"][side] += 1
        elif etype == "injury":
            payload["treatment_seconds"] = self.rng.choice([60, 90, 120, 180])
        self._emit(etype, payload, minute, second, half)

    def _emit_substitution(self, minute: int, second: int, half: str) -> None:
        side = self.rng.choice(["home", "away"])
        off = self._pick_player(side)
        while True:
            on = self._make_squad()[self.rng.randint(0, 10)]
            if on["name"] not in [p["name"] for p in self.squads[side]]:
                break
        self._emit(
            "substitution",
            {
                "event_type": "substitution",
                "side": side,
                "team": self._team_of(side),
                "player_off": off["name"],
                "player_off_number": off["number"],
                "player_on": on["name"],
                "player_on_number": on["number"],
                "reason": self.rng.choice(
                    ["tactical", "injury", "fresh legs"],
                ),
            },
            minute, second, half,
        )

    def _emit_status(
        self, status: str, minute: int, second: int, half: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "status": status,
            "score": f"{self.score['home']}-{self.score['away']}",
        }
        if extra:
            payload.update(extra)
        self._emit("match_status", payload, minute, second, half)

    def _tick_possession(self) -> None:
        # Random walk biased by team strength, clamped to a sane band.
        drift = (self.home_strength - 0.5) * 0.6 + self.rng.uniform(-1.2, 1.2)
        pos = min(68.0, max(32.0, self.stats["possession"]["home"] + drift))
        self.stats["possession"]["home"] = pos
        self.stats["possession"]["away"] = 100.0 - pos

    # ------------------------------------------------------------------
    # Main simulation
    # ------------------------------------------------------------------
    def generate(self) -> List[Dict[str, Any]]:
        rng = self.rng

        self._emit_status(
            "kickoff", 1, 0, "FIRST_HALF",
            {
                "competition": self.competition,
                "venue": self.venue,
                "referee": self.referee,
                "weather": rng.choice(WEATHER),
                "attendance": rng.randrange(18000, 62000, 500),
                "home": self.home,
                "away": self.away,
            },
        )

        stoppage_first = rng.randint(1, 4)
        stoppage_second = rng.randint(3, 8)
        sub_minutes = {
            "home": sorted(rng.sample(range(46, 85), rng.randint(3, 5))),
            "away": sorted(rng.sample(range(46, 85), rng.randint(3, 5))),
        }

        for half, start, end, stoppage in (
            ("FIRST_HALF", 1, 45, stoppage_first),
            ("SECOND_HALF", 46, 90, stoppage_second),
        ):
            minutes = list(range(start, end + 1)) + [
                end + i for i in range(1, stoppage + 1)
            ]
            for minute in minutes:
                # A few seconds within the minute for ordering realism.
                second = rng.randint(0, 59)
                self._tick_possession()

                if half == "SECOND_HALF" and sub_minutes["home"] and minute >= sub_minutes["home"][0]:
                    sub_minutes["home"].pop(0)
                    self._emit_substitution(minute, second, half)
                if half == "SECOND_HALF" and sub_minutes["away"] and minute >= sub_minutes["away"][0]:
                    sub_minutes["away"].pop(0)
                    self._emit_substitution(minute, second, half)

                # Per-minute event probabilities (stoppage time is calmer).
                calm = 0.5 if minute > end else 1.0
                if rng.random() < 0.26 * calm:
                    self._emit_shot(minute, second, half)
                if rng.random() < 0.24 * calm:
                    self._emit_foul(minute, second, half)
                if rng.random() < 0.10 * calm:
                    self._emit_simple("corner", minute, second, half)
                if rng.random() < 0.05 * calm:
                    self._emit_simple("offside", minute, second, half)
                if rng.random() < 0.008 * calm:
                    self._emit_simple("injury", minute, second, half)

                # Rolling stats snapshot every 5 minutes.
                if minute % 5 == 0:
                    self._emit_stats_snapshot(minute, second, half)

            if half == "FIRST_HALF":
                self._emit_status(
                    "half_time", 45 + stoppage_first, 0, "FIRST_HALF",
                    {"stoppage_announced": stoppage_first},
                )
                self._emit_stats_snapshot(45 + stoppage_first, 0, "FIRST_HALF")

        self._emit_stats_snapshot(90 + stoppage_second, 0, "SECOND_HALF")
        self._emit_status(
            "full_time", 90 + stoppage_second, 0, "SECOND_HALF",
            {
                "stoppage_announced": stoppage_second,
                "final_stats": {
                    k: {s: (round(v, 2) if isinstance(v, float) else v)
                        for s, v in d.items()}
                    for k, d in self.stats.items()
                },
            },
        )
        return self.lines

    # ------------------------------------------------------------------
    # Consistency validation (proves stats are a projection of events)
    # ------------------------------------------------------------------
    def validate(self) -> List[str]:
        problems = []
        goals = {"home": 0, "away": 0}
        shots = {"home": 0, "away": 0}
        fouls = {"home": 0, "away": 0}
        corners = {"home": 0, "away": 0}
        yellow = {"home": 0, "away": 0}
        xg = {"home": 0.0, "away": 0.0}
        seqs = []
        for line in self.lines:
            seqs.append(line["seq"])
            p = line["payload"]
            if line["type"] == "shot":
                shots[p["side"]] += 1
                xg[p["side"]] += p["xg"]
                if p["outcome"] == "goal":
                    goals[p["side"]] += 1
            elif line["type"] == "foul":
                fouls[p["side"]] += 1
            elif line["type"] == "corner":
                corners[p["side"]] += 1
            elif line["type"] == "card" and p["card"] == "yellow":
                yellow[p["side"]] += 1
        ft = [l for l in self.lines if l["type"] == "match_status"
              and l["payload"]["status"] == "full_time"][0]
        final = ft["payload"]["final_stats"]
        if goals != self.score:
            problems.append(f"score mismatch: {goals} vs {self.score}")
        if shots != final["shots"]:
            problems.append("shots mismatch with final stats")
        if fouls != final["fouls"]:
            problems.append("fouls mismatch with final stats")
        if corners != final["corners"]:
            problems.append("corners mismatch with final stats")
        if yellow != final["yellow_cards"]:
            problems.append("yellow cards mismatch with final stats")
        for s in ("home", "away"):
            if abs(xg[s] - final["xg"][s]) > 0.01:
                problems.append(f"xG mismatch for {s}")
        if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
            problems.append("seq not strictly increasing")
        return problems


def build_match(seed: Optional[int] = None) -> MatchSimulator:
    sim = MatchSimulator(seed=seed)
    sim.generate()
    return sim


def send_to_event_hubs(lines: List[Dict[str, Any]]) -> None:
    """Optional: push the JSONL batch to Azure Event Hubs.

    Requires: pip install azure-eventhub
    Env: EVENTHUB_CONNECTION_STRING, EVENTHUB_NAME
    """
    try:
        from azure.eventhub import EventHubProducerClient, EventData
    except ImportError:
        print("azure-eventhub not installed — skipping streaming "
              "(pip install azure-eventhub)", file=sys.stderr)
        return
    conn = os.getenv("EVENTHUB_CONNECTION_STRING")
    name = os.getenv("EVENTHUB_NAME")
    if not conn or not name:
        print("EVENTHUB_CONNECTION_STRING / EVENTHUB_NAME not set — skipping",
              file=sys.stderr)
        return
    producer = EventHubProducerClient.from_connection_string(conn, eventhub_name=name)
    with producer:
        batch = producer.create_batch()
        for line in lines:
            try:
                batch.add(EventData(json.dumps(line, separators=(",", ":"))))
            except ValueError:
                producer.send_batch(batch)     # batch full -> flush
                batch = producer.create_batch()
                batch.add(EventData(json.dumps(line, separators=(",", ":"))))
        producer.send_batch(batch)
    print(f"Sent {len(lines)} events to Event Hub '{name}'")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed; omit for a different match every run")
    parser.add_argument("--out", default=None, help="output .jsonl path")
    parser.add_argument("--stream", action="store_true",
                        help="also send events to Azure Event Hubs")
    args = parser.parse_args(argv)

    sim = build_match(seed=args.seed)
    problems = sim.validate()
    for p in problems:
        print(f"VALIDATION PROBLEM: {p}", file=sys.stderr)
    if problems:
        return 1

    out = Path(args.out) if args.out else Path(
        "data/synth/{}.jsonl".format(sim.match_id),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for line in sim.lines:
            fh.write(json.dumps(line, separators=(",", ":")) + "\n")

    ft = sim.lines[-1]["payload"]
    print(f"match_id : {sim.match_id}")
    print(f"file     : {out}")
    print(f"events   : {len(sim.lines)} lines")
    print(f"score    : {sim.home['name']} {ft['score']} {sim.away['name']}")
    print(f"xG       : {sim.stats['xg']['home']:.2f} - "
          f"{sim.stats['xg']['away']:.2f}")
    print("validation: OK (stats are a consistent projection of the events)")

    if args.stream:
        send_to_event_hubs(sim.lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
