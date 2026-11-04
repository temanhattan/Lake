import html, json, mimetypes, re, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from email.parser import BytesParser
from email.policy import default
from .library import (search, chat_detail, parse_import, import_chats, secret_warning,
                      context_block, estimate_tokens, reindex_chat, NOW)
from .welcome import welcome_tiles

STATIC=Path(__file__).parent/"static"

class Handler(BaseHTTPRequestHandler):
    db=None; config=None; jobs=None; embeddings=None; semantic=None
    def setup(self):
        super().setup()
        from .db import connect
        self.db=connect(self.config.db_path)
    def finish(self):
        try: self.db.close()
        finally: super().finish()
    def log_message(self, fmt, *args): pass
    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body,str): body=body.encode("utf-8")
        self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(body))); self.send_header("X-Content-Type-Options","nosniff"); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def _json(self, obj, status=200): self._send(status,json.dumps(obj,ensure_ascii=False,default=str),"application/json; charset=utf-8")
    def _local_origin(self, value):
        try:
            parsed=urllib.parse.urlsplit(value)
            return parsed.scheme in {"http","https"} and parsed.hostname in {"localhost","127.0.0.1"} and parsed.port in {None,self.config.port}
        except ValueError:
            return False
    def _request_security_error(self, state_changing=False):
        host=self.headers.get("Host","")
        try:
            parsed=urllib.parse.urlsplit("//"+host)
            valid_host=parsed.hostname in {"localhost","127.0.0.1"} and parsed.port in {None,self.config.port}
        except ValueError:
            valid_host=False
        if not valid_host:
            self._json({"error":"Unexpected Host header"},403)
            return True
        origin=self.headers.get("Origin")
        referer=self.headers.get("Referer")
        if origin is not None and not self._local_origin(origin):
            self._json({"error":"Cross-origin request rejected"},403)
            return True
        if referer is not None and not self._local_origin(referer):
            self._json({"error":"Cross-origin request rejected"},403)
            return True
        if state_changing and not (origin is not None or referer is not None):
            self._json({"error":"Origin or Referer required"},403)
            return True
        return False
    def _body(self):
        n=int(self.headers.get("Content-Length",0)); return self.rfile.read(min(n,500_000_000))
    def _attach_result_tags(self, rows):
        """Attach assigned tags to visible search results in one read-only query."""
        ids=[row.get("id",row.get("chat_id")) for row in rows]
        ids=[chat_id for chat_id in ids if chat_id is not None]
        by_chat={chat_id:[] for chat_id in ids}
        if ids:
            marks=",".join("?" for _ in ids)
            for row in self.db.execute(
                f"SELECT ct.chat_id,t.name FROM chat_tags ct JOIN tags t ON t.id=ct.tag_id WHERE ct.chat_id IN ({marks}) ORDER BY t.name",
                ids):
                by_chat[row["chat_id"]].append(row["name"])
        for item in rows:
            item["tags"]=by_chat.get(item.get("id",item.get("chat_id")),[])
        for item in rows:
            chat_id=item.get("id",item.get("chat_id"))
            if chat_id is None: continue
            provenance=self.db.execute("SELECT ca.generated_by,ca.generated_at,(SELECT e.model_name FROM embeddings e WHERE e.chat_id=c.id AND e.stale=0 ORDER BY e.id DESC LIMIT 1) embedding_model FROM chats c LEFT JOIN cards ca ON ca.chat_id=c.id WHERE c.id=?",(chat_id,)).fetchone()
            if provenance:
                item["card_model"]=provenance["generated_by"]
                item["card_generated_at"]=provenance["generated_at"]
                item["embedding_model"]=provenance["embedding_model"]
        return rows
    def do_GET(self):
        security_error=self._request_security_error()
        if security_error:return security_error
        u=urllib.parse.urlsplit(self.path); path=u.path; q=urllib.parse.parse_qs(u.query)
        if path in {"/","/welcome","/design-system"}:
            page=(STATIC/"index.html").read_text(encoding="utf-8")
            page=page.replace('content="width=device-width,initial-scale=1"','content="width=device-width,initial-scale=1,viewport-fit=cover"')
            # Delay loading the search app until the entry module knows whether
            # this is a welcome launch; demo mode must not fetch search results.
            page=page.replace('<script type="module" src="/static/app.js"></script>','')
            page=page.replace('<script type="module" src="/static/enhancements.js"></script>','<script type="module" src="/static/entry.js"></script>')
            return self._send(200,page,"text/html; charset=utf-8")
        if path.startswith("/static/"):
            f=STATIC/path.removeprefix("/static/")
            if not f.resolve().is_relative_to(STATIC.resolve()) or not f.is_file(): return self._send(404,b"")
            return self._send(200,f.read_bytes(),mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        if path=="/api/search":
            filters={k:q[k][0] for k in ["source","model","project","tag","from","to"] if q.get(k)}
            if not q.get("archived"): filters["archived"]=False
            for k in ("pinned","archived"):
                if q.get(k): filters[k]=q[k][0]=="1"
            query=q.get("q",[""])[0]; mode=q.get("mode",["hybrid"])[0]
            if self.semantic:
                result=self.semantic.search(self.db,query,filters,mode,100,q.get("rerank",["0"])[0]=="1")
                result["results"]=self._attach_result_tags(result.get("results",[]))
                result["sort"]=q.get("sort",["relevance"])[0]
                if result["sort"] in ("newest","oldest"):
                    result["results"].sort(key=lambda r:r.get("created_at") or "",reverse=result["sort"]=="newest")
                return self._json(result)
            rows=[dict(r) for r in search(self.db,query,filters,q.get("sort",["relevance"])[0],100)]
            return self._json({"results":self._attach_result_tags(rows),"mode":"keyword","backend":None})
        if path=="/api/welcome/tiles":
            return self._json(welcome_tiles(self.db, demo=q.get("demo",["0"])[0]=="1"))
        if path=="/api/duplicates":
            if not self.semantic:return self._json({"error":"Semantic search is not initialized"},503)
            try:threshold=float(q.get("threshold",[self.config.duplicate_similarity_threshold])[0])
            except ValueError:return self._json({"error":"Threshold must be numeric"},400)
            return self._json(self.semantic.duplicates(self.db,threshold,self.config.duplicate_scan_limit))
        if path.startswith("/api/similar/"):
            if not self.semantic:return self._json({"error":"Semantic search is not initialized"},503)
            return self._json(self.semantic.similar(self.db,path.rsplit("/",1)[-1],10))
        if path.startswith("/api/chat/"):
            d=chat_detail(self.db,path.split("/")[-1])
            if not d: return self._json({"error":"Chat not found"},404)
            feedback=self.db.execute("SELECT outcome,note,updated_at FROM solution_feedback WHERE chat_id=?",(d["chat"]["id"],)).fetchone()
            return self._json({"chat":dict(d["chat"]),"messages":[dict(x) for x in d["messages"]],"card":dict(d["card"]) if d["card"] else None,"tags":d["tags"],"feedback":dict(feedback) if feedback else None,"secret_warning":secret_warning("\n".join(x["content"] for x in d["messages"])) if self.config.secret_scan else False})
        if path.startswith("/api/export/"):
            d=chat_detail(self.db,path.split("/")[-1])
            if not d: return self._send(404,b"")
            ids=q.get("ids",[""])[0]
            if ids:
                wanted={int(v) for v in ids.split(",") if v.isdigit()}
                d["messages"]=[m for m in d["messages"] if m["id"] in wanted]
            lines=["# "+d["chat"]["title"],""]+[f"## {m['role'].title()}\n\n{m['content']}\n" for m in d["messages"]]
            return self._send(200,"\n".join(lines),"text/markdown; charset=utf-8")
        if path=="/api/projects": return self._json([dict(r) for r in self.db.execute("SELECT * FROM projects ORDER BY name")])
        if path=="/api/filters":
            return self._json({"models":[r[0] for r in self.db.execute("SELECT DISTINCT model_used FROM chats WHERE model_used IS NOT NULL ORDER BY 1")],"tags":[r[0] for r in self.db.execute("SELECT name FROM tags ORDER BY name")],"projects":[dict(r) for r in self.db.execute("SELECT id,name FROM projects ORDER BY name")]})
        if path=="/api/embedding-progress":return self._json(self.embeddings.progress() if self.embeddings else {"model":None,"total":0,"embedded":0,"pending":0,"failed":0})
        if path=="/api/card-progress":return self._json(self.jobs.progress(self.db) if self.jobs else {"active":None,"queued":[],"pending":0})
        if path.startswith("/api/context/"):
            job_id=path.rsplit("/",1)[-1]; return self._json(self.jobs.context_results.get(job_id,{"status":"missing"}))
        return self._send(404,b"")
    def do_POST(self):
        security_error=self._request_security_error(state_changing=True)
        if security_error:return security_error
        path=urllib.parse.urlsplit(self.path).path
        if path=="/api/import":
            raw=self._body(); ctype=self.headers.get("Content-Type","")
            if "multipart/form-data" in ctype:
                msg=BytesParser(policy=default).parsebytes((f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode()+raw))
                items=[]
                for part in msg.iter_parts():
                    if part.get_filename(): items.append((part.get_filename(),part.get_payload(decode=True).decode("utf-8-sig",errors="replace")))
                if not items:
                    text=next((p.get_content() for p in msg.iter_parts() if p.get_content_disposition()!="attachment"),"")
                    items=[("Pasted transcript.txt",text)]
            else:
                obj=json.loads(raw or b"{}"); items=[(obj.get("filename","Pasted transcript.txt"),obj.get("text",""))]
            total={"added":0,"updated":0,"skipped":0,"failed":[]}
            for name,text in items:
                try:
                    chats=parse_import(name,text); report=import_chats(self.db,chats)
                    for k in ("added","updated","skipped"): total[k]+=report[k]
                    total["failed"].extend(report["failed"])
                    for chat_id in report.get("queued",[]): self.jobs.enqueue(chat_id)
                    if self.embeddings:
                        for chat_id in report.get("changed",[]):self.embeddings.enqueue_chat(chat_id)
                except Exception as exc: total["failed"].append({"title":name,"reason":str(exc)})
            return self._json(total)
        if path=="/api/import-preview":
            try:
                obj=json.loads(self._body() or b"{}")
                return self._json({"secret_warning":secret_warning(obj.get("text",""))})
            except Exception:return self._json({"error":"Invalid preview request"},400)
        try: obj=json.loads(self._body() or b"{}")
        except Exception: return self._json({"error":"Invalid JSON"},400)
        if path=="/api/embeddings/retry":
            if not self.embeddings:return self._json({"error":"Semantic search is not initialized"},503)
            self.embeddings.enqueue_all();return self._json({"queued":True})
        if path.startswith("/api/chat/"):
            chat_id=path.split("/")[-1]; action=obj.get("action")
            if action in ("pin","archive","rename","delete","project","tag","mcp_exclude","feedback"):
                if action=="delete":
                    self.db.execute("DELETE FROM message_fts WHERE chat_id=?",(chat_id,))
                    self.db.execute("DELETE FROM card_fts WHERE chat_id=?",(chat_id,))
                    self.db.execute("DELETE FROM chats WHERE id=?",(chat_id,)); self.db.commit(); return self._json({"ok":True})
                column={"pin":"pinned","archive":"archived","rename":"title","project":"project_id"}.get(action)
                if column:
                    value=obj.get("value")
                    if action in ("pin","archive"): value=int(bool(value))
                    if action=="rename": value=str(value)[:300]
                    self.db.execute(f"UPDATE chats SET {column}=? WHERE id=?",(value,chat_id))
                    if action=="rename": reindex_chat(self.db,chat_id)
                if action=="tag":
                    name=str(obj.get("value","")).strip()[:80]
                    if name:
                        self.db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)",(name,)); tid=self.db.execute("SELECT id FROM tags WHERE name=?",(name,)).fetchone()[0]
                        self.db.execute("INSERT OR IGNORE INTO chat_tags(chat_id,tag_id) VALUES(?,?)",(chat_id,tid))
                if action=="feedback":
                    outcome=obj.get("value")
                    if outcome not in ("worked","failed"):return self._json({"error":"Feedback must be worked or failed"},400)
                    self.db.execute("INSERT INTO solution_feedback(chat_id,outcome,note,updated_at) VALUES(?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET outcome=excluded.outcome,note=excluded.note,updated_at=excluded.updated_at",(chat_id,outcome,str(obj.get("note",""))[:1000],NOW()))
                if action=="mcp_exclude":
                    row=self.db.execute("SELECT project_id FROM chats WHERE id=?",(chat_id,)).fetchone()
                    if row and row[0] is not None:
                        current=self.db.execute("SELECT mcp_excluded FROM projects WHERE id=?",(row[0],)).fetchone()[0]
                        self.db.execute("UPDATE projects SET mcp_excluded=? WHERE id=?",(int(not current) if "value" not in obj else int(bool(obj["value"])),row[0]))
                self.db.commit(); return self._json({"ok":True})
        if path.startswith("/api/card/"):
            chat_id=path.split("/")[-1]
            if obj.get("action")=="generate":
                self.jobs.enqueue(chat_id,bool(obj.get("confirm_overwrite"))); return self._json({"queued":True})
            if obj.get("action")=="save":
                from .library import validate_card
                try: c=validate_card(obj.get("card",{}))
                except ValueError as exc: return self._json({"error":str(exc)},400)
                self.db.execute("UPDATE cards SET problem=?,environment=?,solution_steps=?,result=?,caveats=?,suggested_tags=?,status='ready',error=NULL,edited_by_user=1 WHERE chat_id=?",
                  (c["problem"],c["environment"],json.dumps(c["solution_steps"]),c["result"],json.dumps(c["caveats"]),json.dumps(c["suggested_tags"]),chat_id))
                reindex_chat(self.db,chat_id); self.db.commit()
                if self.embeddings:self.embeddings.enqueue_chat(chat_id)
                return self._json({"ok":True})
            if obj.get("action")=="context":
                d=chat_detail(self.db,chat_id)
                if not d: return self._json({"error":"Chat not found"},404)
                if obj.get("mode") in ("full","selected"):
                    ids=[int(x) for x in obj.get("message_ids",[]) if str(x).isdigit()]
                    job_id=self.jobs.enqueue_context(chat_id,ids or None)
                    return self._json({"job_id":job_id,"status":"pending"},202)
                if obj.get("mode")=="selected" and obj.get("message_ids"):
                    wanted={int(x) for x in obj["message_ids"] if str(x).isdigit()}
                    d["messages"]=[m for m in d["messages"] if m["id"] in wanted]
                text=context_block(d,self.config.context_target_tokens); return self._json({"text":text,"tokens":estimate_tokens(text)})
        if path=="/api/project":
            name=str(obj.get("name","")).strip()
            if not name: return self._json({"error":"Project name required"},400)
            self.db.execute("INSERT OR IGNORE INTO projects(name,description) VALUES(?,?)",(name,obj.get("description",""))); self.db.commit()
            pid=self.db.execute("SELECT id FROM projects WHERE name=?",(name,)).fetchone()[0]
            return self._json({"ok":True,"id":pid})
        return self._send(404,b"")

def serve(db,config,jobs):
    Handler.db,Handler.config,Handler.jobs=db,config,jobs
    host="127.0.0.1" # Local-only binding is a privacy invariant.
    server=ThreadingHTTPServer((host,config.port),Handler)
    print(f"Lake is ready at http://{host}:{config.port}")
    server.serve_forever()
