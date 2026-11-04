import io
import json
import unittest
from unittest.mock import patch
from email.message import Message

from lake.config import Config
from lake.db import connect
from lake.web import Handler
from lake.welcome import SAMPLE_TILES, clear_secret_scan_cache, _SECRET_SCAN_CACHE


class WelcomeEndpointTests(unittest.TestCase):
    def setUp(self):
        clear_secret_scan_cache()
        self.handler = object.__new__(Handler)
        self.handler.db = connect(":memory:")
        self.handler.config = Config()
        self.handler.semantic = None
        self.handler.embeddings = None
        self.handler.jobs = None
        self.handler.headers = Message()
        self.handler.headers["Host"] = "127.0.0.1:8765"
        self.handler.wfile = io.BytesIO()
        self.handler.send_response = lambda *args: None
        self.handler.send_header = lambda *args: None
        self.handler.end_headers = lambda: None

    def tearDown(self):
        self.handler.db.close()

    def add_chat(self, chat_id, title, *, archived=0, pinned=0, content="ordinary transcript", project=None, tag=None):
        db = self.handler.db
        if project:
            db.execute("INSERT OR IGNORE INTO projects(name) VALUES(?)", (project,))
            project_id = db.execute("SELECT id FROM projects WHERE name=?", (project,)).fetchone()[0]
        else:
            project_id = None
        db.execute("""INSERT INTO chats(id,source,title,created_at,updated_at,imported_at,
            archived,pinned,project_id,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (chat_id, "manual", title, "2026-10-20", "2026-10-20", "2026-10-20", archived, pinned, project_id, chat_id))
        db.execute("INSERT INTO messages(chat_id,idx,role,content) VALUES(?,0,'user',?)", (chat_id, content))
        db.execute("INSERT INTO cards(chat_id,problem,result,status) VALUES(?,?,?,'ready')",
                   (chat_id, f"Summary for {title}", f"Result for {title}"))
        if tag:
            db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_id = db.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()[0]
            db.execute("INSERT INTO chat_tags(chat_id,tag_id) VALUES(?,?)", (chat_id, tag_id))
        db.commit()

    def get_tiles(self, query=""):
        self.handler.wfile = io.BytesIO()
        self.handler.path = "/api/welcome/tiles" + query
        self.handler.do_GET()
        return json.loads(self.handler.wfile.getvalue())

    def test_demo_response_contains_only_fictional_metadata(self):
        self.add_chat("real-secret-id", "PRIVATE REAL TITLE", content="api_key=abcdef0123456789abcdef012345")
        response = self.get_tiles("?demo=1")
        self.assertEqual(response, SAMPLE_TILES)
        self.assertNotIn(b"PRIVATE REAL TITLE", self.handler.wfile.getvalue())
        self.assertNotIn(b"abcdef0123456789abcdef012345", self.handler.wfile.getvalue())
        self.assertTrue(all(set(tile) == {"id", "title", "summary", "model", "date", "tags", "project"} for tile in response))

    def test_archived_and_secret_flagged_chats_never_appear_in_real_mode(self):
        for i in range(7):
            self.add_chat(f"good-{i}", f"Good chat {i}", project=f"Project {i % 3}", tag=f"Tag {i % 4}")
        self.add_chat("archived", "Archived chat", archived=1)
        self.add_chat("secret", "Secret chat", content="token=abcdef0123456789abcdef012345")
        response = self.get_tiles()
        ids = {tile["id"] for tile in response}
        self.assertEqual(ids, {f"good-{i}" for i in range(7)})
        self.assertNotIn("archived", ids)
        self.assertNotIn("secret", ids)

    def test_unscanned_chat_with_fake_key_is_scanned_before_wall_eligibility(self):
        for i in range(6):
            self.add_chat(f"safe-{i}", f"Safe fictional chat {i}")
        self.add_chat("never-scanned", "Unscanned fake key chat",
                      content="api_key=FAKEKEY0123456789ABCDEFGHIJK")
        from lake.library import secret_warning
        with patch("lake.welcome.secret_warning", wraps=secret_warning) as scanned:
            response = self.get_tiles()
        self.assertTrue(any("FAKEKEY0123456789ABCDEFGHIJK" in call.args[0] for call in scanned.call_args_list))
        ids = {tile["id"] for tile in response}
        self.assertNotIn("never-scanned", ids)
        self.assertEqual(ids, {f"safe-{i}" for i in range(6)})

    def test_response_is_capped_and_pins_precede_recent_and_diversified_items(self):
        for i in range(30):
            self.add_chat(f"chat-{i:02}", f"Chat {i:02}", pinned=int(i in (2, 5)), project=f"Project {i % 5}", tag=f"Tag {i % 7}")
        response = self.get_tiles()
        self.assertEqual(len(response), 24)
        self.assertEqual(response[0]["id"], "chat-02")
        self.assertEqual(response[1]["id"], "chat-05")
        self.assertTrue(all(set(tile) == {"id", "title", "summary", "model", "date", "tags", "project"} for tile in response))
        self.assertGreater(len({tile["project"] for tile in response}), 1)

    def test_secret_scans_stop_after_24_eligible_chats_and_cache_by_content_hash(self):
        for i in range(30):
            self.add_chat(f"scan-{i:02}", f"Scan candidate {i:02}", project=f"Project {i % 6}", tag=f"tag-{i % 8}")
        from lake.library import secret_warning
        with patch("lake.welcome.secret_warning", wraps=secret_warning) as scanned:
            first = self.get_tiles()
            self.assertEqual(len(first), 24)
            self.assertEqual(scanned.call_count, 24)
            self.get_tiles()
            self.assertEqual(scanned.call_count, 24, "warm response should reuse digest-keyed scan results")

    def test_import_change_invalidates_previous_secret_scan_hash(self):
        from lake.library import content_hash, import_chats, secret_warning
        for i in range(6):
            self.add_chat(f"invalidate-{i}", f"Keep this note {i}")
        db = self.handler.db
        db.execute("UPDATE chats SET source='fixture',source_id='stable-id' WHERE id='invalidate-0'")
        db.commit()
        old_hash = db.execute("SELECT content_hash FROM chats WHERE id='invalidate-0'").fetchone()[0]
        self.get_tiles()
        self.assertIn(old_hash, _SECRET_SCAN_CACHE)
        updated = {"source": "fixture", "source_id": "stable-id", "title": "Updated note",
                   "model_used": "GPT-4.1", "created_at": "2026-10-20", "updated_at": "2026-10-21",
                   "messages": [{"role": "user", "content": "The note has a new safe transcript."}]}
        import_chats(db, [updated])
        new_hash = content_hash(updated)
        self.assertNotEqual(old_hash, new_hash)
        self.assertNotIn(old_hash, _SECRET_SCAN_CACHE)
        self.get_tiles()
        self.assertIn(new_hash, _SECRET_SCAN_CACHE)


if __name__ == "__main__":
    unittest.main()
