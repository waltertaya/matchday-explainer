import argparse
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from streaming.replay import paced_events, replay_speed, send_to_eventhub, send_to_redis
from synth.generator import build_match, main


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
            tempfile.TemporaryDirectory(dir="/tmp/opencode") as directory,
            patch("synth.generator.send_to_event_hubs") as publish,
            redirect_stdout(io.StringIO()),
        ):
            path = Path(directory, "match.jsonl")
            code = main(["--seed", "42", "--out", str(path), "--stream", "--speed", "30"])
            self.assertEqual(code, 0)
            self.assertTrue(path.exists())
            self.assertEqual(publish.call_args.args[1], 30)
            self.assertEqual(publish.call_args.args[0][0]["payload"]["status"], "kickoff")

    def test_generate_and_replay_locally(self):
        with (
            tempfile.TemporaryDirectory(dir="/tmp/opencode") as directory,
            patch("streaming.replay.send_to_redis") as publish,
            redirect_stdout(io.StringIO()),
        ):
            code = main(["--seed", "42", "--out", str(Path(directory, "match.jsonl")),
                         "--to-redis", "--speed", "0"])
            self.assertEqual(code, 0)
            self.assertEqual(publish.call_args.args[1], 0)

    def test_save_only_explicitly_reports_no_live_publication(self):
        output = io.StringIO()
        with (
            tempfile.TemporaryDirectory(dir="/tmp/opencode") as directory,
            patch("synth.generator.send_to_event_hubs") as publish,
            redirect_stdout(output),
        ):
            code = main(["--seed", "42", "--out", str(Path(directory, "match.jsonl"))])
            self.assertEqual(code, 0)
            publish.assert_not_called()
            self.assertIn("Saved only — no live events published", output.getvalue())


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
