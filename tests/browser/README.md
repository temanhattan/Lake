# Welcome browser verification

This harness uses Playwright only for development verification. It starts Lake's HTTP handler against a temporary SQLite database populated with 24 realistic fictional chats adapted from the demo sample style. It also creates a separate 5,000-chat fictional database for endpoint timing. It never opens or reads `data/lake.db` or any configured user library.

## Run

From the repository root in PowerShell:

```powershell
python -m pip install -r tests/browser/requirements.txt
python -m playwright install chromium ffmpeg
python tests/browser/run_welcome.py
```

If Chromium downloads are unavailable, the runner also tries installed Chrome and Edge. In PowerShell, set `$env:LAKE_BROWSER_CHANNEL='chrome'` or `msedge` to select one explicitly. FFmpeg is needed for Playwright video recording; if its download is blocked too, screenshots and assertions can run but the recording check cannot pass. Install Playwright only in the development environment; do not add it to application runtime dependencies.

Evidence is written to `design-research/welcome-evidence/` (ignored by Git): eight real/demo, light/dark, desktop/mobile screenshots; mobile indicator and bottom-scroll views; keyboard focus; the Playwright load → rotation → hover → Start video; a JSON request/performance report; and, when the `welcome-before-*` captures are present, four side-by-side comparison sheets. The runner updates the request totals and unique URL list in `WELCOME-VERIFICATION.md` from its JSON result. The script exits nonzero if a browser assertion fails.

To recreate the comparison sheets, retain the ignored `welcome-before-*.png` images from the visual-polish baseline. If they are absent, browser verification still runs and records the comparison-sheet status as Not run.
