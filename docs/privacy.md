# Privacy

- Lake binds its HTTP server to `127.0.0.1` by default. Chats, indexes, and settings are stored on this machine.
- Lake has no telemetry or hosted service calls. Optional Ollama requests go to the configured loopback URL when you ask for local generation or semantic search.
- The MCP server uses stdio and opens SQLite read-only. Secret redaction is enabled by default for MCP results; archived chats are excluded.

The secret-warning scan flags likely credentials for review. It does not edit imported messages. ChatGPT/Claude exports and pasted transcripts are processed locally. See [Ollama setup](ollama.md) and [read-only MCP](mcp.md) for the requests those optional features make.
