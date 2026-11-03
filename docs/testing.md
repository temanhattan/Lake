# Testing

Run the application tests with:

```powershell
python -m unittest discover -s tests -v
```

The real-browser welcome suite is development-only. Install its requirements and follow [tests/browser/README.md](../tests/browser/README.md). It uses a temporary SQLite database with fictional chats only and stores screenshots, recordings, and JSON results in the ignored `design-research/` folder.

For semantic quality, `python scripts/evaluate_semantic.py` requires a running local Ollama instance and the configured embedding model. `python scripts/benchmark_semantic.py` reproduces the synthetic 100,000-vector benchmark. Browser and performance claims should be reported with their evidence and environment; headless timings are not laptop measurements.
