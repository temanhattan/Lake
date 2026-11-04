<picture>
  <source media="(prefers-color-scheme: dark)" srcset="lake/static/brand/readme-header-dark.svg">
  <img src="lake/static/brand/readme-header.svg" alt="Lake handwritten wordmark">
</picture>

# Lake

Private, local-first gallery for your AI chats: searchable, visual, and ready
to **continue from here**.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-146b60?labelColor=26332f)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-146b60)](https://www.python.org/)
[![CI](https://github.com/temanhattan/Lake/actions/workflows/ci.yml/badge.svg)](https://github.com/temanhattan/Lake/actions/workflows/ci.yml)

> Lake turns scattered AI conversations into a private, searchable library
> that helps you pick up where you left off.

<p align="center">
  <img src="docs/assets/readme/lake-walkthrough.gif" alt="Demo-only walkthrough of Lake's welcome wall, search, chat detail, and continue block" width="720">
</p>

*The media below uses fictional conversations and contains no personal library data.*

## Why Lake

- **Keep it local.** Chats, indexes, cards, and jobs stay on your machine.
- **Find the thread.** Combine exact keyword search with local semantic search.
- **Continue with context.** Turn a long conversation into a compact handoff.
- **Bring your tools.** Read your library from coding agents through read-only MCP.

## At a glance

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/welcome-dark.png">
  <img src="docs/assets/readme/welcome-light.png" alt="Lake welcome wall filled with fictional demo chats" width="24%">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/search-dark.png">
  <img src="docs/assets/readme/search-light.png" alt="Lake hybrid search results for a fictional query" width="24%">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/chat-dark.png">
  <img src="docs/assets/readme/chat-light.png" alt="Lake chat detail with a fictional continue-from-here card" width="24%">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/palette-dark.png">
  <img src="docs/assets/readme/palette-light.png" alt="Lake command palette in a fictional demo library" width="24%">
</picture>

<p align="center"><sub>Welcome wall · hybrid search · chat detail · command palette</sub></p>

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/diagrams/architecture-dark.svg">
  <img src="docs/diagrams/architecture-light.svg" alt="Hand-drawn Lake data flow from exports and pasted chats through local SQLite and merged search to the UI and read-only MCP">
</picture>

Lake imports transcripts into SQLite, builds searchable indexes locally, and
serves the interface over loopback HTTP. Search fuses SQLite FTS5 keyword
matches with local vector results. Cards and context blocks are generated
only when you ask, through your configured local Ollama endpoint.

<table>
<tr>
<td width="50%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/diagrams/search-dark.svg">
  <img src="docs/diagrams/search-light.svg" alt="Lake search pipeline from a query through FTS5, vector search, rank fusion, and chat results">
</picture>
</td>
<td width="50%">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/diagrams/continue-dark.svg">
  <img src="docs/diagrams/continue-light.svg" alt="Lake continue flow from a full conversation to a reusable card and compact context block">
</picture>
</td>
</tr>
</table>

The diagrams and PNG fallbacks are reproducibly built from
[docs/diagrams/src/](docs/diagrams/src/).

## Privacy and boundaries

- Lake binds the web server to `127.0.0.1` and rejects unexpected Host and
  cross-origin state-changing requests.
- Chats, cards, indexes, settings, and jobs stay on your machine.
- Lake has no telemetry or hosted API. Ollama is contacted only for the local
  features you request.
- MCP uses local stdio, opens SQLite read-only, caps its output, and redacts
  detected secrets by default.

See [docs/privacy.md](docs/privacy.md) for boundaries and redaction details.

## Quick start

Install the latest tagged release with [pipx](https://pipx.pypa.io/):

```powershell
pipx install "git+https://github.com/temanhattan/Lake.git@v0.1.0"
lake import .\path\to\export
lake serve
```

Open <http://127.0.0.1:8765>. You can also import an export from **Import** in
the browser. For Ollama setup and configuration options, see
[docs/ollama.md](docs/ollama.md).

For a source checkout:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Lake stores data under a per-user OS data directory by default. Set
`LAKE_DATA_DIR` or `data_dir` in `config.toml` to choose another location.

## Models

| Model | Role | License |
|---|---|---|
| `qwen2.5:3b` | Local cards and context | Qwen license |
| `nomic-embed-text` | Local embeddings | Apache-2.0 |
| `bge-m3` | Optional multilingual embeddings | MIT |

Model weights are not distributed by Lake; download them through Ollama.

## Roadmap

- [x] Local import, dedupe, cards, and hybrid search
- [x] Welcome wall and continue-from-here blocks
- [x] Read-only MCP over stdio
- [ ] More export parsers
- [ ] Better local model setup guidance

## Build the visuals

```powershell
python docs/diagrams/build.py
```

The diagrams use hand-drawn SVG templates, embed the locally vendored OFL font,
and render 2× PNG fallbacks in Chrome. README screenshots and the demo-only
walkthrough are captured with the fictional browser harness described in
[docs/testing.md](docs/testing.md).

## Docs

[Architecture](docs/architecture.md) · [Imports](docs/imports.md) · [Ollama](docs/ollama.md) · [MCP](docs/mcp.md) · [Privacy](docs/privacy.md) · [Testing](docs/testing.md)

## License

Lake's source code and associated documentation are available under the [Apache License 2.0](LICENSE).

**Brand note:** the Lake name, wordmark, and visual identity are reserved; see [LICENSE-BRAND.md](LICENSE-BRAND.md).
