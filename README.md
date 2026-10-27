# Lake

Lake is a private, local-first gallery for AI conversations. It uses Python's standard library and SQLite, so the app has no third-party runtime dependencies and works offline. The server binds to `127.0.0.1` only. Ollama is contacted only when you request card or context generation.

## Run

1. Install Python 3.11 or newer.
2. Install the local vector fallback: `python -m pip install -r requirements.txt`. Optionally install `sqlite-vec` for its SQLite extension backend; Lake falls back to NumPy when the extension is unavailable.
3. Copy `config.example.toml` to `config.toml` and adjust paths or Ollama settings if needed.
4. Run `python -m lake` from this folder.
5. Open <http://127.0.0.1:8765>.

The SQLite database is created at `./data/lake.db`. SQLite FTS5 is required and is included in most standard Python SQLite builds. Semantic vectors are stored in SQLite; NumPy provides the default memory-mapped cosine search backend. The app itself makes no remote calls. Ollama requests are restricted to a local URL. To import every supported file in the configured import folder from a command line, run `python -m lake import-folder` (or pass a folder path).

## Import

Use **Import** in the app to upload `conversations.json`, `.md`, `.txt`, or `.json` files. ChatGPT exports may be selected as a folder or as `conversations.json`; Claude exports may be selected as JSON. You can also paste a transcript. Recognized `User:` / `Assistant:` markers split into messages; unmarked text is preserved as one message. Files are parsed in source-specific modules in `lake/parsers/`.

The importer reports added, updated, skipped, and failed items. Re-importing identical content is idempotent. The original message text is retained as imported.

## Ollama

Install and start Ollama separately if you want generated cards or full-chat context. Set `ollama_url` and `model` in `config.toml`; defaults target `http://127.0.0.1:11434` and `qwen2.5:7b`. Card work runs on a background thread. Failed jobs remain visible with a retry action. The prompt treats transcript text as untrusted data. Manual card edits are protected from regeneration unless the request explicitly confirms overwrite.

## Data and privacy

Lake stores chats and messages in SQLite, uses an FTS5 index, and does not send telemetry. It does not call remote services. The optional secret warning scans for common key patterns and high-entropy strings; it only adds a warning badge and never edits content. Imported markdown is escaped before display. Search filters include source, model, project, tag, date range, pinned, and archived. `Ctrl/Cmd+K` focuses search.

Use `python -m lake backup` for a database copy plus Markdown and JSON exports under `backups/`. Context blocks can be copied from a card or generated from the full transcript; the configured target is approximate because token estimation is local and heuristic.

## Future extension points

Core operations live in `lake/library.py`, separate from the HTTP/UI layer. `embeddings` storage and a search provider seam are present for future local semantic search; embedding generation and semantic ranking are not implemented in this MVP. There is no MCP server or agent write interface.

## Development

Run the test suite with `python -m unittest discover -s tests -v`. Tests cover parsers, import deduplication, FTS search, card validation, context size, and a 5,000-chat / 100,000-message search fixture. `python -m lake --seed` loads the five fake sample chats. Demo exports are in `demo/`.
