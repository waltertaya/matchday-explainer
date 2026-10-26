import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from redis.exceptions import ConnectionError

from api.config import Config
from app import create_app
from rag import embedding
from rag.chunker import chunk_text_by_tokens
from rag.indexing import Indexer
from streaming import consumer

TEMP_ROOT = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None


class ReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            cls.app = create_app()

    def test_ready_does_not_call_ai(self):
        with (patch("api.readiness.mstate.r") as redis,
              patch("api.readiness.db") as database,
              patch("api.readiness.config.OPENAI_API_KEY", "configured")):
            redis.return_value.ping.return_value = True
            database.session.execute.return_value.scalar_one.return_value = 10
            response = self.app.test_client().get("/api/v1/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["checks"]["ai"]["status"], "configured")
        self.assertIn("not probed", response.json["note"])

    def test_degraded_services_are_explained_without_leaking_errors(self):
        with (patch("api.readiness.mstate.r", side_effect=ConnectionError("secret-host")),
              patch("api.readiness.db") as database,
              patch("api.readiness.config.OPENAI_API_KEY", None)):
            database.session.execute.side_effect = RuntimeError("secret-password")
            response = self.app.test_client().get("/api/v1/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["status"], "degraded")
        self.assertNotIn("secret", response.get_data(as_text=True))
        database.session.rollback.assert_called_once()


class ConsumerReliabilityTests(unittest.TestCase):
    def setUp(self):
        consumer._counters.clear()
        consumer._stopping.clear()

    def event(self, full_time=False):
        payload = {"match_id": "test", "type": "match_status", "payload": {
            "status": "full_time" if full_time else "kickoff",
        }}
        return SimpleNamespace(body_as_str=lambda **kwargs: json.dumps(payload))

    def context(self, partition):
        return SimpleNamespace(partition_id=partition, update_checkpoint=MagicMock())

    def test_checkpoints_are_counted_per_partition(self):
        first, second = self.context("0"), self.context("1")
        with patch.object(consumer, "_checkpoint_every", 2), patch.object(consumer, "ingest_event", return_value=None):
            consumer.on_event(first, self.event())
            consumer.on_event(second, self.event())
            first.update_checkpoint.assert_not_called()
            second.update_checkpoint.assert_not_called()
            consumer.on_event(first, self.event())
        first.update_checkpoint.assert_called_once()
        second.update_checkpoint.assert_not_called()

    def test_full_time_flushes_only_after_persistence(self):
        trace = []
        context = self.context("0")
        context.update_checkpoint.side_effect = lambda e: trace.append("checkpoint")
        with patch.object(consumer, "ingest_event", side_effect=lambda e: trace.append("persist")):
            consumer.on_event(context, self.event(full_time=True))
        self.assertEqual(trace, ["persist", "checkpoint"])

    def test_redis_failure_retries_same_event_before_acknowledging(self):
        context = self.context("0")
        with (patch.object(consumer, "ingest_event", side_effect=[ConnectionError(), None]) as ingest,
              patch.object(consumer._stopping, "wait") as wait,
              redirect_stderr(io.StringIO())):
            consumer.on_event(context, self.event(full_time=True))
        self.assertEqual(ingest.call_count, 2)
        wait.assert_called_once_with(2)
        context.update_checkpoint.assert_called_once()

    def test_bad_json_does_not_advance_checkpoint(self):
        context = self.context("0")
        event = SimpleNamespace(body_as_str=lambda **kwargs: "bad json")
        with patch.object(consumer, "ingest_event") as ingest, redirect_stderr(io.StringIO()):
            consumer.on_event(context, event)
        ingest.assert_not_called()
        context.update_checkpoint.assert_not_called()


class EmbeddingCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.seed = Path(self.directory.name, "seed.json")
        self.local = Path(self.directory.name, "local.json")
        self.patches = [patch.object(embedding, "SEED_CACHE", self.seed),
                        patch.object(embedding, "EMBED_CACHE", self.local),
                        patch.object(embedding, "EXPECTED_DIMENSIONS", 2)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        embedding._read_cache.cache_clear()
        self.directory.cleanup()

    def test_seed_file_is_never_modified(self):
        original = '{"seed": [1, 2]}'
        self.seed.write_text(original)
        embedding._save_cache({"seed": [1, 2], "new": [3, 4]})
        self.assertEqual(self.seed.read_text(), original)
        self.assertEqual(json.loads(self.local.read_text()), {"new": [3, 4]})
        self.assertEqual(embedding._load_cache(), {"seed": [1, 2], "new": [3, 4]})

    def test_corrupt_cache_is_ignored(self):
        self.local.write_text("{bad json}")
        with self.assertLogs("rag.embedding", level="WARNING"):
            self.assertEqual(embedding._load_cache(), {})

    def test_duplicate_texts_embed_once_and_reuse_local_cache(self):
        model = "text-embedding-3-small"
        with patch.object(embedding, "OpenAI") as client:
            client.return_value.embeddings.create.return_value = SimpleNamespace(
                data=[SimpleNamespace(embedding=[.1, .2])])
            result = embedding.embed_texts(["law", "law"], model=model)
            repeated = embedding.embed_texts(["law"], model=model)
        client.return_value.embeddings.create.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].tolist(), repeated[0].tolist())
        self.assertNotIn("extra_body", client.return_value.embeddings.create.call_args.kwargs)


class IndexingTests(unittest.TestCase):
    def test_unchanged_document_is_not_reembedded_or_duplicated(self):
        with (patch("rag.indexing.listdir", return_value=["Laws.pdf"]),
              patch("rag.indexing.isfile", return_value=True),
              patch("rag.indexing.Parser") as parser,
              patch("rag.indexing.chunk_text_by_tokens", return_value=["existing passage"]),
              patch("rag.indexing.embed_texts") as embed,
              patch("rag.indexing.db") as database):
            parser.return_value.parse.return_value = ("text", {"source": "Laws.pdf"})
            database.session.execute.return_value.scalars.return_value.all.return_value = ["existing passage"]
            report = Indexer().save()
        self.assertEqual(report, {"indexed": 0, "unchanged": 1, "chunks": 0})
        embed.assert_not_called()
        database.session.add.assert_not_called()
        database.session.commit.assert_called_once()

    def test_invalid_chunk_parameters_fail_instead_of_looping(self):
        for size, overlap in [(0, 0), (10, 10), (10, 11), (10, -1)]:
            with self.assertRaises(ValueError):
                chunk_text_by_tokens("text", chunk_size=size, overlap=overlap)


class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            cls.app = create_app()

    def test_original_source_document_can_be_opened(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, patch("api.ifab_routes.config.IFAB_DIR", directory):
            Path(directory, "Laws of the Game.pdf").write_bytes(b"%PDF-1.7 test")
            response = self.app.test_client().get("/api/v1/ifabs/Laws%20of%20the%20Game.pdf")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/pdf")
            response.close()

    def test_upload_cannot_escape_document_directory_or_overwrite(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, patch("api.ifab_routes.config.IFAB_DIR", directory):
            client = self.app.test_client()
            response = client.post("/api/v1/ifabs", data={"file": (io.BytesIO(b"%PDF-1.7 test"), "../../escape.pdf")})
            self.assertEqual(response.status_code, 201)
            self.assertTrue(Path(directory, "escape.pdf").exists())
            response = client.post("/api/v1/ifabs", data={"file": (io.BytesIO(b"%PDF-1.7 replacement"), "escape.pdf")})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(Path(directory, "escape.pdf").read_bytes(), b"%PDF-1.7 test")


if __name__ == "__main__":
    unittest.main()
