# Testing

Run the application tests with:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The real-browser suite is development-only. Install its requirements and follow [tests/browser/README.md](../tests/browser/README.md). It uses a temporary SQLite database with fictional chats only and stores screenshots, recordings, and JSON results in the ignored `design-research/` folder.

To capture README media, run `python tests/browser/capture_readme_media.py`. Review every generated image for fictional titles, names, paths, and keys before committing it. The capture script enables demo mode and never opens `data/lake.db`.

For semantic quality, `python scripts/evaluate_semantic.py` requires a running local Ollama instance and the configured embedding model. `python scripts/benchmark_semantic.py` reproduces the synthetic 100,000-vector benchmark. Browser and performance claims should be reported with their evidence and environment; headless timings are not laptop measurements.
