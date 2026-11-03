# Local models with Ollama

Ollama is optional. Lake uses it for requested card/context generation and local embeddings. Install Ollama separately, pull the models below, then set `model` and `embedding_model` in the ignored local `config.toml`.

| Model | Role | License |
| --- | --- | --- |
| `qwen2.5:3b` | Chat and summaries | Apache-2.0 |
| `nomic-embed-text` | Embeddings | Apache-2.0 |

The model names are Lake's configured defaults; weights are not distributed here. Check the [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) and [Nomic model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) for current model terms. Requests use `ollama_url`, which must resolve to loopback. See [config.example.toml](../config.example.toml) for all settings.

`python -m lake doctor` reports Python, SQLite/FTS, vector backend, Ollama connectivity, and configured model availability.
