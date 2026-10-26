import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from redis.exceptions import ConnectionError

from api.config import Config
from api.summary import summary_facts
from app import create_app
from streaming import catalog
from streaming.state import apply_event, new_state


def fixture():
    state = new_state("test-match")
    state.update(home={"name": "Home FC", "short": "HFC"},
                 away={"name": "Away FC", "short": "AFC"},
                 status="live", minute=30, last_seq=4,
                 score={"home": 2, "away": 0})
    state["stats"]["possession"] = {"home": 40, "away": 60}
    state["timeline"] = [
        {"seq": seq, "minute": minute, "display": f"{minute}'", "event_type": kind,
         "label": label, "side": "home", "detail": detail}
        for seq, minute, kind, label, detail in [
            (1, 10, "shot", "Goal, Home FC", {"outcome": "goal", "score_after": "1-0"}),
            (2, 12, "shot", "Goal, Home FC", {"outcome": "goal", "score_after": "2-0"}),
            (3, 25, "yellow-card", "Yellow card, Home FC", {"card": "yellow"}),
        ]
    ]
    return state


class SummaryFactsTests(unittest.TestCase):
    def test_historical_summary_never_uses_current_score_or_stats(self):
        _, facts, _ = summary_facts(fixture(), 11, "since-kickoff", 0)
        self.assertIn("1–0", facts["score"])
        self.assertNotIn("possession", facts)
        self.assertNotIn("event:2", facts)

    def test_window_filters_events_and_aggregates(self):
        _, facts, _ = summary_facts(fixture(), 30, "last-10", 0)
        self.assertIn("event:3", facts)
        self.assertNotIn("event:1", facts)
        self.assertNotIn("possession", facts)

    def test_join_window_can_be_empty(self):
        _, facts, _ = summary_facts(fixture(), 30, "since-joined", 30)
        self.assertIn("quiet", facts)

    def test_two_goals_same_team_are_not_called_an_equalizer(self):
        _, facts, _ = summary_facts(fixture(), 30, "since-kickoff", 0)
        self.assertIn("2–0", facts["score"])
        self.assertNotIn("levelled", " ".join(facts.values()))

    def test_truncated_history_does_not_invent_a_zero_score(self):
        state = fixture()
        state["timeline"] = [dict(state["timeline"][-1], seq=i) for i in range(300)]
        _, facts, _ = summary_facts(state, 5, "since-kickoff", 0)
        self.assertNotIn("0–0", facts["score"])
        self.assertIn("does not establish", facts["score"])


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir="/tmp/opencode")
        self.env = patch.dict(os.environ, {"MATCH_DATA_DIR": self.directory.name})
        self.env.start()
        event = {
            "match_id": "saved", "seq": 1, "type": "match_status",
            "match_clock": {"minute": 0, "display": "0'"},
            "payload": {"status": "kickoff", "home": {"name": "Home"}, "away": {"name": "Away"}},
        }
        Path(self.directory.name, "saved.jsonl").write_text(json.dumps(event) + "\n")

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()
        catalog._project_file.cache_clear()

    @patch("streaming.catalog.mstate.list_matches", return_value=[])
    def test_saved_match_visible_without_replay(self, _):
        matches = catalog.list_matches()
        self.assertEqual([m["match_id"] for m in matches], ["saved"])
        self.assertEqual(matches[0]["source"], "saved")

    @patch("streaming.catalog.mstate.load_state", side_effect=ConnectionError)
    def test_saved_match_available_when_redis_is_down(self, _):
        self.assertEqual(catalog.get_state("saved")["home"]["name"], "Home")

    def test_redis_wins_without_duplicates(self):
        live = {"match_id": "saved", "status": "half_time", "updated_at": "2026"}
        with patch("streaming.catalog.mstate.list_matches", return_value=[live]):
            matches = catalog.list_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "half_time")
        self.assertEqual(matches[0]["source"], "live")

    def test_bad_file_does_not_hide_good_matches(self):
        Path(self.directory.name, "broken.jsonl").write_text("{not json}")
        self.assertIn("saved", catalog.saved_states())

    def test_projection_does_not_change_ingestion_state(self):
        projected = catalog.saved_states()["saved"]
        projected["home"]["name"] = "Changed"
        self.assertEqual(catalog.saved_states()["saved"]["home"]["name"], "Home")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()
        self.state = fixture()
        self.patches = [patch(f"api.{module}.get_state", return_value=deepcopy(self.state))
                        for module in ("match_summary_routes", "match_stats_routes", "rag_routes")]
        for mock in self.patches:
            mock.start()

    def tearDown(self):
        for mock in self.patches:
            mock.stop()

    @patch("api.match_summary_routes.complete_json", return_value={"fact_ids": ["score", "event:1"]})
    def test_ai_summary_is_rendered_from_verified_ids(self, _):
        response = self.client.post("/api/v1/matches/test-match/summary", json={})
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["source"], "ai")
        self.assertEqual(body["claims"], {"verified": 2, "total": 2})
        self.assertEqual(body["paragraphs"][1], "10' — Goal, Home FC.")

    @patch("api.match_summary_routes.complete_json", return_value={"fact_ids": ["score", "invented"]})
    def test_unsupported_ai_claim_falls_back_to_evidence(self, _):
        body = self.client.post("/api/v1/matches/test-match/summary", json={}).get_json()
        self.assertEqual(body["source"], "event-stream")
        self.assertNotIn("invented", str(body["paragraphs"]))
        self.assertIsNotNone(body["notice"])

    def test_invalid_summary_requests(self):
        for data in ([], {"minute": -1}, {"minute": True}, {"minute": 31}, {"window": "bad"}):
            response = self.client.post("/api/v1/matches/test-match/summary", json=data)
            self.assertEqual(response.status_code, 400, data)

    @patch("api.match_stats_routes.complete_json", return_value={"what_it_is": "Ball possession."})
    def test_stat_numbers_are_not_generated(self, _):
        body = self.client.post("/api/v1/matches/test-match/stats/possession/explanation",
                                json={"audience": "analyst"}).get_json()
        self.assertEqual(body["source"], "ai")
        self.assertIn("Home FC: 40%", body["in_this_match"])
        self.assertIn("Away FC: 60%", body["in_this_match"])

    @patch("api.match_stats_routes.complete_json", side_effect=RuntimeError("offline"))
    def test_stat_fallback_is_explicit(self, _):
        body = self.client.post("/api/v1/matches/test-match/stats/xg/explanation", json={}).get_json()
        self.assertEqual(body["source"], "glossary")
        self.assertIsNotNone(body["notice"])

    def test_rag_input_validation(self):
        for data in ([], {"query": 5}, {"query": "offside", "limit": 50}):
            self.assertEqual(self.client.post("/api/v1/rag/search", json=data).status_code, 400)

    @patch("rag.indexing.Indexer.search", return_value=[])
    @patch("api.rag_routes.complete_json")
    def test_no_passages_never_calls_model(self, model, _):
        body = self.client.post("/api/v1/rag/matches/test-match/events/3/explanation", json={}).get_json()
        self.assertFalse(body["answer"]["answerable"])
        model.assert_not_called()

    @patch("rag.indexing.Indexer.search", return_value=[
        {"id": "p1", "source": "IFAB.pdf", "similarity": .8, "content": "A caution is a yellow card."},
    ])
    @patch("api.rag_routes.complete_json", return_value={
        "answerable": True, "explanation": "A caution is shown with a yellow card.",
        "law_reference": "Law 12", "citations": ["p1"], "data_limits": "The reason is not recorded.",
    })
    def test_rag_receives_server_event_and_returns_cited_passage(self, model, _):
        response = self.client.post("/api/v1/rag/matches/test-match/events/3/explanation", json={})
        self.assertEqual(response.status_code, 200)
        evidence = json.loads(model.call_args.args[1])
        self.assertEqual(evidence["event"]["seq"], 3)
        self.assertEqual(response.get_json()["chunks"][0]["id"], "p1")

    @patch("rag.indexing.Indexer.search", return_value=[
        {"id": "p1", "source": "IFAB.pdf", "similarity": .8, "content": "A caution is a yellow card."},
    ])
    @patch("api.rag_routes.complete_json", return_value={
        "answerable": True, "explanation": "Unsupported", "citations": ["fake"],
    })
    def test_invented_rag_citation_is_not_shown(self, model, _):
        response = self.client.post("/api/v1/rag/matches/test-match/events/3/explanation", json={})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Unsupported", response.get_data(as_text=True))

    def test_missing_event(self):
        self.assertEqual(self.client.post("/api/v1/rag/matches/test-match/events/999/explanation",
                                          json={}).status_code, 404)

    @patch("api.routes.catalog.get_state")
    def test_sse_starts_with_a_snapshot_for_saved_matches(self, get_state):
        get_state.return_value = self.state
        response = self.client.get("/api/v1/matches/test-match/stream", buffered=False)
        try:
            frame = next(response.response).decode()
            self.assertTrue(frame.startswith("event: state\ndata: "))
            self.assertIn('"match_id": "test-match"', frame)
            self.assertEqual(response.mimetype, "text/event-stream")
        finally:
            response.close()


class ProjectionTests(unittest.TestCase):
    def test_duplicate_events_do_not_double_count(self):
        state = new_state("test-match")
        event = {"match_id": "test-match", "seq": 1, "type": "shot",
                 "match_clock": {"minute": 10},
                 "payload": {"side": "home", "outcome": "goal", "xg": .5}}
        self.assertTrue(apply_event(state, event))
        self.assertFalse(apply_event(state, event))
        self.assertEqual(state["score"]["home"], 1)


if __name__ == "__main__":
    unittest.main()
