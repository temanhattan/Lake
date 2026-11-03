# Read-only MCP server

Lake's MCP transport uses stdio with the official Python MCP SDK. Its database connection is SQLite `mode=ro`; the MCP process cannot run migrations or write to Lake's database.

Register a local server with Claude Code from the repository directory:

```powershell
claude mcp add --transport stdio lake -- python -m lake.mcp_server --config "C:\path\to\config.toml"
```

Tools include chat search, card and excerpt retrieval, context blocks, projects, and tags. Results are bounded, carry an untrusted historical-data notice, and redact detected secrets by default. Project allowlists and rate limits are configured in `config.toml`; local calls are appended to the configured JSONL audit file.
