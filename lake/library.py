"""Application-independent operations for chats, imports, search, and context."""
import hashlib, json, re, secrets, math
from datetime import datetime, timezone
from .parsers import chatgpt, claude
from .parsers.common import manual_messages

NOW = lambda: datetime.now(timezone.utc).isoformat()


def content_hash(chat):
    raw = json.dumps({"title": chat.get("title"), "messages": chat.get("messages", [])},
                     ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def import_chats(db, chats):
    report = {"added": 0, "updated": 0, "skipped": 0, "failed": [], "queued": [], "changed": []}
    for chat in chats:
        try:
            if not chat.get("messages"):
                report["skipped"] += 1; continue
            digest = content_hash(chat)
            source_id = chat.get("source_id") or None
            row = db.execute("SELECT id,content_hash FROM chats WHERE source=? AND source_id=?",
                             (chat["source"], source_id)).fetchone() if source_id else None
            if not row:
                row = db.execute("SELECT id,content_hash FROM chats WHERE content_hash=?", (digest,)).fetchone()
            now = NOW()
            if row and row["content_hash"] == digest:
                report["skipped"] += 1; continue
            if row:
                chat_id = row["id"]
                db.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
                db.execute("UPDATE chats SET title=?,model_used=?,updated_at=?,content_hash=?,imported_at=? WHERE id=?",
                           (chat.get("title", "Untitled"), chat.get("model_used"), chat.get("updated_at"), digest, now, chat_id))
                card=db.execute("SELECT edited_by_user FROM cards WHERE chat_id=?",(chat_id,)).fetchone()
                if card and not card[0]:
                    db.execute("UPDATE cards SET status='pending',error=NULL WHERE chat_id=?",(chat_id,))
                    report["queued"].append(chat_id)
                report["updated"] += 1
            else:
                chat_id = secrets.token_hex(16)
                db.execute("INSERT INTO chats(id,source,source_id,title,model_used,created_at,updated_at,imported_at,content_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                           (chat_id, chat["source"], source_id, chat.get("title", "Untitled"), chat.get("model_used"),
                            chat.get("created_at"), chat.get("updated_at"), now, digest))
                report["added"] += 1
                report["queued"].append(chat_id)
            for idx, msg in enumerate(chat["messages"]):
                role = msg.get("role", "user")
                if role not in ("user", "assistant", "system", "tool"): role = "tool"
                db.execute("INSERT INTO messages(chat_id,idx,role,content,created_at) VALUES(?,?,?,?,?)",
                           (chat_id, idx, role, msg.get("content", ""), msg.get("created_at")))
            db.execute("INSERT OR IGNORE INTO cards(chat_id,status) VALUES(?,'pending')", (chat_id,))
            reindex_chat(db, chat_id)
            db.commit()
            if chat_id not in report["changed"]:report["changed"].append(chat_id)
        except Exception as exc:
            db.rollback(); report["failed"].append({"title": chat.get("title", "Untitled"), "reason": str(exc)})
    return report


def reindex_chat(db, chat_id):
    row = db.execute("SELECT title FROM chats WHERE id=?", (chat_id,)).fetchone()
    if not row: return
    db.execute("DELETE FROM message_fts WHERE chat_id=?", (chat_id,))
    db.execute("DELETE FROM card_fts WHERE chat_id=?", (chat_id,))
    for m in db.execute("SELECT id,content FROM messages WHERE chat_id=? ORDER BY idx", (chat_id,)):
        db.execute("INSERT INTO message_fts(chat_id,message_id,title,content) VALUES(?,?,?,?)",
                   (chat_id, m["id"], row["title"], m["content"]))
    c = db.execute("SELECT * FROM cards WHERE chat_id=?", (chat_id,)).fetchone()
    if c:
        db.execute("INSERT INTO card_fts(chat_id,title,problem,environment,solution_steps,result,caveats) VALUES(?,?,?,?,?,?,?)",
                   (chat_id, row["title"], c["problem"], c["environment"], c["solution_steps"], c["result"], c["caveats"]))


def parse_import(filename, raw):
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "json":
        try: data = json.loads(raw)
        except json.JSONDecodeError as exc: raise ValueError(f"Malformed JSON: {exc}") from exc
        if isinstance(data, dict) and ("mapping" in data or "conversations" in data and data.get("format") == "chatgpt"):
            return chatgpt.parse(data)
        if isinstance(data, list) and data and isinstance(data[0], dict) and "mapping" in data[0]:
            return chatgpt.parse(data)
        if isinstance(data, dict) and data.get("conversations") and any("mapping" in x for x in data["conversations"] if isinstance(x, dict)):
            return chatgpt.parse(data)
        if isinstance(data, dict) and isinstance(data.get("messages"),list):
            msgs=[]
            for m in data["messages"]:
                if isinstance(m,dict): msgs.append({"role":m.get("role","user"),"content":m.get("content",m.get("text",""))})
            return [{"source":"manual","source_id":"","title":data.get("title","Imported transcript"),"messages":msgs}]
        return claude.parse(data)
    title = filename.rsplit(".", 1)[0] or "Imported transcript"
    return [{"source": "manual", "source_id": "", "title": title, "messages": manual_messages(raw)}]


def search(db, query="", filters=None, sort="relevance", limit=100, offset=0):
    filters = filters or {}; clauses=[]; args=[]
    if filters.get("source"): clauses.append("c.source=?"); args.append(filters["source"])
    if filters.get("model"): clauses.append("c.model_used=?"); args.append(filters["model"])
    if filters.get("project"): clauses.append("c.project_id=?"); args.append(filters["project"])
    if filters.get("pinned") is not None: clauses.append("c.pinned=?"); args.append(int(filters["pinned"]))
    if filters.get("archived") is not None: clauses.append("c.archived=?"); args.append(int(filters["archived"]))
    if filters.get("from"): clauses.append("c.created_at>=?"); args.append(filters["from"])
    if filters.get("to"): clauses.append("c.created_at<=?"); args.append(filters["to"])
    if filters.get("tag"): clauses.append("EXISTS(SELECT 1 FROM chat_tags ct JOIN tags t ON t.id=ct.tag_id WHERE ct.chat_id=c.id AND t.name=?)"); args.append(filters["tag"])
    base = " WHERE " + " AND ".join(clauses) if clauses else ""
    if query.strip():
        tokens=re.findall(r"\w+",query,flags=re.UNICODE)
        if not tokens: return []
        terms=" AND ".join('"'+token.replace('"','""')+'"' for token in tokens)
        sql = """SELECT c.*, bm25(message_fts) rank, snippet(message_fts,3,'<mark>','</mark>','…',12) snippet,
        message_fts.message_id matched_message_id,
        (SELECT content FROM messages WHERE id=CAST(message_fts.message_id AS INTEGER)) match_content,
        ca.problem, ca.result, ca.status card_status FROM message_fts JOIN chats c ON c.id=message_fts.chat_id
        LEFT JOIN cards ca ON ca.chat_id=c.id WHERE message_fts MATCH ?""" + (" AND "+" AND ".join(clauses) if clauses else "")
        order = "rank ASC" if sort == "relevance" else ("c.created_at ASC" if sort == "oldest" else "c.created_at DESC")
        # FTS5 rank helpers cannot be combined with GROUP BY. Read the ranked
        # matching message rows, then keep the best match per conversation.
        matched=db.execute(sql+f" ORDER BY {order} LIMIT ?", [terms]+args+[max(2000,(limit+offset)*20)]).fetchall()
        unique=[]; seen=set()
        for row in matched:
            if row["id"] not in seen:
                seen.add(row["id"]); unique.append(row)
        card_rows=db.execute("""SELECT c.*,bm25(card_fts) rank,
            snippet(card_fts,2,'<mark>','</mark>','…',12) snippet,
            NULL matched_message_id,(coalesce(ca.problem,'')||' '||coalesce(ca.result,'')) match_content,
            ca.problem,ca.result,ca.status card_status FROM card_fts
            JOIN chats c ON c.id=card_fts.chat_id LEFT JOIN cards ca ON ca.chat_id=c.id
            WHERE card_fts MATCH ?"""+ (" AND "+" AND ".join(clauses) if clauses else "")+
            f" ORDER BY {'rank ASC' if sort=='relevance' else ('c.created_at ASC' if sort=='oldest' else 'c.created_at DESC')} LIMIT ?",
            [terms]+args+[max(2000,(limit+offset)*20)]).fetchall()
        for row in card_rows:
            if row["id"] not in seen: seen.add(row["id"]); unique.append(row)
        return unique[offset:offset+limit]
    order = "c.created_at ASC" if sort=="oldest" else "c.created_at DESC"
    sql = "SELECT c.*, NULL rank, NULL matched_message_id, '' snippet, '' match_content, ca.problem,ca.result,ca.status card_status FROM chats c LEFT JOIN cards ca ON ca.chat_id=c.id"+base+f" ORDER BY {order} LIMIT ? OFFSET ?"
    return db.execute(sql, args+[limit,offset]).fetchall()


def chat_detail(db, chat_id):
    chat=db.execute("SELECT * FROM chats WHERE id=?",(chat_id,)).fetchone()
    if not chat: return None
    messages=db.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY idx",(chat_id,)).fetchall()
    card=db.execute("SELECT * FROM cards WHERE chat_id=?",(chat_id,)).fetchone()
    tags=db.execute("SELECT t.name FROM tags t JOIN chat_tags ct ON t.id=ct.tag_id WHERE ct.chat_id=?",(chat_id,)).fetchall()
    return {"chat":chat,"messages":messages,"card":card,"tags":[x[0] for x in tags]}


def validate_card(obj):
    if not isinstance(obj,dict): raise ValueError("Card must be an object")
    for key in ("problem","environment","result"):
        if not isinstance(obj.get(key),str): raise ValueError(f"{key} must be text")
    for key in ("solution_steps","caveats","suggested_tags"):
        if not isinstance(obj.get(key),list) or any(not isinstance(v,str) for v in obj[key]): raise ValueError(f"{key} must be a list of text")
    obj["suggested_tags"]=obj["suggested_tags"][:5]
    return obj


def secret_warning(text):
    patterns=[r"sk-[A-Za-z0-9_-]{20,}",r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]
    if any(re.search(p,text) for p in patterns): return True
    for token in re.findall(r"[A-Za-z0-9+/=_-]{24,}",text):
        freq={c:token.count(c)/len(token) for c in set(token)}
        entropy=-sum(p*math.log2(p) for p in freq.values())
        if entropy>4.3: return True
    return False


def estimate_tokens(text): return max(1, math.ceil(len(text)/4))


def context_block(detail, target=500):
    c=detail["chat"]; card=detail["card"]
    if not card or card["status"]!="ready":
        msgs=detail["messages"][-8:]
        bits=[f"Problem/context: {c['title']}"]+[f"{m['role']}: {m['content']}" for m in msgs]
    else:
        bits=[f"Problem: {card['problem']}",f"Environment: {card['environment']}",
              "What worked: "+"; ".join(json.loads(card["solution_steps"])),f"Result: {card['result']}",
              "Open issues: "+"; ".join(json.loads(card["caveats"]))]
    bits.append("Use as background context; verify before applying.")
    out="\n".join(x for x in bits if x.strip())
    cap=max(80,int(target*0.92))
    while estimate_tokens(out)>cap:
        # Trim the longest informational line while preserving section labels and instruction.
        candidates=[(len(x),i) for i,x in enumerate(bits[:-1]) if len(x)>40]
        if not candidates: break
        _,i=max(candidates); line=bits[i]; bits[i]=line[:max(40,int(len(line)*0.8))].rsplit(" ",1)[0]+"…"
        out="\n".join(x for x in bits if x.strip())
    return out
