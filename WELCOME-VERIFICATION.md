# Welcome page verification

Date: 2026-11-03

This report distinguishes automated checks from browser checks that still need a capture-capable browser session. No unmeasured result is marked as passed.

## Automated checks

| Check | Result | Evidence |
|---|---|---|
| Demo endpoint does not return real chat content | Passed | `tests/test_welcome.py::test_demo_response_contains_only_fictional_metadata` calls the endpoint handler with a database containing a private title and secret-like transcript. It compares the complete response to `SAMPLE_TILES` and asserts neither real value is in the serialized response. |
| Archived and secrets-flagged chats are excluded in real mode | Passed | `tests/test_welcome.py::test_archived_and_secret_flagged_chats_never_appear_in_real_mode` asserts the real response IDs contain only eligible chats. |
| Response metadata allowlist and 24-item cap | Passed | `tests/test_welcome.py::test_response_is_capped_and_pins_precede_recent_and_diversified_items` checks the cap, pin order, and response keys. |
| Welcome HTTP route uses the deferred entry module | Passed | `tests/test_http.py` verifies welcome HTML does not load `app.js` directly and loads `entry.js`. |
| JavaScript syntax | Passed | `node --check` for `entry.js`, `welcome.js`, and `app.js`. |
| Full Python suite | 31 passed, 1 failed | 32 tests ran. Existing `tests/test_semantic.py::ChunkerTests::test_migration_from_mvp_schema_reaches_current_embeddings_layout` expects `PRAGMA user_version` 3, but migration returns 4. This test is outside the welcome implementation. |

The demo test inspects the handler’s serialized network response bytes, rather than only checking rendered DOM. The browser entry module also delays importing the search app until after it has selected the welcome route, so welcome startup does not issue the regular search request.

## Interaction checks

| Check | Result | Evidence / limitation |
|---|---|---|
| Featured rotation interval | Implemented, not browser-timed | `welcome.js` schedules rotation every 7,200 ms. |
| Pause on hover, focus, and hidden tab | Implemented, not browser-observed | Wall mouse enter/leave, focus in/out, and `visibilitychange` handlers stop/resume the timer. |
| Reduced motion disables rotation | Implemented, not system-emulated | System preference and Lake's stored Reduced preference both feed the rotation guard. A real browser emulation pass was not available in this run. |
| Keyboard Start / Skip / tile navigation | Implemented, not keyboard-walkthrough recorded | Start is a native button; Escape and Skip enter the app; arrow keys move between tiles; Enter activates a focused tile. |
| Start transition under 700 ms | Code path is 320 ms; not timed in browser | Reduced motion enters immediately. No frame timing capture was available. |
| No requests leave localhost | Partially verified | Welcome's fetch is a relative `/api/welcome/tiles` URL, and its HTML defers the search app. No browser network log/egress capture was available, so a complete request audit remains outstanding. |

## Visual and performance checks still outstanding

This environment did not provide a controllable browser viewport or a recording/export path. The local page rendered in the editor's embedded browser, but that surface did not expose usable click geometry or a viewport resizing control. Therefore the requested artifacts and measurements have **not** been produced:

- Screenshots of the current implementation in light and dark at 1440 px.
- Screenshots at 390 × 844 px, including confirmation that the fixed Start control does not cover content.
- A load → rotation → hover → Start → app screen recording.
- Measured frame rate during hover/transition on a mid-range laptop.
- Real `prefers-reduced-motion` emulation and keyboard-only walkthrough.
- Complete browser network panel audit.

The responsive CSS uses a one-column layout under its mobile breakpoint and places Start in a fixed bottom control with `env(safe-area-inset-bottom)`, but this is a code inspection result, not a 390 × 844 visual measurement.

## Originality

The implementation uses Lake's existing tokens and typography, a wrapper component around the existing Lake mark, and original text-only chat tiles. It adds no external image, font, SVG, JavaScript dependency, or downloaded reference asset. The reference is cited only in the design analysis. This was checked by reviewing the new welcome assets and dependency changes; no source-code similarity scanner was run.

## Current local implementation

The page is available at `/welcome`. Layout sizing, the deterministic tile-size cycle, and the mobile breakpoint are documented in the README. Three implementation commits were created before this report:

- `0d29f76` Add private welcome gallery endpoint
- `fd96fa3` Build Lake welcome gallery experience
- `3efa76f` Expose direct chat opening for welcome tiles
