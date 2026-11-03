# Welcome page verification

Run date: 2026-11-03. Browser: installed Google Chrome 156.0.8078.74 through Playwright 1.64.1. All browser checks used a temporary Lake database seeded with 24 fabricated chats under `design-research/welcome-evidence/fictional-test-library.sqlite3`; the user's library was not opened or queried. Screenshots, video, request logs, and test output are in the ignored `design-research/welcome-evidence/` directory and are not committed.

## Results

| Check | Status | Evidence |
|---|---|---|
| Full Python unit suite | **Passed** | [unittest-full.txt](design-research/welcome-evidence/unittest-full.txt): 34 tests, `OK`. |
| Migration schema version | **Passed** | [test_semantic.py](tests/test_semantic.py): test now compares against `SCHEMA_VERSION` (4). The migration is correct; the old assertion for 3 was stale because migration 4 adds project MCP exclusion and solution feedback. |
| Pre-migration automatic backup | **Passed** | [test_semantic.py](tests/test_semantic.py): migrates a populated copy, verifies the adjacent `.pre-migration-v1.bak` exists, retains version 1 and both fixture rows, and verifies the live copy reached version 4. Output is in `unittest-full.txt`. |
| Unscanned chat with a fake key | **Passed** | [test_welcome.py](tests/test_welcome.py): `test_unscanned_chat_with_fake_key_is_scanned_before_wall_eligibility` confirms the chat is scanned and excluded. |
| Archived and secret-bearing chats in real mode | **Passed** | [test_welcome.py](tests/test_welcome.py): `test_archived_and_secret_flagged_chats_never_appear_in_real_mode` confirms neither ID appears. |
| Secret-warning behavior | **Passed** | [welcome.py](lake/welcome.py) calls `secret_warning()` on demand while building the welcome response. There is no persisted scan flag. Import preview also calls the detector on demand; it does not store a warning flag. The detail API calculates a warning for display when `secret_scan` is enabled. Welcome eligibility scans every candidate regardless of that display preference. |
| Originality/source and asset audit | **Passed** | [originality-check.txt](design-research/welcome-evidence/originality-check.txt) records the source search and review. The audit found no reference URL/text in shipped welcome source, no imported reference media/fonts/code, and no runtime external asset host. This was a source/asset audit, not an automated similarity scan. |
| Light/dark, desktop/mobile screenshots in real/demo modes | **Passed** | Eight screenshots: [real light 1440×900](design-research/welcome-evidence/welcome-real-light-1440x900.png), [real dark 1440×900](design-research/welcome-evidence/welcome-real-dark-1440x900.png), [demo light 1440×900](design-research/welcome-evidence/welcome-demo-light-1440x900.png), [demo dark 1440×900](design-research/welcome-evidence/welcome-demo-dark-1440x900.png), [real light 390×844](design-research/welcome-evidence/welcome-real-light-390x844.png), [real dark 390×844](design-research/welcome-evidence/welcome-real-dark-390x844.png), [demo light 390×844](design-research/welcome-evidence/welcome-demo-light-390x844.png), [demo dark 390×844](design-research/welcome-evidence/welcome-demo-dark-390x844.png). |
| Fixed Start does not cover mobile content | **Passed** | Each 390×844 run scrolled to the bottom before capture. Geometry in [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): Start bounds y=776.4–832; last tile bottom y=480.1 (demo) / 480.0 (real), leaving about 296 px. The screenshots above show the fixed button at the bottom. |
| Load → rotation → hover pause → Start → app recording | **Passed** | [welcome-load-rotation-hover-start.webm](design-research/welcome-evidence/welcome-load-rotation-hover-start.webm), recorded by Playwright Video. |
| Featured rotation interval; pause on hover, focus, and hidden tab | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): Playwright clock verifies a tile change at 7,200 ms and separately verifies no advancement during hover, focus, and `document.hidden` after dispatching `visibilitychange`. |
| Reduced motion: system emulation and in-app preference | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): both modes assert no tile rotation, zero running animations from `getAnimations()`, no transforms anywhere in the welcome subtree, and working Start. Reduced Start measured 116 ms (system) and 162 ms (in-app). |
| Keyboard-only path | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): first Tab focuses Start, next Tab enters tiles, arrow navigation changes focus, Enter opens the chat, Escape and Skip enter the library. [welcome-keyboard-focus.png](design-research/welcome-evidence/welcome-keyboard-focus.png) captures visible tile focus. |
| Demo-mode privacy in browser response and DOM | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): the browser fetches the demo endpoint and checks the full response body, document title, DOM text (including hidden expanded summaries), `aria-label`, `aria-describedby` targets, `title` attributes, and local/session storage for fixture markers. No marker is present. The serialized endpoint unit test is also in [test_welcome.py](tests/test_welcome.py). |
| “Real chats visible” indicator | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): asserts the indicator exists and is visible with seeded real-mode tiles, hides in demo mode, and reappears when real tiles are restored. |
| Network remains on localhost | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json) records all 244 page requests. All 19 distinct request URLs were on `http://127.0.0.1:6044`; the complete unique URL list is below. This included the welcome load, rotation, demo-response audit, direct chat open, and Start into the app. |
| Start-to-library usable under 700 ms | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): 409.4 ms from click to populated library result count in headless Chrome. |
| Frame cadence during hover and Start transition | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): headless/CI-style 24-tile run measured 60.02 FPS during hover (61 frames, median 16.7 ms, p95 16.7 ms) and 60.02 FPS during transition (21 frames, median 16.7 ms, p95 16.8 ms). These are headless measurements, not a real laptop result. |
| Real-laptop FPS measurement | **Not run** | A headless CI-style sample cannot establish performance on the user's laptop. Exact DevTools procedure is below. |

## Local network request list

The request log contains 300 events; the following is its complete set of 21 distinct URLs. Every request used the temporary local origin shown here:

```text
http://127.0.0.1:6044/api/card-progress
http://127.0.0.1:6044/api/chat/ci-fictional-23
http://127.0.0.1:6044/api/embedding-progress
http://127.0.0.1:6044/api/filters
http://127.0.0.1:6044/api/search?q=&sort=relevance&mode=hybrid&rerank=0&archived=0
http://127.0.0.1:6044/api/welcome/tiles?demo=0
http://127.0.0.1:6044/api/welcome/tiles?demo=1
http://127.0.0.1:6044/static/app.js
http://127.0.0.1:6044/static/brand/lake-wordmark.svg
http://127.0.0.1:6044/static/enhancements.js
http://127.0.0.1:6044/static/entry.js
http://127.0.0.1:6044/static/fonts/dm-sans.woff2
http://127.0.0.1:6044/static/fonts/fraunces.woff2
http://127.0.0.1:6044/static/fonts/local-fonts.css
http://127.0.0.1:6044/static/lake-loader.js
http://127.0.0.1:6044/static/style.css
http://127.0.0.1:6044/static/welcome.css
http://127.0.0.1:6044/static/welcome.js
http://127.0.0.1:6044/welcome
```

The complete event-by-event list is the `requests` array in `welcome-browser-results.json`.

## Real-laptop FPS check

1. Start Lake locally and open `http://127.0.0.1:8765/welcome` in Chrome.
2. Open DevTools with **F12**. Press **Ctrl+Shift+P**, run **Show Rendering**, then enable **Frame rendering stats** in the Rendering drawer.
3. Hover and focus tiles while the overlay is visible; observe the live FPS estimate and frame timeline. Then click Start and observe the transition. For a representative 24-tile run, use a local library with 24 eligible chats; the Playwright fixture is deliberately fictional and contains 24.
4. Record the displayed FPS during steady hover and during the transition, along with the laptop model and Chrome version.

Chrome's documented path and overlay are described in the [Rendering tab guide](https://developer.chrome.com/docs/devtools/rendering/performance).

## Issue found and fixed

The first real-browser screenshot exposed that the pre-existing `.story-view` rule limited `#welcome-view` to 850 px and added a large top margin. That made the desktop gallery narrow and pushed most tiles below the fold. The welcome override now clears that inherited width and margin. Fix committed separately as `a9ab258` (`Fix welcome gallery desktop width`).

The first Start timing was inconsistent because it faded out and then reloaded the whole document (one run measured 910 ms). Lake now initializes the app modules during the exit animation and reveals the library in place. The final 24-tile headless measurement is 409.4 ms. This fix is committed separately as `866e8f6` (`Speed up welcome Start transition`); the final screenshots and recording were regenerated afterward.

## Run the browser suite again

See [tests/browser/README.md](tests/browser/README.md). It uses Playwright as a development-only dependency, launches installed Chrome when selected, seeds 24 fictional chats, logs browser requests, and writes all evidence to the ignored `design-research/welcome-evidence/` directory.
