# Lake

Lake is a private, local-first gallery for AI conversations. It uses SQLite, Python, and a local NumPy memory-mapped vector index (or optional sqlite-vec). The server binds to `127.0.0.1` only. Ollama is contacted only for requested local generation and semantic queries/embedding jobs.

## Run

1. Install Python 3.11 or newer.
2. Install the local vector fallback: `python -m pip install -r requirements.txt`. Optionally install the SQLite extension backend with `python -m pip install sqlite-vec`; Lake falls back to NumPy when the extension is unavailable.
3. Copy `config.example.toml` to `config.toml` and adjust paths or Ollama settings if needed.
4. Run `python -m lake` from this folder.
5. Open <http://127.0.0.1:8765>.

The SQLite database is created at `./data/lake.db`. SQLite FTS5 is required and is included in most standard Python SQLite builds. Semantic vectors are stored in SQLite; NumPy provides the default memory-mapped cosine search backend. The app itself makes no remote calls. Ollama requests are restricted to a local URL. To import every supported file in the configured import folder from a command line, run `python -m lake import-folder` (or pass a folder path).

## Import

Use **Import** in the app to upload `conversations.json`, `.md`, `.txt`, or `.json` files. ChatGPT exports may be selected as a folder or as `conversations.json`; Claude exports may be selected as JSON. You can also paste a transcript. Recognized `User:` / `Assistant:` markers split into messages; unmarked text is preserved as one message. Files are parsed in source-specific modules in `lake/parsers/`.

The importer reports added, updated, skipped, and failed items. Re-importing identical content is idempotent. The original message text is retained as imported.

## Ollama

Install and start Ollama separately for cards, context, and semantic search. Pull `qwen2.5:7b` and `nomic-embed-text` locally. Set `ollama_url`, `model`, and `embedding_model` in `config.toml`. For multilingual chat collections, set `embedding_model = "bge-m3"` and pull that model. New imports and ready cards are embedded in a durable background queue; progress and failed-job retries appear above the library. Switching models marks the previous vectors stale and schedules the current model. Searches never combine models. Card and embedding prompts treat transcript text as untrusted data.

## Semantic search

The search selector supports **Keyword**, **Semantic**, and **Hybrid** (default). Hybrid runs FTS5 and local vector retrieval together, then merges chat ranks with reciprocal rank fusion. Source, model, project, tag, date, pin, and archive filters apply in every mode. An optional **Local rerank** asks the configured Ollama chat model to rerank the top 20; its latency is shown with the result count.

Each chat is split into approximate 400-token user/reply chunks with overlap for long messages, plus a separate vector for a ready card. Small fenced code blocks stay together. `sqlite-vec` is used when installed and loadable; otherwise normalized float32 vectors are searched with NumPy over a memory-mapped matrix. The default cache is `./data/vector-cache`. **Find similar chats** uses a card vector. **Find duplicate problems** compares card vectors above `duplicate_similarity_threshold`; for predictable local memory use it scans at most `duplicate_scan_limit` cards per request and indicates when that cap applies.

Run `python evaluate_semantic.py` with Ollama running and the configured embedding model available to compute recall@5 for the bundled 20-query sample set. Run `python benchmark_semantic.py` to reproduce warmed vector-query latency over 100,000 768-dimensional vectors. The recorded measurements are in [reports/semantic_benchmark.md](reports/semantic_benchmark.md); they exclude Ollama query embedding time.

## Data and privacy

Lake stores chats, FTS indexes, embeddings, and durable embedding jobs in SQLite, uses no telemetry, and makes no remote calls. Ollama URLs are restricted to loopback. The optional secret warning scans for common key patterns and high-entropy strings; it only adds a warning badge and never edits content. Imported markdown is escaped before display. Search filters include source, model, project, tag, date range, pinned, and archived. `Ctrl/Cmd+K` focuses search.

Use `python -m lake backup` for a database copy plus Markdown and JSON exports under `backups/`. Context blocks can be copied from a card or generated from the full transcript; the configured target is approximate because token estimation is local and heuristic.

## Future extension points

Core operations live in the `lake/` library layer, separate from the HTTP/UI layer. There is no MCP server or agent write interface.

## Development

Run the test suite with `python -m unittest discover -s tests -v`. Tests cover parsers, import deduplication, chunking, resumable embedding jobs, model staleness, FTS and vector search, RRF, similar chats, duplicates, card validation, and context size. `python -m lake --seed` loads the five fake sample chats. Demo exports are in `demo/`.
