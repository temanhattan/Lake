# Semantic vector benchmark

Measured with `python benchmark_semantic.py` on the development runtime (Python 3.12.14, NumPy 2.3.5, 12 logical CPUs).

| Dataset | Backend | Index warm-up | Unfiltered p50 / p95 | Default archive-filter p50 / p95 |
|---|---|---:|---:|---:|
| 100,000 vectors × 768 dimensions | NumPy memory-mapped cosine | 2.78 s | 74.3 / 78.0 ms | 194.5 / 199.1 ms |

The vectors are deterministic synthetic float32 values. The timed query includes vector cache validation, cosine scoring, top-k selection, and (for the second column) the default `archived = false` chat filter. It excludes query-vector generation by Ollama. Both measured p95 values were below the 300 ms target on this run.
