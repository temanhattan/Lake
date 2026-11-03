# Welcome page verification

Run date: 2026-11-03. Browser: installed Google Chrome 156.0.8078.74, Playwright 1.64.1. The browser suite used a temporary SQLite database with 24 realistic fictional chats and a separate 5,000-chat fictional benchmark database. It never opened or queried the user's library. Screenshots, comparisons, video, JSON, and test output are in the Git-ignored `design-research/welcome-evidence/` directory.

## Results

| Check | Status | Evidence |
|---|---|---|
| Full Python unit suite | **Passed** | [unittest-full.txt](design-research/welcome-evidence/unittest-full.txt): 36 tests, `OK`. |
| Migration version expectation | **Passed** | [test_semantic.py](tests/test_semantic.py): schema version 4 is correct; the migration adds schema-v4 fields, so the old expected version 3 was stale. |
| Backup before migrating a populated copy | **Passed** | [test_semantic.py](tests/test_semantic.py): verifies the adjacent backup exists before upgrading the populated copy, retains its original version/data, and confirms the copy reaches current version 4. |
| Archived and secrets-flagged chats excluded | **Passed** | [test_welcome.py](tests/test_welcome.py): `test_archived_and_secret_flagged_chats_never_appear_in_real_mode`. |
| Unscanned chat with a fake key | **Passed** | [test_welcome.py](tests/test_welcome.py): verifies an unscanned transcript is actually passed to the detector before eligibility and is excluded. |
| Secret-warning timing and scan cache | **Passed** | [welcome.py](lake/welcome.py), [library.py](lake/library.py), [test_welcome.py](tests/test_welcome.py): there is no persisted warning flag. Import preview checks on demand; welcome eligibility scans candidates server-side on first wall request, caches only `{content_hash: boolean}`, invalidates the prior digest when an import changes content, and stops scanning after 24 eligible chats. The detail endpoint calculates its warning when requested if secret scanning is enabled. |
| 5,000-chat endpoint benchmark | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): cold **88.96 ms**, warm **67.07 ms** (target: warm under 300 ms), 24 returned. Both timings use the local HTTP endpoint and fictional data. |
| Eight real/demo light/dark viewport screenshots | **Passed** | [real light desktop](design-research/welcome-evidence/welcome-real-light-1440x900.png), [real dark desktop](design-research/welcome-evidence/welcome-real-dark-1440x900.png), [demo light desktop](design-research/welcome-evidence/welcome-demo-light-1440x900.png), [demo dark desktop](design-research/welcome-evidence/welcome-demo-dark-1440x900.png), [real light mobile](design-research/welcome-evidence/welcome-real-light-390x844.png), [real dark mobile](design-research/welcome-evidence/welcome-real-dark-390x844.png), [demo light mobile](design-research/welcome-evidence/welcome-demo-light-390x844.png), [demo dark mobile](design-research/welcome-evidence/welcome-demo-dark-390x844.png). Mobile captures are at the bottom of the stream. |
| Before/after comparison sheets | **Passed** | [desktop light](design-research/welcome-evidence/welcome-before-after-desktop-light.png), [desktop dark](design-research/welcome-evidence/welcome-before-after-desktop-dark.png), [mobile light](design-research/welcome-evidence/welcome-before-after-mobile-light.png), [mobile dark](design-research/welcome-evidence/welcome-before-after-mobile-dark.png). |
| Logo, headline, wall alignment and compact hero | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): exactly one welcome mark, no extra serif brand name, equal measured left edges, balanced headline wrapping, and the desktop wall occupies **61.7%** of the 900px viewport. |
| Brand mark stroke weight | **Passed** | [welcome-real-light-1440x900.png](design-research/welcome-evidence/welcome-real-light-1440x900.png), [welcome.css](lake/static/welcome.css): displayed SVG stroke is 28px versus the available handwritten SVG's 10px path stroke (**2.8×**). The requested `assets/brand/lake-handwriting-original.jpg` is absent from the workspace, so a JPG overlay comparison is **Not run**; the 2.8× ratio is against the available SVG source. |
| Tile variety and text contrast | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): six deterministic tag/project hues and at least one inverted solid accent in all four theme/mode combinations; measured minimum text contrast is **4.74:1** light and **6.93:1** dark. |
| Mobile settings and fixed Start | **Passed** | [real light mobile indicator view](design-research/welcome-evidence/welcome-real-light-390x844-indicator.png), [real dark mobile indicator view](design-research/welcome-evidence/welcome-real-dark-390x844-indicator.png), plus the four bottom-of-stream screenshots above. At 390×844, Start bounds are y=778–832; at bottom scroll the last tile ends at y=705.52 real / y=706.30 demo, leaving at least 71px clear. Theme and Motion controls and the settings disclosure have 44px targets; the D hint is hidden for coarse pointers. |
| “Real chats visible” indicator position | **Passed** | [desktop real light](design-research/welcome-evidence/welcome-real-light-1440x900.png), [mobile real light](design-research/welcome-evidence/welcome-real-light-390x844-indicator.png), [mobile real dark](design-research/welcome-evidence/welcome-real-dark-390x844-indicator.png): browser assertions put the pill inside the initial viewport at 1440×900 and 390×844. It tracks the real/demo toggle. |
| Featured rotation and pause | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): Playwright clock confirms rotation at 7.2 seconds and no change while hovered, focused, or hidden after `visibilitychange`. |
| Reduced motion: system and in-app | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): both paths assert no rotation, no running animations (`getAnimations()`), no transforms, and working Start. Reduced Start measured 192ms (system) / 138ms (in-app). |
| Keyboard-only path and focus | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): first Tab reaches Start; arrows move tile focus; Enter opens that tile; Escape and Skip enter the library. [welcome-keyboard-focus.png](design-research/welcome-evidence/welcome-keyboard-focus.png) shows the focus ring. |
| Demo privacy in network response and page state | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json), [run_welcome.py](tests/browser/run_welcome.py): demo response has no seeded real-chat marker; title, all text, expanded summaries, accessible names, descriptions and targets, tooltips, local/session storage also contain none. The demo page makes no search, chat, or filter API request before Start. |
| Start to usable library | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): measured with `performance.now()` at **455.8 ms**, target under 700 ms. |
| Frame cadence at 24 tiles | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): headless/CI-style Chromium measured **60.02 FPS** during hover and **60.04 FPS** during the Start transition. This is a headless measurement, not a laptop result. |
| Network audit | **Passed** | [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json) contains every request event during load, rotation, and Start. All were to the run's loopback origin; the unique URL list and totals are calculated below from that JSON. |
| Real-laptop frame rate | **Not run** | Headless CI cannot establish laptop performance. Use the DevTools instructions below for the real-world number. |
| Original JPG overlay comparison | **Not run** | The supplied relative path `assets/brand/lake-handwriting-original.jpg` does not exist in this workspace. The available SVG comparison and stroke ratio are recorded above. |
| Originality and external asset audit | **Passed** | [originality-check.txt](design-research/welcome-evidence/originality-check.txt): no reference assets/fonts/code or external runtime hosts in the welcome implementation. This is a source/asset audit, not an automated image-similarity scan. |

## Local network request list

Every browser request used the temporary loopback origin. The full event sequence is the `requests` array in [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json). Counts and the complete unique URL list below are rewritten programmatically from that JSON by `tests/browser/run_welcome.py`.

<!-- REQUEST_COUNTS_START -->
Programmatically counted from [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): **257 request events**, **19 distinct URLs**.

```text
http://127.0.0.1:40565/api/card-progress
http://127.0.0.1:40565/api/chat/ci-fictional-01
http://127.0.0.1:40565/api/embedding-progress
http://127.0.0.1:40565/api/filters
http://127.0.0.1:40565/api/search?q=&sort=relevance&mode=hybrid&rerank=0&archived=0
http://127.0.0.1:40565/api/welcome/tiles?demo=0
http://127.0.0.1:40565/api/welcome/tiles?demo=1
http://127.0.0.1:40565/static/app.js
http://127.0.0.1:40565/static/brand/lake-wordmark.svg
http://127.0.0.1:40565/static/enhancements.js
http://127.0.0.1:40565/static/entry.js
http://127.0.0.1:40565/static/fonts/dm-sans.woff2
http://127.0.0.1:40565/static/fonts/fraunces.woff2
http://127.0.0.1:40565/static/fonts/local-fonts.css
http://127.0.0.1:40565/static/lake-loader.js
http://127.0.0.1:40565/static/style.css
http://127.0.0.1:40565/static/welcome.css
http://127.0.0.1:40565/static/welcome.js
http://127.0.0.1:40565/welcome
```
<!-- REQUEST_COUNTS_END -->

## Real-laptop FPS check

1. Start Lake locally and open `http://127.0.0.1:8765/welcome` in Chrome.
2. Open DevTools with **F12**. Press **Ctrl+Shift+P**, run **Show Rendering**, then enable **Frame rendering stats** in the Rendering drawer.
3. With 24 eligible local chats, hover and focus tiles, then click Start. Read the FPS overlay during steady hover and during the transition.
4. Record both FPS values, laptop model, and Chrome version. This is the real-device result to compare with the headless measurements above.

## Issues found and fixed

- Browser contrast sampling found the date/model metadata at **3.72:1** on one light tinted tile. The metadata now uses the stronger ink-soft token; the final minimum is **4.74:1** light and **6.93:1** dark.
- The app-wide `.brand-mark{display:none}` rule hid the welcome SVG. The welcome component now has its own mark class and the browser test verifies it renders once.
- Start-time module parsing made one headless transition sample fall below 60 FPS. The welcome page now preloads the local app module without evaluating it; no library API is requested before Start. The final headless transition sample measured 60.02 FPS.
- The prior report's handwritten network totals disagreed with its URL list. The runner now derives request-event and distinct-URL counts and rewrites the complete URL list from `welcome-browser-results.json` on every successful run.

## Run the browser suite again

See [tests/browser/README.md](tests/browser/README.md). The runner uses Playwright as a development-only dependency, starts Chrome against fictional-only databases, regenerates the screenshots, focus image, video and comparison sheets under the ignored evidence directory, and fails on assertion errors.
