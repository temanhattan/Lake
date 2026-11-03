# Lake promo

This folder contains the re-renderable promo sources only. It is dev-only and
is not imported by the Lake application.

## Current checkpoint

The character rig and sheet are the first build-order checkpoint. The two
characters are original marker-style drawings authored as layered SVG paths in
[`characters/rig.svg`](./characters/rig.svg). The sheet is generated from that
rig, not traced from an existing character or imported artwork.

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
