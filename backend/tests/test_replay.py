import argparse
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from streaming.replay import fresh_replay, paced_events, replay_speed, send_to_eventhub, send_to_redis
from streaming.replay import main as replay_main
from streaming.pacing import ReplayTiming, event_offsets
from synth.generator import build_match, main

TEMP_ROOT = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None


def events():
    return [
        {"match_id": "stream-test", "seq": seq, "type": "match_status",
         "recorded_at": f"2026-10-26T15:{minute:02d}:{second:02d}Z",
         "match_clock": {"display": f"{minute}'"}, "payload": {}}
        for seq, minute, second in [(1, 0, 0), (2, 0, 30), (3, 1, 30)]
    ]


class ReplayTests(unittest.TestCase):
    def publish(self, speed):
        trace = []
        producer = MagicMock()
        producer.__enter__.return_value = producer
        producer.send_batch.side_effect = lambda batch: trace.append("send")
        with (
            patch.dict(os.environ, {"EVENTHUB_CONNECTION_STRING": "test", "EVENTHUB_NAME": "test-hub"}),
            patch("azure.eventhub.EventHubProducerClient.from_connection_string", return_value=producer),
            patch("streaming.replay.time.sleep", side_effect=lambda delay: trace.append(("sleep", delay))),
            redirect_stdout(io.StringIO()),
        ):
            send_to_eventhub(events(), speed)
        return producer, trace

    def test_each_event_is_published_before_next_wait(self):
        producer, trace = self.publish(30)
        self.assertEqual(trace, ["send", ("sleep", 1.0), "send", ("sleep", 2.0), "send"])
        self.assertEqual(producer.send_batch.call_count, 3)

    def test_match_partition_key_preserves_event_order(self):
        producer, _ = self.publish(0)
        for call in producer.create_batch.call_args_list:
            self.assertEqual(call.kwargs, {"partition_key": "stream-test"})

    def test_zero_speed_has_no_sleeps(self):
        _, trace = self.publish(0)
        self.assertEqual(trace, ["send", "send", "send"])

    def test_kickoff_is_immediate(self):
        with patch("streaming.replay.time.sleep") as sleep:
            replay = paced_events(events(), 1)
            self.assertEqual(next(replay)["seq"], 1)
            sleep.assert_not_called()

    def test_invalid_speeds_are_rejected(self):
        for speed in ("-1", "nan", "inf"):
            with self.assertRaises(argparse.ArgumentTypeError):
                replay_speed(speed)

    def test_local_replay_uses_same_pacing_and_accepts_z_timestamps(self):
        trace = []
        with (
            patch("streaming.replay.ingest_event", side_effect=lambda e: trace.append(e["seq"])),
            patch("streaming.replay.time.sleep", side_effect=lambda d: trace.append(("sleep", d))),
            redirect_stdout(io.StringIO()),
        ):
            send_to_redis(events(), 30)
        self.assertEqual(trace, [1, ("sleep", 1.0), 2, ("sleep", 2.0), 3])


class GeneratorTests(unittest.TestCase):
    def test_repeated_teams_get_unique_match_ids(self):
        first = build_match(seed=42)
        second = build_match(seed=42)
        self.assertEqual(first.home, second.home)
        self.assertEqual(first.away, second.away)
        self.assertEqual(first.stats, second.stats)
        self.assertNotEqual(first.match_id, second.match_id)
        self.assertEqual(first.lines[0]["match_id"], first.match_id)
        self.assertEqual(second.lines[0]["match_id"], second.match_id)

    def test_generate_and_stream_is_one_command(self):
        with (
            tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,
            patch("synth.generator.send_to_event_hubs") as publish,
            redirect_stdout(io.StringIO()),
        ):
            path = Path(directory, "match.jsonl")
            code = main(["--seed", "42", "--out", str(path), "--stream", "--speed", "30"])
            self.assertEqual(code, 0)
            self.assertTrue(path.exists())
            self.assertEqual(publish.call_args.args[1].speed, 30)
            self.assertEqual(publish.call_args.args[0][0]["payload"]["status"], "kickoff")

    def test_generate_and_replay_locally(self):
        with (
            tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,
            patch("streaming.replay.send_to_redis") as publish,
            redirect_stdout(io.StringIO()),
        ):
            code = main(["--seed", "42", "--out", str(Path(directory, "match.jsonl")),
                         "--to-redis", "--speed", "0"])
            self.assertEqual(code, 0)
            self.assertEqual(publish.call_args.args[1].speed, 0)

    def test_save_only_explicitly_reports_no_live_publication(self):
        output = io.StringIO()
        with (
            tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,
            patch("synth.generator.send_to_event_hubs") as publish,
            redirect_stdout(output),
        ):
            code = main(["--seed", "42", "--out", str(Path(directory, "match.jsonl"))])
            self.assertEqual(code, 0)
            publish.assert_not_called()
            self.assertIn("Saved only — no live events published", output.getvalue())

    def test_live_archive_is_hidden_until_publishing_finishes(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, redirect_stdout(io.StringIO()):
            target = Path(directory, "live.jsonl")
            pending = target.with_suffix(".jsonl.pending")
            def publish(lines, timing):
                self.assertTrue(pending.exists())
                self.assertFalse(target.exists())
            with patch("streaming.replay.send_to_redis", side_effect=publish):
                self.assertEqual(main(["--out", str(target), "--to-redis", "--duration", "600"]), 0)
            self.assertTrue(target.exists())
            self.assertFalse(pending.exists())

    def test_interrupted_replay_preserves_pending_file(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, redirect_stdout(io.StringIO()):
            target = Path(directory, "live.jsonl")
            with patch("streaming.replay.send_to_redis", side_effect=KeyboardInterrupt):
                self.assertEqual(main(["--out", str(target), "--to-redis"]), 130)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_suffix(".jsonl.pending").exists())

    def test_printed_seed_reproduces_generated_match(self):
        first = build_match()
        second = build_match(seed=first.seed)
        self.assertEqual(first.home, second.home)
        self.assertEqual(first.stats, second.stats)
        self.assertEqual(first.score, second.score)

    def test_environment_loads_before_redis_projection_import(self):
        script = """
import os
import dotenv
os.environ.pop('REDIS_URL', None)
def settings(*args, **kwargs):
    os.environ['REDIS_URL'] = 'redis://configured-demo-host:6379/0'
dotenv.load_dotenv = settings
import synth.generator
from streaming.state import _pool
assert _pool.connection_kwargs['host'] == 'configured-demo-host'
"""
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_timestamps_follow_football_clock(self):
        match = build_match(seed=42)
        stamps = [datetime.fromisoformat(e["recorded_at"].replace("Z", "+00:00")).timestamp()
                  for e in match.lines]
        self.assertEqual(stamps, sorted(stamps))
        self.assertGreaterEqual(stamps[-1] - stamps[0], 90 * 60)
        self.assertEqual(match.lines[0]["match_clock"]["minute"], 0)
        self.assertTrue(any(e["payload"].get("status") == "second_half_kickoff" for e in match.lines))

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, redirect_stderr(io.StringIO()):
            path = Path(directory, "existing.jsonl")
            path.write_text("user data")
            with self.assertRaises(SystemExit):
                main(["--out", str(path)])
            self.assertEqual(path.read_text(), "user data")

    def test_dry_run_writes_nothing_and_does_not_publish(self):
        with (tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,
              patch("synth.generator.send_to_event_hubs") as publish,
              redirect_stdout(io.StringIO()) as output):
            target = Path(directory, "dry.jsonl")
            code = main(["--seed", "42", "--out", str(target), "--duration", "600", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertEqual(list(Path(directory).iterdir()), [])
            publish.assert_not_called()
            self.assertIn("600.0s", output.getvalue())

    def test_conflicting_or_invalid_controls_fail_before_writing(self):
        cases = [["--duration", "600", "--speed", "30"], ["--duration", "0"],
                 ["--event-interval", "-1"], ["--event-interval", "nan"],
                 ["--speed", "inf"]]
        for case in cases:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--dry-run", *case])

    def test_timing_on_save_only_is_not_silently_ignored(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--duration", "600"])

    def test_failed_publication_preserves_recovery_file(self):
        with (tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,
              patch("streaming.replay.send_to_redis", side_effect=RuntimeError("offline")),
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO())):
            target = Path(directory, "live.jsonl")
            self.assertEqual(main(["--out", str(target), "--to-redis"]), 1)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_suffix(".jsonl.pending").exists())


class ReplayCliTests(unittest.TestCase):
    def test_dry_run_has_no_redis_or_azure_calls(self):
        with (patch("streaming.replay.load_jsonl", return_value=events()),
              patch("streaming.replay.load_state") as state,
              patch("streaming.replay.send_to_redis") as publish,
              redirect_stdout(io.StringIO())):
            self.assertEqual(replay_main(["--file", "demo.jsonl", "--duration", "600", "--dry-run"]), 0)
        state.assert_not_called()
        publish.assert_not_called()

    def test_projected_local_match_requires_fresh_ids(self):
        with (patch("streaming.replay.load_jsonl", return_value=events()),
              patch("streaming.replay.load_state", return_value={"last_seq": 3}),
              patch("streaming.replay.send_to_redis") as publish,
              redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()),
              self.assertRaises(SystemExit)):
            replay_main(["--file", "demo.jsonl"])
        publish.assert_not_called()


class TimingTests(unittest.TestCase):
    def test_higher_speed_reduces_delay_and_fractional_speed_slows_down(self):
        lines = events()
        self.assertEqual(sum(ReplayTiming(speed=1).delays(lines)), 90)
        self.assertEqual(sum(ReplayTiming(speed=30).delays(lines)), 3)
        self.assertEqual(sum(ReplayTiming(speed=.5).delays(lines)), 180)

    def test_duration_controls_total_scheduled_waits(self):
        delays = ReplayTiming(duration=600).delays(events())
        self.assertEqual(delays, [0, 200, 400])

    def test_event_interval_separates_simultaneous_facts(self):
        lines = events()
        for line in lines:
            line["recorded_at"] = lines[0]["recorded_at"]
        self.assertEqual(ReplayTiming(event_interval=5).delays(lines), [0, 5, 5])

    def test_clock_overrides_artificial_old_timestamps(self):
        lines = events()
        for line, minute in zip(lines, [0, 45, 90]):
            line["match_clock"].update(minute=minute, second=0)
        self.assertEqual(sum(ReplayTiming(speed=1).delays(lines)), 5400)

    def test_first_half_added_time_survives_clock_reset(self):
        clocks = [(0, "FIRST_HALF"), (45, "FIRST_HALF"), (48, "FIRST_HALF"),
                  (45, "SECOND_HALF"), (46, "SECOND_HALF"), (90, "SECOND_HALF")]
        lines = [{"match_clock": {"minute": m, "second": 0, "period": p}} for m, p in clocks]
        self.assertEqual(event_offsets(lines), [0, 2700, 2880, 2880, 2940, 5580])

    def test_empty_and_single_event_are_immediate(self):
        timing = ReplayTiming(duration=600)
        self.assertEqual(timing.delays([]), [])
        self.assertEqual(timing.delays(events()[:1]), [0])

    def test_fresh_replay_does_not_mutate_source_or_clear_state(self):
        lines = events()
        fresh = fresh_replay(lines)
        self.assertEqual(lines[0]["match_id"], "stream-test")
        self.assertNotEqual(lines[0]["match_id"], fresh[0]["match_id"])
        self.assertEqual(len({e["match_id"] for e in fresh}), 1)
        self.assertEqual(fresh[0]["seq"], lines[0]["seq"])

    def test_slow_interval_is_applied_by_both_publishers(self):
        trace = []
        with patch("streaming.replay.time.sleep", side_effect=trace.append):
            list(paced_events(events(), ReplayTiming(event_interval=5)))
        self.assertEqual(trace, [5, 5])


class ConsumerDiagnosticsTests(unittest.TestCase):
    def test_missing_consumer_group_has_actionable_error(self):
        from streaming.consumer import on_error
        output = io.StringIO()
        with redirect_stderr(output):
            on_error(None, RuntimeError("amqp:not-found: messaging entity could not be found"))
        self.assertIn("Consumer groups", output.getvalue())
        self.assertIn("restart this consumer", output.getvalue())

    def test_other_errors_are_reported_without_claiming_group_is_missing(self):
        from streaming.consumer import on_error
        output = io.StringIO()
        with redirect_stderr(output):
            on_error(None, RuntimeError("connection timed out"))
        self.assertIn("connection timed out", output.getvalue())
        self.assertNotIn("does not exist", output.getvalue())


if __name__ == "__main__":
    unittest.main()
