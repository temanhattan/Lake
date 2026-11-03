import json, shutil, sys, urllib.request, urllib.error, importlib.util
from pathlib import Path
from .config import load_config
from .db import connect
from .jobs import CardQueue
from .embeddings import EmbeddingQueue
from .vector_index import create_vector_index
from .semantic_search import SemanticSearch
from .web import serve, Handler
from .library import import_chats, NOW, parse_import

def seed(db):
    chats=[]
    samples=[
      ("Fix a slow SQLite query","manual",["How do I speed up a filtered query?","Add an index on the filtered column, then inspect EXPLAIN QUERY PLAN.","The query became faster after adding the composite index."]),
      ("Python CSV cleanup","manual",["I have blank rows in a CSV.","Use csv.DictReader and skip rows where all values are blank.","That removed the empty rows without changing quoted commas."]),
      ("Vite local server","manual",["How do I bind a dev server to localhost?","Set the host to 127.0.0.1 in the server configuration.","The page is reachable only from this machine."]),
      ("Regex log parsing","manual",["Extract timestamps from logs.","Use a named capture group for the timestamp and parse it with datetime.","Malformed lines are now reported and skipped."]),
      ("Markdown export","manual",["Export a chat with code fences intact.","Join message bodies with role headings and leave code fence content untouched.","The exported file preserves the original code blocks."]),
    ]
    for title,source,lines in samples:
        chats.append({"source":source,"source_id":"seed-"+str(len(chats)+1),"title":title,"created_at":NOW(),"messages":[{"role":"user" if i%2==0 else "assistant","content":v} for i,v in enumerate(lines)]})
    return import_chats(db,chats)

def backup(db,path):
    out=Path(path); out.mkdir(parents=True,exist_ok=True)
    target=out/"lake.db"; dst=connect(str(target))
    db.backup(dst); dst.close()
    data=[]
    for chat in db.execute("SELECT * FROM chats ORDER BY created_at"):
        c=dict(chat); c["messages"]=[dict(m) for m in db.execute("SELECT role,content,created_at FROM messages WHERE chat_id=? ORDER BY idx",(c["id"],))]
        card=db.execute("SELECT * FROM cards WHERE chat_id=?",(c["id"],)).fetchone(); c["card"]=dict(card) if card else None
        c["tags"]=[r[0] for r in db.execute("SELECT t.name FROM tags t JOIN chat_tags ct ON ct.tag_id=t.id WHERE ct.chat_id=?",(c["id"],))]
        data.append(c)
        md="# "+c["title"]+"\n\n"+"\n\n".join("## "+m["role"].title()+"\n\n"+m["content"] for m in c["messages"])
        (out/(c["id"]+".md")).write_text(md,encoding="utf-8")
    export={"projects":[dict(r) for r in db.execute("SELECT * FROM projects")],"chats":data}
    (out/"chats.json").write_text(json.dumps(export,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Backup written to {out.resolve()}")

def doctor(cfg,db):
    checks=[]
    checks.append(("Python",sys.version.split()[0]+(" (OK)" if sys.version_info >= (3,11) else " (need 3.11+)")))
    checks.append(("SQLite FTS5","available" if db.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')").fetchone()[0] or db.execute("SELECT name FROM sqlite_master WHERE name='message_fts'").fetchone() else "unavailable"))
    checks.append(("NumPy", "available" if importlib.util.find_spec("numpy") else "missing"))
    checks.append(("sqlite-vec", "installed (optional)" if importlib.util.find_spec("sqlite_vec") else "not installed; NumPy fallback"))
    try:
        with urllib.request.urlopen(cfg.ollama_url.rstrip("/")+"/api/tags",timeout=3) as response: tags=json.loads(response.read()).get("models",[])
        names={m.get("name","") for m in tags}
        checks.append(("Ollama","reachable"))
        for label,model in (("Chat model",cfg.model),("Embedding model",cfg.embedding_model)):
            checks.append((label, "available" if any(n==model or n.startswith(model+":") for n in names) else f"missing ({model})"))
    except Exception as exc:checks.append(("Ollama",f"unavailable ({exc})"))
    for label,value in checks:print(f"{label}: {value}")

def main():
    args=sys.argv[1:]
    cfg=load_config()
    if args and args[0] in {"doctor","diagnose"}:
        db=connect(cfg.db_path);doctor(cfg,db);db.close();return
    db=connect(cfg.db_path)
    if args and args[0]=="backup": backup(db,args[1] if len(args)>1 else "./backups"); return
    if args and args[0]=="import-folder":
        folder=Path(args[1] if len(args)>1 else cfg.import_folder)
        total={"added":0,"updated":0,"skipped":0,"failed":[]}
        for file in folder.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in {".json",".md",".txt"}: continue
            try: report=import_chats(db,parse_import(file.name,file.read_text(encoding="utf-8-sig")))
            except Exception as exc: report={"added":0,"updated":0,"skipped":0,"failed":[{"title":file.name,"reason":str(exc)}]}
            for key in ("added","updated","skipped"): total[key]+=report[key]
            total["failed"].extend(report["failed"])
        print(json.dumps(total,ensure_ascii=False,indent=2)); return
    if "--seed" in args: print(seed(db))
    vector_index=create_vector_index(db,cfg.vector_cache_path)
    embeddings=EmbeddingQueue(db,cfg)
    embeddings.set_index(vector_index)
    Handler.embeddings=embeddings
    Handler.semantic=SemanticSearch(vector_index,embeddings,cfg)
    jobs=CardQueue(db,cfg,embeddings)
    Handler.jobs=jobs
    for row in db.execute("SELECT chat_id FROM cards WHERE status='pending' AND edited_by_user=0"):
        jobs.enqueue(row[0])
    serve(db,cfg,jobs)

if __name__=="__main__": main()
