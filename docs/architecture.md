# Architecture

The Python library layer handles imports, deduplication, indexing, search, and context generation. SQLite stores chats, messages, cards, tags, FTS5 indexes, embeddings, and background jobs. The loopback HTTP server serves a static JavaScript/CSS interface and read-only MCP requests use a separate stdio process.

See the reproducible [architecture, search, and continue-block diagrams](diagrams/README.md). Vector retrieval uses `sqlite-vec` when available and a NumPy memory-mapped fallback otherwise. Hybrid search combines keyword and vector result ranks with reciprocal rank fusion.
