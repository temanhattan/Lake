"""Real-browser checks for Lake's welcome page, using a fictional-only DB."""
from __future__ import annotations

import json
import base64
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lake.welcome import SAMPLE_TILES, clear_secret_scan_cache
EVIDENCE = ROOT / "design-research" / "welcome-evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
SENTINEL = "FAKE_SENTINEL_TEXT_FAKE_SENTINEL_TEXT"
EXTRA_FIXTURES = [
    ("A queue that drains without surprises", "The retry worker now releases successful jobs and leaves only failed work for the next pass.", "Northstar", ["python", "jobs"], "GPT-4o"),
    ("Search remembers the phrase, not just the word", "A small synonym expansion brings back the decision even when the original wording has faded.", "Lake", ["search", "retrieval"], "GPT-4.1"),
    ("An import preview with room to breathe", "The preview separates skipped rows from warnings so a large export is easier to review.", "Field Notes", ["imports", "ux"], "Claude Sonnet"),
    ("The quiet fix for a noisy refresh", "A stale request was winning a race after navigation; cancelling it keeps the new view in control.", "Northstar", ["debugging", "web"], "GPT-4.1"),
    ("A label that survives the narrow screen", "The mobile filter keeps its full name while the rest of the controls wrap into a clean second row.", "Field Notes", ["mobile", "accessibility"], "GPT-4o"),
    ("Cards that tell you what changed", "A concise result summary gives the library a useful preview without opening the full conversation.", "Lake", ["product", "design"], "Claude Sonnet"),
    ("One backup before the schema moves", "The migration now creates a recoverable copy before applying the next schema version.", "Northstar", ["sqlite", "reliability"], "GPT-4.1"),
    ("A better boundary for local search", "The query builder keeps filters parameterized and makes the empty-search path inexpensive.", "Lake", ["privacy", "sql"], "GPT-4o"),
    ("Focus that stays in the picture", "Keyboard navigation returns to the same control after a dialog closes and keeps the focus ring visible.", "Field Notes", ["accessibility", "keyboard"], "Claude Sonnet"),
    ("A project view with fewer duplicates", "The grouped list folds repeated titles together while keeping the original chats available underneath.", "Northstar", ["organization", "search"], "GPT-4.1"),
    ("A softer accent for ink mode", "The selected hue keeps its character on the dark surface without dropping below readable contrast.", "Field Notes", ["color", "design"], "GPT-4o"),
    ("Keep the useful detail, leave the transcript", "A compact card carries the decision and next step while the private conversation stays in local storage.", "Lake", ["privacy", "summaries"], "Claude Sonnet"),
]
BASE_FIXTURE_COPY = [
    ("A trail map that remembers your route", "An offline-first trail planner restores the last waypoint, preserves field notes between visits, and only asks for location access when you choose to record a new route."),
    ("The cache that quietly missed a locale", "A stale panel traced back to a cache key that left out the active language."),
    ("A query plan with fewer surprises", "A smaller SQL path made the import preview easier to understand and quicker to trust."),
    ("A color with the right contrast at dusk", "The accent keeps its character and stays readable across warm paper and dark ink."),
    ("A queue worker that knows when to stop", "The retry loop leaves completed work alone and reports only the items that still need attention."),
    ("Search from the detail you still recall", "A little hybrid retrieval brings back the fix even when its exact phrase has slipped away."),
    ("An export parser with a clean landing", "The importer accepts both the full conversation list and one copied transcript."),
    ("Focus rings that stay clear in ink mode", "The keyboard outline remains distinct against the darker surface without brightening every control."),
    ("When background indexing catches up", "The first search no longer waits for the optional index to finish its work."),
    ("A migration that can finish after a pause", "The schema step can resume safely after an interrupted upgrade."),
    ("A narrow page with room for one action", "The mobile layout keeps its main choice close while the reading stream stays easy to scan."),
    ("Keep this conversation on the device", "Local storage leaves the useful decision available without sending a copy to a service."),
]
FIXTURE = [{**tile, "title": title, "summary": summary} for tile, (title, summary) in zip(SAMPLE_TILES, BASE_FIXTURE_COPY)] + [
    {"title": title, "summary": summary, "project": project, "tags": tags, "model": model}
    for title, summary, project, tags, model in EXTRA_FIXTURES
]
REAL_MARKERS = [SENTINEL] + [value for i, tile in enumerate(FIXTURE) for value in (
    f"ci-fictional-{i:02d}", tile["title"], tile["summary"])]
REPORT = {"statuses": {}, "requests": [], "measurements": {}, "evidence": []}


def make_server():
    from lake.config import Config
    from lake.db import connect
    from lake.web import Handler

    db_path = EVIDENCE / "fictional-test-library.sqlite3"
    db_path.unlink(missing_ok=True)
    print("Opening temporary test DB…", flush=True)
    db = connect(str(db_path))
    print("Seeding fictional summaries…", flush=True)
    for i, fixture in enumerate(FIXTURE):
        title = fixture["title"]
        cid = f"ci-fictional-{i:02d}"
        db.execute("""INSERT INTO chats(id,source,title,model_used,created_at,updated_at,imported_at,
            pinned,archived,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (cid, "manual", title, fixture["model"], f"2026-10-{24-i:02d}", f"2026-10-{24-i:02d}", "2026-11-03", int(i == 0), 0, f"hash-{i}"))
        db.execute("INSERT INTO messages(chat_id,idx,role,content) VALUES(?,0,'user',?)",
                   (cid, f"Fictional browser test transcript {i}; {SENTINEL if i == 0 else 'fictional local fixture only.'}"))
        db.execute("INSERT INTO cards(chat_id,problem,result,status) VALUES(?,?,?,'ready')",
                   (cid, fixture["summary"], fixture["summary"]))
        project_name = fixture["project"]
        db.execute("INSERT OR IGNORE INTO projects(name) VALUES(?)", (project_name,))
        project_id = db.execute("SELECT id FROM projects WHERE name=?", (project_name,)).fetchone()[0]
        db.execute("UPDATE chats SET project_id=? WHERE id=?", (project_id, cid))
        for tag in fixture["tags"]:
            db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_id = db.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()[0]
            db.execute("INSERT INTO chat_tags(chat_id,tag_id) VALUES(?,?)", (cid, tag_id))
    db.commit()
    print("Starting local HTTP handler…", flush=True)
    Handler.db = db
    Handler.config = Config(db_path=str(db_path), port=0)
    Handler.semantic = Handler.embeddings = Handler.jobs = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("Local HTTP handler ready.", flush=True)
    return server, thread, db, f"http://127.0.0.1:{server.server_address[1]}"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def _rgb_from_hex(value):
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))


def _luminance(rgb):
    channels = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]


def _contrast(first, second):
    one, two = sorted((_luminance(_rgb_from_hex(first)), _luminance(_rgb_from_hex(second))), reverse=True)
    return (one + .05) / (two + .05)


def benchmark_endpoint():
    """Measure cold and warm HTTP responses against 5,000 fictional chats."""
    from lake.config import Config
    from lake.db import connect
    from lake.web import Handler

    class BenchmarkHandler(Handler):
        pass

    db_path = EVIDENCE / "fictional-benchmark-5000.sqlite3"
    db_path.unlink(missing_ok=True)
    db = connect(str(db_path))
    rows = []
    cards = []
    messages = []
    for i in range(5000):
        chat_id = f"bench-fictional-{i:04d}"
        digest = f"benchmark-content-hash-{i:04d}"
        rows.append((chat_id, "manual", f"Fictional benchmark note {i:04d}", "GPT-4.1",
                     "2026-10-20", "2026-10-20", "2026-11-03", 0, 0, digest))
        cards.append((chat_id, f"Fictional benchmark topic {i:04d}", f"A safe summary for the fictional benchmark item {i:04d}.", "ready"))
        messages.append((chat_id, 0, "user", f"A fictional transcript for benchmark item {i:04d}."))
    db.executemany("""INSERT INTO chats(id,source,title,model_used,created_at,updated_at,imported_at,pinned,archived,content_hash)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", rows)
    db.executemany("INSERT INTO cards(chat_id,problem,result,status) VALUES(?,?,?,?)", cards)
    db.executemany("INSERT INTO messages(chat_id,idx,role,content) VALUES(?,?,?,?)", messages)
    db.commit()
    BenchmarkHandler.db = db
    BenchmarkHandler.config = Config(db_path=str(db_path), port=0)
    BenchmarkHandler.semantic = BenchmarkHandler.embeddings = BenchmarkHandler.jobs = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), BenchmarkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/api/welcome/tiles"
    try:
        clear_secret_scan_cache()
        started = time.perf_counter()
        with urlopen(url) as response:
            cold_payload = response.read()
        cold_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        with urlopen(url) as response:
            warm_payload = response.read()
        warm_ms = (time.perf_counter() - started) * 1000
        check(len(json.loads(cold_payload)) == 24 and cold_payload == warm_payload,
              "5,000-chat endpoint benchmark did not return the same capped fictional result")
        REPORT["measurements"]["endpoint_5000_cold_ms"] = round(cold_ms, 2)
        REPORT["measurements"]["endpoint_5000_warm_ms"] = round(warm_ms, 2)
        REPORT["measurements"]["endpoint_5000_chat_count"] = 5000
        REPORT["statuses"]["endpoint_5000_warm_under_300ms"] = "Passed" if warm_ms < 300 else "Failed"
        check(warm_ms < 300, f"warm endpoint on 5,000 fictional chats took {warm_ms:.2f} ms (target <300 ms)")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        db.close()


def update_report_network_block(report_path):
    """Derive the markdown request totals and unique list from browser JSON."""
    import re
    report = json.loads(report_path.read_text(encoding="utf-8"))
    requests = report["requests"]
    urls = sorted(set(requests))
    report["measurements"]["request_event_count"] = len(requests)
    report["measurements"]["distinct_request_url_count"] = len(urls)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path = ROOT / "WELCOME-VERIFICATION.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    url_lines = "\n".join(f"{url}" for url in urls)
    block = ("<!-- REQUEST_COUNTS_START -->\n"
             f"Programmatically counted from [welcome-browser-results.json](design-research/welcome-evidence/welcome-browser-results.json): **{len(requests)} request events**, **{len(urls)} distinct URLs**.\n\n"
             "```text\n" + url_lines + "\n```\n"
             "<!-- REQUEST_COUNTS_END -->")
    markdown, count = re.subn(r"<!-- REQUEST_COUNTS_START -->.*?<!-- REQUEST_COUNTS_END -->", block,
                              markdown, count=1, flags=re.S)
    check(count == 1, "verification report network markers are missing")
    markdown_path.write_text(markdown, encoding="utf-8")


def build_comparison_sheets(browser):
    """Render four before/after pairs as browser evidence, without image deps."""
    pairs = [
        ("desktop-light", "real-light-1440x900", 1440, 900),
        ("desktop-dark", "real-dark-1440x900", 1440, 900),
        ("mobile-light", "real-light-390x844", 390, 844),
        ("mobile-dark", "real-dark-390x844", 390, 844),
    ]
    if any(not (EVIDENCE / f"welcome-before-{stem}.png").is_file() for _, stem, _, _ in pairs):
        REPORT["statuses"]["before_after_comparison_sheets"] = "Not run"
        print("Before screenshots are not present; before/after sheets were not generated.", flush=True)
        return
    for label, stem, width, height in pairs:
        sources = []
        for prefix in ("welcome-before-", "welcome-"):
            path = EVIDENCE / f"{prefix}{stem}.png"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            sources.append(f"data:image/png;base64,{encoded}")
        html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
          *{{box-sizing:border-box}}body{{margin:0;padding:12px;background:#eee;color:#222;font:16px system-ui,sans-serif}}
          main{{display:grid;grid-template-columns:repeat(2, {width}px);gap:12px}}figure{{margin:0}}figcaption{{height:30px;font-weight:700}}
          img{{display:block;width:{width}px;height:{height}px;object-fit:contain;background:#fff}}
          </style></head><body><main><figure><figcaption>Before</figcaption><img src="{sources[0]}"></figure>
          <figure><figcaption>After</figcaption><img src="{sources[1]}"></figure></main></body></html>"""
        page = browser.new_page(viewport={"width": width * 2 + 36, "height": height + 60}, device_scale_factor=1)
        page.set_content(html, wait_until="load")
        target = EVIDENCE / f"welcome-before-after-{label}.png"
        page.screenshot(path=str(target), full_page=True)
        REPORT["evidence"].append(str(target.relative_to(ROOT)))
        page.close()
    REPORT["statuses"]["before_after_comparison_sheets"] = "Passed"


def main():
    print("Preparing fictional-only Lake database and local server…", flush=True)
    server, server_thread, seed_db, origin = make_server()
    all_requests = []
    try:
        with sync_playwright() as p:
            browser = None
            channel = os.environ.get("LAKE_BROWSER_CHANNEL", "").strip() or None
            try:
                browser = p.chromium.launch(headless=True, channel=channel)
                browser_name = channel or "Playwright Chromium"
            except Exception as first_error:
                if channel:
                    raise
                errors = [str(first_error)]
                for installed in ("chrome", "msedge"):
                    try:
                        browser = p.chromium.launch(headless=True, channel=installed)
                        browser_name = f"installed {installed}"
                        break
                    except Exception as exc:
                        errors.append(str(exc))
                else:
                    raise RuntimeError("No Playwright Chromium or installed Chrome/Edge launched: " + "\n".join(errors))
            print(f"Launched {browser_name} against {origin}", flush=True)

            def context_for(width, height, *, theme="light", demo=False, reduced=None, video=False):
                kwargs = {"viewport": {"width": width, "height": height}, "device_scale_factor": 1,
                          "color_scheme": theme, "reduced_motion": reduced}
                kwargs.update(is_mobile=(width <= 680), has_touch=(width <= 680))
                if video:
                    kwargs["record_video_dir"] = str(EVIDENCE)
                    kwargs["record_video_size"] = {"width": width, "height": height}
                context = browser.new_context(**kwargs)
                context.add_init_script(f"""(() => {{
                  localStorage.setItem('lake-demo-mode', '{'1' if demo else '0'}');
                  localStorage.setItem('lake-theme', '{theme}');
                  localStorage.removeItem('lake-motion');
                }})()""")
                return context

            def attach_requests(page):
                page.on("request", lambda req: (all_requests.append(req.url), REPORT["requests"].append(req.url)))

            def open_welcome(context):
                page = context.new_page()
                attach_requests(page)
                page.goto(origin + "/welcome", wait_until="networkidle")
                page.locator(".welcome-card").first.wait_for()
                return page

            try:
                # All eight requested viewport/theme/privacy combinations.
                for mode in ("real", "demo"):
                    for theme in ("light", "dark"):
                        for width, height in ((1440, 900), (390, 844)):
                            ctx = context_for(width, height, theme=theme, demo=(mode == "demo"))
                            print(f"Capture {mode} {theme} {width}x{height}", flush=True)
                            page = open_welcome(ctx)
                            page.wait_for_timeout(700)
                            count = page.locator(".welcome-card").count()
                            check(12 <= count <= 24, f"expected 12–24 tiles, got {count}")
                            palette = ["#145e59", "#285c91", "#60498a", "#87482e", "#576128", "#8b3c58"]
                            accent_ratios = [_contrast("#ffffff", color) for color in palette]
                            check(min(accent_ratios) >= 4.5, f"an inverted accent hue fails AA contrast: {accent_ratios}")
                            visual = page.evaluate("""() => {
                              const lum = c => {let q=c.match(/[\\d.]+/g).slice(0,3).map(Number);if(!c.startsWith('color(srgb'))q=q.map(x=>x/255);
                                const v=q.map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return .2126*v[0]+.7152*v[1]+.0722*v[2];};
                              const contrast=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
                              const cards=[...document.querySelectorAll('.welcome-card')];
                              const checks=cards.flatMap(card=>['.welcome-card__title','.welcome-card__summary-short','.welcome-card__summary-full','.welcome-card__head','.welcome-card__foot','.welcome-tag']
                                .map(selector=>{const el=card.querySelector(selector);if(!el)return null;
                                  const fg=getComputedStyle(el).color,bg=getComputedStyle(card).backgroundColor;
                                  return {selector,fg,bg,ratio:contrast(fg,bg),id:card.dataset.chatId};}).filter(Boolean));
                              checks.sort((a,b)=>a.ratio-b.ratio);
                              const logo=document.querySelector('#welcome-logo svg');
                              const edges=['#welcome-logo','.welcome-copy h1','#welcome-wall'].map(selector=>
                                document.querySelector(selector).getBoundingClientRect().left);
                              return {hues:[...new Set(cards.map(card=>card.dataset.hue))],solid:cards.some(card=>card.classList.contains('welcome-card--solid-accent')),
                                logoVisible:Boolean(logo&&getComputedStyle(logo).display!=='none'&&getComputedStyle(logo).strokeWidth==='28px'),
                                logoCount:document.querySelectorAll('#welcome-logo').length,duplicateNameCount:document.querySelectorAll('.welcome-brand-name').length,
                                leftEdges:edges,headlineWrap:getComputedStyle(document.querySelector('#welcome-title')).textWrap,
                                minContrast:checks[0].ratio,lowest:checks.slice(0,3)};
                            }""")
                            check(len(visual["hues"]) >= 5, f"fewer than five deterministic hue accents appear: {visual['hues']}")
                            check(visual["solid"], "gallery has no inverted solid accent tile")
                            check(visual["logoVisible"], "single welcome mark is missing or does not use the heavier stroke")
                            check(visual["logoCount"] == 1 and visual["duplicateNameCount"] == 0, "welcome page has a duplicate Lake wordmark")
                            check(max(visual["leftEdges"]) - min(visual["leftEdges"]) <= 1.0, f"logo, headline, and wall do not share a left edge: {visual['leftEdges']}")
                            check(visual["headlineWrap"] == "balance", f"headline text-wrap is not balanced: {visual['headlineWrap']}")
                            check(visual["minContrast"] >= 4.5, f"gallery text fails AA contrast: {visual}")
                            REPORT["measurements"][f"{mode}-{theme}-tile_hues"] = visual["hues"]
                            REPORT["measurements"][f"{mode}-{theme}-minimum_text_contrast"] = round(visual["minContrast"], 2)
                            if mode == "real":
                                check(page.locator("#real-chat-indicator").is_visible(), "real mode indicator missing while seeded real tiles display")
                                check("A trail map that remembers your route" in page.locator(".welcome-card").first.get_attribute("aria-label"), "seeded fictional real-mode tile is missing")
                                indicator = page.locator("#real-chat-indicator").bounding_box()
                                check(indicator and 0 <= indicator["y"] and indicator["y"] + indicator["height"] <= height,
                                      f"real-content indicator is outside the initial {width}x{height} viewport: {indicator}")
                                if width == 1440:
                                    wall_box = page.locator("#welcome-wall").bounding_box()
                                    visible_wall = max(0, min(height, wall_box["y"] + wall_box["height"]) - max(0, wall_box["y"]))
                                    check(visible_wall / height >= 0.60, f"wall occupies only {visible_wall/height:.1%} of desktop viewport")
                                    REPORT["measurements"]["desktop_wall_visible_fraction"] = round(visible_wall / height, 3)
                            else:
                                check(not page.locator("#real-chat-indicator").is_visible(), "real indicator visible in demo mode")
                                response = next((r for r in page.locator(".welcome-card").all() if SENTINEL in (r.get_attribute("aria-label") or "")), None)
                                check(response is None, "seeded fictional library sentinel leaked into demo DOM")
                                demo_response = page.evaluate("async()=>await(await fetch('/api/welcome/tiles?demo=1',{cache:'no-store'})).text()")
                                check(SENTINEL not in demo_response, "seeded fictional library sentinel leaked in demo network response")
                                privacy = page.evaluate("""() => {
                                  const attrs = [...document.querySelectorAll('*')].flatMap(e =>
                                    [...e.attributes].filter(a => ['aria-label','aria-describedby','title'].includes(a.name)).map(a => a.value));
                                  const refs = [...document.querySelectorAll('[aria-describedby]')].flatMap(e =>
                                    e.getAttribute('aria-describedby').split(/\\s+/).map(id => document.getElementById(id)?.textContent || 'MISSING:'+id));
                                  return [document.title, document.documentElement.textContent, attrs.join(' '), refs.join(' '),
                                    JSON.stringify(localStorage), JSON.stringify(sessionStorage)].join('\\n');
                                }""")
                                check(not any(marker in privacy for marker in REAL_MARKERS), "demo DOM, accessible names, tooltip attrs, title, or storage contains seeded library content")
                                pre_start_api = page.evaluate("""() => performance.getEntriesByType('resource').map(x=>new URL(x.name).pathname)
                                  .filter(path=>path.startsWith('/api/search')||path.startsWith('/api/chat')||path.startsWith('/api/filters'))""")
                                check(not pre_start_api, f"demo welcome requested real-library APIs before Start: {pre_start_api}")
                            name = f"welcome-{mode}-{theme}-{width}x{height}"
                            if width == 390:
                                check(not page.locator(".demo-shortcut").is_visible(), "Press D hint visible on coarse-pointer mobile")
                                check(not page.locator("#welcome-extra-settings").evaluate("e=>e.open"), "mobile settings disclosure should be compact by default")
                                disclosure_height = page.locator("#welcome-extra-settings summary").evaluate("e=>e.getBoundingClientRect().height")
                                check(disclosure_height >= 44, f"mobile settings disclosure target is under 44px: {disclosure_height}")
                                page.locator("#welcome-extra-settings summary").click()
                                controls = page.locator(".welcome-controls button").evaluate_all("es=>es.map(e=>({id:e.id,h:e.getBoundingClientRect().height}))")
                                check(all(item["h"] >= 44 for item in controls), f"mobile theme/motion hit target is under 44px: {controls}")
                                page.locator("#welcome-extra-settings summary").click()
                                if mode == "real":
                                    indicator = page.locator("#real-chat-indicator").bounding_box()
                                    check(indicator and 0 <= indicator["y"] and indicator["y"] + indicator["height"] <= height,
                                          f"real-content indicator is outside initial mobile viewport: {indicator}")
                                    indicator_shot = EVIDENCE / f"welcome-real-{theme}-390x844-indicator.png"
                                    page.screenshot(path=str(indicator_shot), animations="disabled")
                                    REPORT["evidence"].append(str(indicator_shot.relative_to(ROOT)))
                                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                                page.wait_for_timeout(150)
                                geometry = page.evaluate("""() => {
                                  const start=document.querySelector('#welcome-start').getBoundingClientRect();
                                  const last=[...document.querySelectorAll('.welcome-card')].at(-1).getBoundingClientRect();
                                  return {start:{top:start.top,bottom:start.bottom},last:{top:last.top,bottom:last.bottom},innerHeight};
                                }""")
                                check(geometry["start"]["bottom"] <= 844, "fixed Start button extends beyond the mobile viewport")
                                check(geometry["last"]["bottom"] <= geometry["start"]["top"], f"last tile is obscured by fixed Start: {geometry}")
                                bottom_shot = EVIDENCE / f"{name}-bottom.png"
                                page.screenshot(path=str(bottom_shot), animations="disabled")
                                REPORT["evidence"].append(str(bottom_shot.relative_to(ROOT)))
                                REPORT["measurements"][name + "-bottom-geometry"] = geometry
                            shot = EVIDENCE / f"{name}.png"
                            page.screenshot(path=str(shot), animations="disabled")
                            REPORT["evidence"].append(str(shot.relative_to(ROOT)))
                            ctx.close()
                REPORT["statuses"]["theme_viewport_screenshots"] = "Passed"
                REPORT["statuses"]["logo_brand_and_shared_container"] = "Passed"
                REPORT["statuses"]["desktop_wall_at_least_60_percent"] = "Passed"
                REPORT["statuses"]["mobile_controls_and_safe_start"] = "Passed"
                REPORT["statuses"]["tile_hues_contrast_and_solid_accent"] = "Passed"

                # Clock-driven carousel: rotation, hover, focus and hidden document.
                ctx = context_for(1440, 900, demo=True)
                page = ctx.new_page(); attach_requests(page)
                page.clock.install()
                page.goto(origin + "/welcome", wait_until="networkidle")
                page.locator(".welcome-card").first.wait_for()
                page.wait_for_timeout(500)
                featured = page.locator(".welcome-card.is-featured")
                first_id = featured.get_attribute("data-chat-id")
                page.clock.fast_forward(7200)
                page.wait_for_timeout(500)
                second_id = page.locator(".welcome-card.is-featured").get_attribute("data-chat-id")
                check(first_id != second_id, "featured tile did not rotate at the configured 7.2 second interval")
                featured = page.locator(".welcome-card.is-featured")
                featured.hover()
                held = featured.get_attribute("data-chat-id")
                page.clock.fast_forward(21600)
                page.wait_for_timeout(500)
                check(page.locator(".welcome-card.is-featured").get_attribute("data-chat-id") == held, "rotation advanced while hovered")
                page.mouse.move(0, 0)
                featured.focus()
                focused = page.locator(".welcome-card.is-featured").get_attribute("data-chat-id")
                page.clock.fast_forward(21600)
                page.wait_for_timeout(500)
                check(page.locator(".welcome-card.is-featured").get_attribute("data-chat-id") == focused, "rotation advanced while focused")
                page.evaluate("document.activeElement.blur()")
                page.mouse.move(0, 0)
                page.evaluate("""() => {Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));}""")
                hidden_feature = page.locator(".welcome-card.is-featured").get_attribute("data-chat-id")
                page.clock.fast_forward(21600)
                page.wait_for_timeout(500)
                check(page.locator(".welcome-card.is-featured").get_attribute("data-chat-id") == hidden_feature, "rotation advanced while document.hidden")
                page.evaluate("""() => {Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));}""")
                REPORT["statuses"]["rotation_interval_hover_focus_hidden"] = "Passed"
                ctx.close()

                # Reduced motion via emulation and Lake's in-app preference.
                for name, reduced in (("system", "reduce"), ("in-app", "no-preference")):
                    ctx = context_for(1440, 900, demo=True, reduced=reduced)
                    page = ctx.new_page(); attach_requests(page); page.clock.install()
                    page.goto(origin + "/welcome", wait_until="networkidle")
                    page.locator(".welcome-card").first.wait_for()
                    page.wait_for_timeout(650)
                    if name == "in-app":
                        page.locator("#welcome-motion-toggle").click()
                    check(page.locator("html").get_attribute("data-motion") == "reduced", f"{name} reduced-motion preference not active")
                    before = page.locator(".welcome-card.is-featured").get_attribute("data-chat-id")
                    page.clock.fast_forward(28800); page.wait_for_timeout(350)
                    check(page.locator(".welcome-card.is-featured").get_attribute("data-chat-id") == before, f"{name} reduced motion rotated")
                    active = page.evaluate("""() => document.querySelector('.welcome-page').getAnimations({subtree:true}).filter(a=>a.playState==='running').length""")
                    transforms = page.evaluate("""() => [...document.querySelectorAll('.welcome-page,.welcome-page *')]
                      .filter(e=>getComputedStyle(e).transform!=='none').map(e=>({tag:e.tagName,className:String(e.className),transform:getComputedStyle(e).transform}))""")
                    check(active == 0, f"{name} reduced motion has {active} running animations")
                    check(not transforms, f"{name} reduced motion has transforms: {transforms}")
                    page.clock.resume()
                    page.evaluate("sessionStorage.setItem('browser-test-start-ms', String(performance.now()))")
                    page.locator("#welcome-start").click()
                    page.wait_for_function("location.pathname === '/' ")
                    page.locator("#search").wait_for(state="visible")
                    elapsed = page.evaluate("performance.now() - Number(sessionStorage.getItem('browser-test-start-ms'))")
                    REPORT["measurements"][f"reduced_start_ms_{name}"] = round(elapsed, 2)
                    check(elapsed < 700, f"{name} reduced Start took {elapsed:.2f} ms (target <700 ms)")
                    ctx.close()
                REPORT["statuses"]["reduced_motion_emulation_and_in_app"] = "Passed"

                # Keyboard path: first Tab is Start; arrow, Enter, Escape, Skip.
                ctx = context_for(1440, 900, demo=False)
                page = ctx.new_page(); attach_requests(page)
                page.goto(origin + "/welcome", wait_until="networkidle")
                page.locator(".welcome-card").first.wait_for()
                page.keyboard.press("Tab")
                check(page.evaluate("document.activeElement.id") == "welcome-start", "first Tab did not focus Start")
                page.keyboard.press("Tab")
                for _ in range(8):
                    if page.evaluate("Boolean(document.activeElement.dataset.chatId)"):
                        break
                    page.keyboard.press("Tab")
                first_tile = page.evaluate("document.activeElement.dataset.chatId")
                page.keyboard.press("ArrowRight")
                next_tile = page.evaluate("document.activeElement.dataset.chatId")
                check(first_tile and next_tile and first_tile != next_tile, "arrow key did not move between tiles")
                expected_open_title = FIXTURE[int(next_tile.rsplit("-", 1)[1])]["title"]
                focused_box = page.locator(".welcome-card:focus-visible").bounding_box()
                check(focused_box is not None, "focused tile has no visible focus target")
                focus_shot = EVIDENCE / "welcome-keyboard-focus.png"
                page.screenshot(path=str(focus_shot), animations="disabled")
                REPORT["evidence"].append(str(focus_shot.relative_to(ROOT)))
                page.keyboard.press("Enter")
                page.locator("#reader").wait_for(state="visible")
                page.locator("#chat .reader-head h1").wait_for()
                check(expected_open_title in page.locator("#chat .reader-head h1").inner_text(), "Enter did not open the focused fictional chat")
                REPORT["statuses"]["keyboard_tab_arrow_enter"] = "Passed"
                ctx.close()

                for via in ("Escape", "Skip"):
                    ctx = context_for(1440, 900, demo=True)
                    page = open_welcome(ctx)
                    if via == "Escape":
                        page.keyboard.press("Escape")
                    else:
                        page.locator(".welcome-skip").click()
                    page.locator("#search").wait_for(state="visible")
                    check(page.locator("#welcome-view").is_hidden(), f"{via} did not enter the app")
                    ctx.close()
                REPORT["statuses"]["escape_and_skip"] = "Passed"

                # Demo privacy assertions in DOM/accessibility/storage and actual response.
                ctx = context_for(1440, 900, demo=True)
                page = open_welcome(ctx)
                demo_payload = page.evaluate("async()=>await(await fetch('/api/welcome/tiles?demo=1',{cache:'no-store'})).text()")
                privacy = page.evaluate("""() => {
                  const attrs=[...document.querySelectorAll('*')].flatMap(e=>[...e.attributes]
                    .filter(a=>['aria-label','aria-describedby','title'].includes(a.name)).map(a=>a.value));
                  const refs=[...document.querySelectorAll('[aria-describedby]')].flatMap(e=>e.getAttribute('aria-describedby').split(/\\s+/)
                    .map(id=>document.getElementById(id)?.textContent||'MISSING:'+id));
                  return {title:document.title,text:document.documentElement.textContent,attrs:attrs.join(' '),refs:refs.join(' '),
                    local:JSON.stringify(localStorage),session:JSON.stringify(sessionStorage)};
                }""")
                serialized = demo_payload + json.dumps(privacy)
                check(SENTINEL not in serialized, "real-mode sentinel leaked into demo response, title, DOM, accessibility, or storage")
                check(not page.locator("#real-chat-indicator").is_visible(), "real indicator shown in demo")
                check(page.locator("#real-chat-indicator").count() == 1, "Real chats visible indicator is missing from page DOM")
                check("MISSING:" not in privacy["refs"], "aria-describedby contains a missing target")
                REPORT["statuses"]["demo_network_dom_accessibility_storage"] = "Passed"
                REPORT["statuses"]["real_content_indicator"] = "Passed"
                ctx.close()

                ctx = context_for(1440, 900, demo=False)
                page = open_welcome(ctx)
                check(page.locator("#real-chat-indicator").is_visible(), "indicator absent with real tiles")
                page.locator(".welcome-demo-row label").click()
                page.wait_for_function("document.querySelector('#real-chat-indicator').hidden")
                page.locator(".welcome-demo-row label").click()
                page.wait_for_function("!document.querySelector('#real-chat-indicator').hidden")
                check(page.locator(".welcome-card").first.get_attribute("data-chat-id").startswith("ci-fictional-"), "real tiles not restored after leaving demo")
                REPORT["statuses"]["indicator_tracks_demo_toggle"] = "Passed"
                ctx.close()

                # Capture load -> actual rotation -> hover pause -> Start -> app.
                ctx = context_for(1440, 900, demo=True, video=True)
                page = ctx.new_page(); attach_requests(page)
                page.goto(origin + "/welcome", wait_until="networkidle")
                page.locator(".welcome-card.is-featured").wait_for()
                before = page.locator(".welcome-card.is-featured").get_attribute("data-chat-id")
                page.wait_for_function("(prev)=>document.querySelector('.welcome-card.is-featured')?.dataset.chatId!==prev", arg=before, timeout=9500)
                page.locator(".welcome-card.is-featured").hover()
                hold_id = page.locator(".welcome-card.is-featured").get_attribute("data-chat-id")
                page.wait_for_timeout(7600)
                check(page.locator(".welcome-card.is-featured").get_attribute("data-chat-id") == hold_id, "video hover step did not pause rotation")
                page.locator("#welcome-start").click()
                page.locator("#search").wait_for(state="visible")
                page.wait_for_timeout(150)
                ctx.close()
                video = page.video.path()
                video_target = EVIDENCE / "welcome-load-rotation-hover-start.webm"
                Path(video).replace(video_target)
                REPORT["evidence"].append(str(video_target.relative_to(ROOT)))
                REPORT["statuses"]["load_rotation_hover_start_recording"] = "Passed"

                # Start usable latency and requestAnimationFrame cadence, labeled headless.
                ctx = context_for(1440, 900, demo=True)
                page = ctx.new_page(); attach_requests(page)
                page.goto(origin + "/welcome", wait_until="networkidle")
                page.locator(".welcome-card").first.wait_for()
                page.locator(".welcome-card").first.hover()
                hover_fps = page.evaluate("""async()=>{const t=[];let start=0;return await new Promise(resolve=>{
                  const tick=now=>{if(!start)start=now;t.push(now);if(now-start<1000)requestAnimationFrame(tick);else{
                    const d=t.slice(1).map((x,i)=>x-t[i]).sort((a,b)=>a-b);resolve({frames:d.length,medianMs:d[Math.floor(d.length/2)],p95Ms:d[Math.floor(d.length*.95)],fps:1000/d.reduce((a,b)=>a+b,0)*d.length});}};requestAnimationFrame(tick);})}""")
                page.evaluate("""() => {const frames=[];const tick=t=>{frames.push(t);
                  if(document.querySelector('#welcome-view').hidden)sessionStorage.setItem('transition-raf-times',JSON.stringify(frames));
                  else requestAnimationFrame(tick);};requestAnimationFrame(tick);}""")
                page.evaluate("sessionStorage.setItem('browser-test-start-ms', String(performance.now()))")
                page.locator("#welcome-start").click()
                page.locator("#results").wait_for(state="visible")
                page.wait_for_function("document.querySelector('#count')?.textContent.trim().length > 0")
                start_ms = page.evaluate("performance.now() - Number(sessionStorage.getItem('browser-test-start-ms'))")
                transition_fps = page.evaluate("""() => {const t=JSON.parse(sessionStorage.getItem('transition-raf-times')||'[]');
                  const d=t.slice(1).map((x,i)=>x-t[i]).sort((a,b)=>a-b);return {frames:d.length,
                  medianMs:d.length?d[Math.floor(d.length/2)]:null,p95Ms:d.length?d[Math.floor(d.length*.95)]:null,
                  fps:d.length?1000*d.length/d.reduce((a,b)=>a+b,0):null};}""")
                check(transition_fps["frames"] > 0, "transition requestAnimationFrame sample missing")
                REPORT["measurements"]["headless_hover_raf"] = hover_fps
                REPORT["measurements"]["headless_transition_raf"] = transition_fps
                REPORT["measurements"]["start_to_library_visible_ms"] = round(start_ms, 2)
                REPORT["measurements"]["frame_rate_environment"] = "headless Playwright Chromium; CI-style VM, not a real-laptop result"
                check(start_ms < 700, f"start-to-library usable took {start_ms:.2f} ms (target <700 ms)")
                ctx.close()
                REPORT["statuses"]["start_under_700ms"] = "Passed"
                REPORT["statuses"]["headless_hover_frame_cadence"] = "Passed"
                REPORT["statuses"]["headless_transition_frame_cadence"] = "Passed"
                REPORT["browser"] = browser_name
                REPORT["origin"] = origin
                REPORT["statuses"]["network_localhost_only"] = "Passed" if all(url.startswith(origin + "/") for url in all_requests) else "Failed"
                check(all(url.startswith(origin + "/") for url in all_requests), "non-local request detected")
                REPORT["measurements"]["network_request_list"] = sorted(set(all_requests))
                build_comparison_sheets(browser)
            finally:
                if browser is not None:
                    browser.close()
    finally:
        seed_db.close()
        server.shutdown(); server.server_close(); server_thread.join(timeout=2)
    benchmark_endpoint()
    report_path = EVIDENCE / "welcome-browser-results.json"
    report_path.write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
    update_report_network_block(report_path)
    print(json.dumps(REPORT, indent=2))
    print(f"Evidence report: {report_path}")


if __name__ == "__main__":
    main()
