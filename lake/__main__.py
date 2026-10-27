import json, shutil, sys
from pathlib import Path
from .config import load_config
from .db import connect
from .jobs import CardQueue
from .web import serve
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

def main():
    cfg=load_config(); db=connect(cfg.db_path)
    args=sys.argv[1:]
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
    jobs=CardQueue(db,cfg)
    for row in db.execute("SELECT chat_id FROM cards WHERE status='pending' AND edited_by_user=0"):
        jobs.enqueue(row[0])
    serve(db,cfg,jobs)

if __name__=="__main__": main()
