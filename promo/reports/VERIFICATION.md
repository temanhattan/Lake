# Promo verification report

## OCR

OCR ran on four rendered Arabic-check frames with Tesseract.js (English model).
Arabic glyphs were additionally verified visually in the rendered PNGs because
the English model cannot reliably classify Arabic script.

Observed OCR text (fixture/UI/caption allowlist review):

### out\checks\element-0060.png
```text
01: AGAIN?
WH 53 Airall Jl> dund Ul
```

### out\checks\element-0810.png
```text
search - fictional library

S— Ce mn res

Whathave vou
(Ye op

ligured out

Search results ———

Aquos that drains without sur SHER Cards that tell yor what changed
[4
in
```

### out\checks\element-1050.png
```text
eeeeNQGOWP
190 .39MS i
9 es Oblws 2
Dou (yo gllazy 0
) ol
```

### out\checks\element-1410.png
```text
Lake
Lake. <REPO_URL> - Uj»
<<HANDLE
```

No real file paths, usernames, hostnames, or third-party logos were present in the rendered frames.

## Privacy and IP

- Capture metadata confirms `demoMode: true`, `fixtureOnly: true`, device scale factor 2, and zero external requests.
- The fixture server uses a temporary SQLite database and never opens the configured user database.
- Characters are original layered SVG artwork; no imported character art or tracing is used.
- Audio is generated pen-pop sound design; no music track is included.
- CTA values remain `<REPO_URL>` and `<HANDLE>` placeholders.
- No performance, savings, or accuracy claims are present.
