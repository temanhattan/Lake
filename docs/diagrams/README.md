# Diagrams

Sources are hand-authored SVG templates in `src/`; `build.py` embeds Lake's locally vendored DM Sans (SIL Open Font License) into each SVG and uses Chrome to render 2× PNG fallbacks. This was chosen over Mermaid and Excalidraw so the project can keep a tiny, reviewable source format, preserve the Lake linework, and render identically in GitHub `<img>` tags. No web font, image library, runtime dependency, or app dependency is added. Python Playwright is used only in the build environment; its setup is in [tests/browser/README.md](../../tests/browser/README.md).

Build every light/dark variant with one command from the repository root:

```powershell
python docs/diagrams/build.py
```

The build opens each SVG as an `<img>` in Chrome before capturing PNG, which checks the same image embedding path used by GitHub README rendering. SVG text uses the embedded OFL font instead of an external font request. Architecture flow, search pipeline, and continue-from-here each have both theme variants. PNG exports are 2× and optimized by the browser encoder. No evaluation chart is included yet: the bundled recall script requires a local Ollama model, and the repository does not contain a completed measured recall run. The benchmark source is synthetic and remains documented in [../benchmarks/semantic_benchmark.md](../benchmarks/semantic_benchmark.md).
