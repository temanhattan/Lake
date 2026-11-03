"""Start a fixture-only Lake server for promo capture.

This deliberately uses a temporary database and never opens the configured
user database. The Node capture runner owns the browser and screenshots.
"""
from __future__ import annotations

import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lake.config import Config
from lake.db import connect
from lake.library import reindex_chat
from lake.web import Handler

FIXTURES = [
    ("A queue that drains without surprises", "The retry worker now releases successful jobs and leaves only failed work for the next pass.", "Northstar", ["python", "jobs"], "GPT-4o"),
    ("Search remembers the phrase, not just the word", "A small synonym expansion brings back the decision even when the original wording has faded.", "Lake", ["search", "retrieval"], "GPT-4.1"),
    ("An import preview with room to breathe", "The preview separates skipped rows from warnings so a large export is easier to review.", "Field Notes", ["imports", "ux"], "Claude Sonnet"),
    ("The quiet fix for a noisy refresh", "A stale request was winning a race after navigation; cancelling it keeps the new view in control.", "Northstar", ["debugging", "web"], "GPT-4.1"),
    ("A label that survives the narrow screen", "The mobile filter keeps its full name while the rest of the controls wrap into a clean second row.", "Field Notes", ["mobile", "accessibility"], "GPT-4o"),
    ("Cards that tell you what changed", "A concise result summary gives the library a useful preview without opening the full conversation.", "Lake", ["product", "design"], "Claude Sonnet"),
]


def main() -> None:
    db_path = ROOT / "promo" / "tmp" / "fictional-promo.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    db = connect(str(db_path))
    for index, (title, summary, project, tags, model) in enumerate(FIXTURES):
        chat_id = f"promo-fictional-{index:02d}"
        db.execute(
            """INSERT INTO chats(id,source,title,model_used,created_at,updated_at,imported_at,
               pinned,archived,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (chat_id, "manual", title, model, "2026-10-24", "2026-10-24", "2026-11-03", int(index == 0), 0, f"promo-hash-{index}"),
        )
        db.execute(
            "INSERT INTO messages(chat_id,idx,role,content) VALUES(?,0,'user',?)",
            (chat_id, f"Fictional promo transcript {index}; local demo fixture only."),
        )
        db.execute(
            "INSERT INTO cards(chat_id,problem,result,status) VALUES(?,?,?,'ready')",
            (chat_id, summary, summary),
        )
        db.execute("INSERT OR IGNORE INTO projects(name) VALUES(?)", (project,))
        project_id = db.execute("SELECT id FROM projects WHERE name=?", (project,)).fetchone()[0]
        db.execute("UPDATE chats SET project_id=? WHERE id=?", (project_id, chat_id))
        for tag in tags:
            db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_id = db.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()[0]
            db.execute("INSERT INTO chat_tags(chat_id,tag_id) VALUES(?,?)", (chat_id, tag_id))
        reindex_chat(db, chat_id)
    db.commit()
    Handler.db = db
    Handler.config = Config(db_path=str(db_path), port=0)
    Handler.semantic = Handler.embeddings = Handler.jobs = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        thread.join()
    finally:
        server.shutdown()
        server.server_close()
        db.close()


if __name__ == "__main__":
    main()
