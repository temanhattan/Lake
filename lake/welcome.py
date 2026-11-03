"""Curated, read-only data for the welcome gallery."""
from collections import OrderedDict
from threading import RLock
from .library import secret_warning

MAX_TILES = 24
_SECRET_SCAN_CACHE = OrderedDict()
_SECRET_SCAN_LOCK = RLock()
_SECRET_SCAN_CACHE_SIZE = 8192


def clear_secret_scan_cache():
    """Clear process-local scan results (also used by isolated benchmarks)."""
    with _SECRET_SCAN_LOCK:
        _SECRET_SCAN_CACHE.clear()


def invalidate_secret_scan(content_hash):
    """Forget a scan when its source transcript changes or is replaced."""
    if content_hash:
        with _SECRET_SCAN_LOCK:
            _SECRET_SCAN_CACHE.pop(content_hash, None)

SAMPLE_TILES = [
    {"id": "sample-01", "title": "A map that remembers the way", "summary": "A local trail planner keeps its place between visits.", "model": "GPT-4o", "date": "2026-10-22", "tags": ["design", "maps"], "project": "Field Notes"},
    {"id": "sample-02", "title": "The quiet cache invalidation", "summary": "A stale view was caused by a cache key that missed the locale.", "model": "Claude Sonnet", "date": "2026-10-19", "tags": ["debugging", "web"], "project": "Northstar"},
    {"id": "sample-03", "title": "One query, fewer surprises", "summary": "A smaller SQL query made the import preview easier to trust.", "model": "GPT-4.1", "date": "2026-10-17", "tags": ["sql", "architecture"], "project": "Lake"},
    {"id": "sample-04", "title": "A color that works in both skies", "summary": "The accent stays legible across paper and ink themes.", "model": "Claude Sonnet", "date": "2026-10-14", "tags": ["accessibility", "design"], "project": "Field Notes"},
    {"id": "sample-05", "title": "A small queue with a clear end", "summary": "The worker retries only the failed items and reports progress.", "model": "GPT-4o", "date": "2026-10-11", "tags": ["python", "jobs"], "project": "Northstar"},
    {"id": "sample-06", "title": "Search by the detail you recall", "summary": "Hybrid retrieval finds the fix even when the exact phrase is gone.", "model": "GPT-4.1", "date": "2026-10-08", "tags": ["search", "embeddings"], "project": "Lake"},
    {"id": "sample-07", "title": "The export that imports cleanly", "summary": "A parser accepts both the conversation list and a single transcript.", "model": "Claude Sonnet", "date": "2026-10-04", "tags": ["imports", "python"], "project": "Field Notes"},
    {"id": "sample-08", "title": "A softer edge for keyboard focus", "summary": "A visible focus ring keeps its contrast in dark mode.", "model": "GPT-4o", "date": "2026-09-29", "tags": ["accessibility", "css"], "project": "Northstar"},
    {"id": "sample-09", "title": "When the index catches up", "summary": "Background indexing no longer blocks the first search.", "model": "GPT-4.1", "date": "2026-09-25", "tags": ["performance", "search"], "project": "Lake"},
    {"id": "sample-10", "title": "A reliable little migration", "summary": "The schema upgrade can resume safely after an interrupted run.", "model": "Claude Sonnet", "date": "2026-09-20", "tags": ["sqlite", "reliability"], "project": "Field Notes"},
    {"id": "sample-11", "title": "A page with room to breathe", "summary": "The narrow layout keeps one clear action within thumb reach.", "model": "GPT-4o", "date": "2026-09-16", "tags": ["mobile", "design"], "project": "Northstar"},
    {"id": "sample-12", "title": "Keep the transcript close", "summary": "Local-only storage keeps the conversation available without a sync.", "model": "GPT-4.1", "date": "2026-09-12", "tags": ["privacy", "storage"], "project": "Lake"},
]


def _one_line(value, limit=180):
    text = " ".join((value or "").split())
    if len(text) > limit:
        return text[:limit - 1].rsplit(" ", 1)[0] + "…"
    return text


def _has_secret(db, chat_id, content_hash):
    # Scan on demand for wall eligibility, regardless of the optional import
    # warning preference. Cache only the content digest and boolean result.
    with _SECRET_SCAN_LOCK:
        if content_hash in _SECRET_SCAN_CACHE:
            result = _SECRET_SCAN_CACHE.pop(content_hash)
            _SECRET_SCAN_CACHE[content_hash] = result
            return result
    messages = db.execute("SELECT content FROM messages WHERE chat_id=?", (chat_id,))
    result = secret_warning("\n".join(row[0] for row in messages))
    with _SECRET_SCAN_LOCK:
        _SECRET_SCAN_CACHE[content_hash] = result
        while len(_SECRET_SCAN_CACHE) > _SECRET_SCAN_CACHE_SIZE:
            _SECRET_SCAN_CACHE.popitem(last=False)
    return result


def _spread(candidates, limit):
    """Keep pins/recent first, then greedily add project/tag diversity."""
    pins = [row for row in candidates if row["pinned"]]
    recent = [row for row in candidates if not row["pinned"]]
    chosen = pins[:limit]
    recent_slots = min(8, limit - len(chosen))
    chosen.extend(recent[:recent_slots])
    remaining = recent[recent_slots:]
    seen_projects = {row["project"] for row in chosen if row["project"]}
    seen_tags = {tag for row in chosen for tag in row["tags"]}
    while remaining and len(chosen) < limit:
        # Stable max() tie-breaking preserves the original recent-first order.
        best_index = max(
            range(len(remaining)),
            key=lambda i: (
                int(bool(remaining[i]["project"]) and remaining[i]["project"] not in seen_projects) * 3
                + sum(tag not in seen_tags for tag in remaining[i]["tags"]),
                -i,
            ),
        )
        row = remaining.pop(best_index)
        chosen.append(row)
        if row["project"]:
            seen_projects.add(row["project"])
        seen_tags.update(row["tags"])
    return chosen


def welcome_tiles(db, demo=False, limit=MAX_TILES):
    """Return only safe card metadata; demo and small-library paths are fictional."""
    limit = min(MAX_TILES, max(0, int(limit)))
    if limit == 0:
        return []
    if demo:
        return [dict(tile) for tile in SAMPLE_TILES[:limit]]

    rows = db.execute("""SELECT c.id,c.title,c.model_used,c.created_at,c.updated_at,c.content_hash,
        c.imported_at,c.pinned,coalesce(p.name,'') project,
        coalesce(ca.problem,'') problem,coalesce(ca.result,'') result
        FROM chats c LEFT JOIN cards ca ON ca.chat_id=c.id
        LEFT JOIN projects p ON p.id=c.project_id
        WHERE c.archived=0 AND (trim(coalesce(ca.problem,''))<>'' OR trim(coalesce(ca.result,''))<>'')
        ORDER BY c.pinned DESC, coalesce(c.created_at,c.updated_at,c.imported_at) DESC, c.id ASC""").fetchall()
    candidates = []
    for row in rows:
        if _has_secret(db, row["id"], row["content_hash"]):
            continue
        tags = [item[0] for item in db.execute(
            "SELECT t.name FROM tags t JOIN chat_tags ct ON ct.tag_id=t.id WHERE ct.chat_id=? ORDER BY t.name",
            (row["id"],),
        )]
        summary = _one_line(row["problem"] or row["result"])
        candidates.append({
            "id": row["id"], "title": row["title"], "summary": summary,
            "model": row["model_used"] or "", "date": row["created_at"] or row["updated_at"] or "",
            "tags": tags, "project": row["project"], "pinned": row["pinned"],
        })
        # Preserve the pin/recent ordering while bounding expensive scans.
        if len(candidates) >= limit:
            break
    if len(candidates) < 6:
        return [dict(tile) for tile in SAMPLE_TILES[:limit]]
    selected = _spread(candidates, limit)
    return [{key: row[key] for key in ("id", "title", "summary", "model", "date", "tags", "project")} for row in selected]
