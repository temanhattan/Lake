# Promo assets and licenses

## Original artwork

- `characters/rig.svg` and `characters/sheet.svg`: original Lake promo artwork
  authored for this repository. No third-party character art, tracing, or
  logos are used.
- Lake's existing handwritten stroke is referenced as a design cue only; the
  promo character paths are new artwork.

## Fonts

- `lake/static/fonts/dm-sans.woff2`: DM Sans, SIL Open Font License 1.1.
- `lake/static/fonts/arabic.woff2`: Noto Sans Arabic, SIL Open Font License 1.1.
  The license text is kept in `lake/static/fonts/licenses/`.

## Audio

No music or third-party audio is included at this checkpoint. The final
pipeline will use generated sound design or supplied/CC0 audio and will record
each source and license here before release.

## Capture

- `capture/capture_server.py` seeds a temporary SQLite database with fictional
  conversations only; it does not open `data/lake.db` or a configured library.
- `capture/capture_demo.js` uses the MIT-licensed Playwright package declared in
  `promo/package.json`. Capture metadata records demo mode and local-only
  requests.

## Claims

No performance, savings, accuracy, URL, or handle claims are included in the
character-sheet checkpoint.
