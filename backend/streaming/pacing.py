"""Shared, testable replay timing. A larger speed multiplier is FASTER."""
import argparse
import math
from dataclasses import dataclass
from datetime import datetime


def finite_number(value, *, positive=False):
    try:
        number = float(value)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("expected a number") from error
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        bound = "greater than 0" if positive else "greater than or equal to 0"
        raise argparse.ArgumentTypeError(f"value must be finite and {bound}")
    return number


def replay_speed(value):
    return finite_number(value)


def positive_seconds(value):
    return finite_number(value, positive=True)


def add_timing_arguments(parser):
    timing = parser.add_mutually_exclusive_group()
    timing.add_argument("--speed", type=replay_speed,
                        help="match-clock multiplier: 1 = real time, 30 = faster, 0.5 = slower, 0 = instant")
    timing.add_argument("--duration", type=positive_seconds, metavar="SECONDS",
                        help="spread the match over this many seconds (e.g. 600 = ten-minute demo)")
    timing.add_argument("--event-interval", type=positive_seconds, metavar="SECONDS",
                        help="wait this long between EVERY event (e.g. 5 = easy-to-follow demo)")


def event_offsets(events):
    """Match-clock seconds, including first-half added time, without the break.

    Old saved files have artificially short recorded_at gaps. Prefer their
    structured football clocks; fall back to timestamps for other producers.
    Several facts at the same clock time deliberately share an offset.
    """
    if not events:
        return []
    clocks = [event.get("match_clock", {}) for event in events]
    has_clocks = all(isinstance(c.get("minute"), (int, float)) for c in clocks)
    positions = []
    previous = 0.0
    first_half_end = 45 * 60.0
    second_half = False
    for event, clock in zip(events, clocks):
        if has_clocks:
            raw = clock["minute"] * 60.0 + clock.get("second", 0)
            if clock.get("period") == "SECOND_HALF":
                second_half = True
            if second_half:
                raw += max(0, first_half_end - 45 * 60)
            else:
                first_half_end = max(first_half_end, raw)
        else:
            raw = datetime.fromisoformat(event["recorded_at"].replace("Z", "+00:00")).timestamp()
        previous = max(previous, raw)
        positions.append(previous)
    return [position - positions[0] for position in positions]


@dataclass(frozen=True)
class ReplayTiming:
    speed: float = 1.0
    duration: float | None = None
    event_interval: float | None = None

    def __post_init__(self):
        finite_number(self.speed)
        for value in (self.duration, self.event_interval):
            if value is not None:
                positive_seconds(value)
        if self.duration is not None and self.event_interval is not None:
            raise ValueError("Choose duration OR event interval, not both")

    @classmethod
    def from_args(cls, args):
        return cls(speed=1.0 if args.speed is None else args.speed,
                   duration=args.duration, event_interval=args.event_interval)

    def delays(self, events):
        if not events:
            return []
        if self.event_interval is not None:
            return [0.0] + [self.event_interval] * (len(events) - 1)
        offsets = event_offsets(events)
        if self.duration is not None:
            if offsets[-1] > 0:
                offsets = [offset / offsets[-1] * self.duration for offset in offsets]
            else:
                offsets = [i * self.duration / max(1, len(events) - 1) for i in range(len(events))]
        elif self.speed == 0:
            return [0.0] * len(events)
        else:
            offsets = [offset / self.speed for offset in offsets]
        return [0.0] + [max(0, end - start) for start, end in zip(offsets, offsets[1:])]

    def describe(self, events):
        seconds = sum(self.delays(events))
        if self.event_interval is not None:
            mode = f"{self.event_interval:g}s between every event"
        elif self.duration is not None:
            mode = f"target duration {self.duration:g}s"
        else:
            mode = "instant (no waits)" if self.speed == 0 else f"{self.speed:g}× match-clock speed"
        return (f"Pacing: {mode}; scheduled waits {seconds / 60:.1f} min "
                f"({seconds:.1f}s). Network/processing time is additional.")
