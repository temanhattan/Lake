# Lake promo

This folder contains the re-renderable promo sources only. It is dev-only and
is not imported by the Lake application.

## Current checkpoint

The character rig and sheet are the first build-order checkpoint. The two
characters are original marker-style drawings authored as layered SVG paths in
[`characters/rig.svg`](./characters/rig.svg). The sheet is generated from that
rig, not traced from an existing character or imported artwork.

The approved storyboard and data-driven bilingual timing live in
[`script.json`](./script.json) and [`storyboard.svg`](./storyboard.svg).

## Fictional UI capture

The capture runner starts a temporary SQLite database seeded only with
fictional promo conversations, enables Lake demo mode before navigation, and
captures the welcome wall, library, search, chat, and context-block states:

```powershell
npm run capture:demo
```

The screenshots and `capture.json` metadata are written to `captures/` (and
ignored by git). The metadata records the device scale factor, fixture-only
flag, local request paths, and an empty external-request list.

## Scene composition checkpoint

The Remotion composition in [`src/Promo.jsx`](./src/Promo.jsx) reads scene
timings and captions directly from `script.json`. It supports English and
Egyptian Arabic caption props, RTL alignment for Arabic, a safe caption zone,
and a `reducedMotion` prop that disables the boil/wobble motion. After capture:

```powershell
npm run render
```

renders review frames into ignored `out/frames/`. The command bundles the
composition with the MIT-licensed Remotion renderer and copies capture stills
into a temporary public directory.

Output targets:

```powershell
npm run captions
npm run sound-design
npm run render:video
npm run render:gif
```

The resulting ignored files are the English and Arabic vertical masters, the
16:9 cut, the 15-second teaser, and a 360x640 reduced-motion README GIF. The
Arabic frame check is `npm run render:checks`; inspect its PNGs for shaped RTL
text using the OFL Noto Sans Arabic font.

Run the final OCR/privacy report with:

```powershell
npm run verify:ocr
```

The report is written to [`reports/VERIFICATION.md`](./reports/VERIFICATION.md).

## Planned renderer

The pipeline will use Remotion for deterministic, code-driven scene timing,
with Playwright for the fictional-library capture and FFmpeg-compatible
encoding for MP4/GIF outputs. Remotion is MIT licensed; Playwright is Apache
2.0 licensed. These are development dependencies only. The exact encoder and
asset licenses will be recorded in [`ASSETS.md`](./ASSETS.md) before renders
are declared complete.

## Re-render

Once the remaining scenes and render scripts are present:

```powershell
npm install
npm run render
```

Rendered media belongs in `promo/out/` and is intentionally ignored by git.
