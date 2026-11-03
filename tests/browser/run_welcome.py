"""Real-browser checks for Lake's welcome page, using a fictional-only DB."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / "design-research" / "welcome-evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)
SENTINEL = "FAKE_SENTINEL_TEXT_FAKE_SENTINEL_TEXT"
REAL_MARKERS = [SENTINEL, "Test model"] + [value for i in range(24) for value in (
    f"ci-fictional-{i:02d}", f"Fictional conversation {i+1:02d}",
    f"Fictional browser issue {i}", f"Fictional browser resolution {i}",
)] + ["Fictional browser test transcript 0", "test-tag-"]
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
    for i in range(24):
        title = f"Fictional conversation {i+1:02d}"
        cid = f"ci-fictional-{i:02d}"
        db.execute("""INSERT INTO chats(id,source,title,model_used,created_at,updated_at,imported_at,
            pinned,archived,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (cid, "manual", title, "Test model", f"2026-10-{i+1:02d}", f"2026-10-{i+1:02d}", "2026-11-03", int(i == 0), 0, f"hash-{i}"))
        db.execute("INSERT INTO messages(chat_id,idx,role,content) VALUES(?,0,'user',?)",
                   (cid, f"Fictional browser test transcript {i}; {SENTINEL if i == 0 else 'no user data.'}"))
        db.execute("INSERT INTO cards(chat_id,problem,result,status) VALUES(?,?,?,'ready')",
                   (cid, f"Fictional browser issue {i}", f"Fictional browser resolution {i}"))
        tag = f"test-tag-{i % 4}"
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
                            if mode == "real":
                                check(page.locator("#real-chat-indicator").is_visible(), "real mode indicator missing while seeded real tiles display")
                                check("Fictional conversation" in page.locator(".welcome-card").first.get_attribute("aria-label"), "seeded fictional real-mode tile is missing")
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
                            name = f"welcome-{mode}-{theme}-{width}x{height}"
                            if width == 390:
                                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                                page.wait_for_timeout(150)
                                geometry = page.evaluate("""() => {
                                  const start=document.querySelector('#welcome-start').getBoundingClientRect();
                                  const last=[...document.querySelectorAll('.welcome-card')].at(-1).getBoundingClientRect();
                                  return {start:{top:start.top,bottom:start.bottom},last:{top:last.top,bottom:last.bottom},innerHeight};
                                }""")
                                check(geometry["start"]["bottom"] <= 844, "fixed Start button extends beyond the mobile viewport")
                                check(geometry["last"]["bottom"] <= geometry["start"]["top"], f"last tile is obscured by fixed Start: {geometry}")
                                REPORT["measurements"][name + "-bottom-geometry"] = geometry
                            shot = EVIDENCE / f"{name}.png"
                            page.screenshot(path=str(shot), animations="disabled")
                            REPORT["evidence"].append(str(shot.relative_to(ROOT)))
                            ctx.close()
                REPORT["statuses"]["theme_viewport_screenshots"] = "Passed"

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
                    page.evaluate("sessionStorage.setItem('browser-test-start-ms', String(performance.timeOrigin + performance.now()))")
                    page.locator("#welcome-start").click()
                    page.wait_for_function("location.pathname === '/' ")
                    page.locator("#search").wait_for(state="visible")
                    elapsed = page.evaluate("Date.now() - Number(sessionStorage.getItem('browser-test-start-ms'))")
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
                first_tile = page.evaluate("document.activeElement.dataset.chatId")
                page.keyboard.press("ArrowRight")
                next_tile = page.evaluate("document.activeElement.dataset.chatId")
                check(first_tile and next_tile and first_tile != next_tile, "arrow key did not move between tiles")
                focused_box = page.locator(".welcome-card:focus-visible").bounding_box()
                check(focused_box is not None, "focused tile has no visible focus target")
                focus_shot = EVIDENCE / "welcome-keyboard-focus.png"
                page.screenshot(path=str(focus_shot), animations="disabled")
                REPORT["evidence"].append(str(focus_shot.relative_to(ROOT)))
                page.keyboard.press("Enter")
                page.locator("#reader").wait_for(state="visible")
                page.locator("#chat .reader-head h1").wait_for()
                check("Fictional conversation" in page.locator("#chat .reader-head h1").inner_text(), "Enter did not open the focused fictional chat")
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
                page.evaluate("sessionStorage.setItem('browser-test-start-ms', String(performance.timeOrigin + performance.now()))")
                page.locator("#welcome-start").click()
                page.locator("#results").wait_for(state="visible")
                page.wait_for_function("document.querySelector('#count')?.textContent.trim().length > 0")
                start_ms = page.evaluate("Date.now() - Number(sessionStorage.getItem('browser-test-start-ms'))")
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
            finally:
                if browser is not None:
                    browser.close()
    finally:
        seed_db.close()
        server.shutdown(); server.server_close(); server_thread.join(timeout=2)
    report_path = EVIDENCE / "welcome-browser-results.json"
    report_path.write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
    print(json.dumps(REPORT, indent=2))
    print(f"Evidence report: {report_path}")


if __name__ == "__main__":
    main()
