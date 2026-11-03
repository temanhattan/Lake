# Welcome browser verification

This harness uses Playwright only for development verification. It starts Lake's HTTP handler against a temporary SQLite database populated only with fabricated chats. It never opens or reads `data/lake.db` or any configured user library.

## Run

From the repository root in PowerShell:

```powershell
python -m pip install -r tests/browser/requirements.txt
python -m playwright install chromium ffmpeg
python tests/browser/run_welcome.py
```

If Chromium downloads are unavailable, the runner also tries installed Chrome and Edge. In PowerShell, set `$env:LAKE_BROWSER_CHANNEL='chrome'` or `msedge` to select one explicitly. FFmpeg is needed for Playwright video recording; if its download is blocked too, screenshots and assertions can run but the recording check cannot pass. Install Playwright only in the development environment; do not add it to application runtime dependencies.

Evidence is written to `design-research/welcome-evidence/` (ignored by Git): screenshots, Playwright's load → rotation → hover → Start video, a JSON request/performance report, and the test output. The script exits nonzero if any assertion fails.
