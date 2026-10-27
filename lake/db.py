import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

MIGRATIONS = ["""
CREATE TABLE chats (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, source_id TEXT, title TEXT NOT NULL,
 model_used TEXT, created_at TEXT, updated_at TEXT, imported_at TEXT NOT NULL,
 pinned INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
 project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL, content_hash TEXT NOT NULL
);
CREATE TABLE messages (
 id INTEGER PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
 idx INTEGER NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
 content TEXT NOT NULL, created_at TEXT, UNIQUE(chat_id, idx)
);
CREATE TABLE cards (
 chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE, problem TEXT NOT NULL DEFAULT '',
 environment TEXT NOT NULL DEFAULT '', solution_steps TEXT NOT NULL DEFAULT '[]', result TEXT NOT NULL DEFAULT '',
 caveats TEXT NOT NULL DEFAULT '[]', suggested_tags TEXT NOT NULL DEFAULT '[]',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ready','failed')),
 error TEXT, generated_by TEXT, generated_at TEXT, edited_by_user INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE chat_tags (chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
 tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY(chat_id,tag_id));
CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '');
CREATE TABLE embeddings (chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
 model TEXT NOT NULL, vector BLOB NOT NULL, created_at TEXT NOT NULL);
CREATE VIRTUAL TABLE message_fts USING fts5(chat_id UNINDEXED, message_id UNINDEXED, title, content,
 tokenize='unicode61');
CREATE VIRTUAL TABLE card_fts USING fts5(chat_id UNINDEXED, title, problem, environment,
 solution_steps, result, caveats, tokenize='unicode61');
CREATE INDEX messages_chat_order ON messages(chat_id,idx);
CREATE INDEX chats_updated ON chats(updated_at);
CREATE INDEX chats_source ON chats(source);
""", """
DROP TABLE embeddings;
CREATE TABLE embeddings (
 id INTEGER PRIMARY KEY,
 chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
 message_start_idx INTEGER NOT NULL DEFAULT -1,
 message_end_idx INTEGER NOT NULL DEFAULT -1,
 kind TEXT NOT NULL CHECK(kind IN ('chunk','card')),
 model_name TEXT NOT NULL,
 dim INTEGER NOT NULL,
 vector BLOB NOT NULL,
 content_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 stale INTEGER NOT NULL DEFAULT 0 CHECK(stale IN (0,1)),
 UNIQUE(chat_id,message_start_idx,message_end_idx,kind,model_name,content_hash)
);
CREATE INDEX embeddings_active_model ON embeddings(model_name,stale,kind,chat_id);
CREATE INDEX embeddings_chat_model ON embeddings(chat_id,model_name,kind);
CREATE TABLE embedding_jobs (
 chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
 model_name TEXT NOT NULL,
 content_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','running','ready','failed')),
 error TEXT,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(chat_id,model_name)
);
CREATE INDEX embedding_jobs_progress ON embedding_jobs(model_name,status);
"""]


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    migrate(db)
    return db


def migrate(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    for i in range(version, len(MIGRATIONS)):
        db.executescript(MIGRATIONS[i])
        db.execute(f"PRAGMA user_version={i+1}")
    db.commit()
