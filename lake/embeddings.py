"""Durable, resumable Ollama embedding jobs."""
import array
import hashlib
import json
import math
import queue
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .chunking import chunk_messages


def now(): return datetime.now(timezone.utc).isoformat()


def content_digest(messages, card=None):
    payload={"messages":[[m.get("idx"),m.get("role"),m.get("content")] for m in messages],
             "card":card if card else None}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()).hexdigest()


def encode_vector(values):
    values=[float(x) for x in values]
    if not values or any(not math.isfinite(x) for x in values): raise ValueError("Embedding vector is empty or non-finite")
    buf=array.array("f",values)
    if buf.itemsize!=4: raise RuntimeError("This Python build does not provide float32 arrays")
    if __import__("sys").byteorder!="little": buf.byteswap()
    return len(values),buf.tobytes()


def ollama_embed(texts,model,url):
    if not texts: return []
    endpoint=url.rstrip("/")+"/api/embed"
    body=json.dumps({"model":model,"input":texts}).encode("utf-8")
    req=urllib.request.Request(endpoint,body,{"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=240) as response: result=json.loads(response.read())
        vectors=result.get("embeddings")
        if vectors is None and result.get("embedding") is not None: vectors=[result["embedding"]]
        if not isinstance(vectors,list) or len(vectors)!=len(texts): raise ValueError("Ollama returned an unexpected embedding count")
        return vectors
    except urllib.error.HTTPError as exc:
        if exc.code!=404: raise
    # Compatibility path for older Ollama versions that predate /api/embed.
    vectors=[]
    for text in texts:
        req=urllib.request.Request(url.rstrip("/")+"/api/embeddings",json.dumps({"model":model,"prompt":text}).encode(),{"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=240) as response: vectors.append(json.loads(response.read())["embedding"])
    return vectors


class EmbeddingQueue:
    """SQLite-backed queue; jobs and vectors survive restarts and retries."""
    def __init__(self,db,config,embedder=None,start_worker=True,schedule=True):
        self.db=db; self.config=config; self.embedder=embedder or (lambda texts:ollama_embed(texts,config.embedding_model,config.ollama_url))
        self.batch_size=16; self.wakeup=threading.Event(); self.stop_event=threading.Event()
        self.index=None
        if schedule: self.enqueue_all()
        if start_worker: threading.Thread(target=self._worker,daemon=True,name="lake-embeddings").start()

    def set_index(self,index): self.index=index

    def _source(self,db,chat_id):
        messages=[dict(row) for row in db.execute("SELECT idx,role,content FROM messages WHERE chat_id=? ORDER BY idx",(chat_id,))]
        card=db.execute("SELECT problem,result,status FROM cards WHERE chat_id=?",(chat_id,)).fetchone()
        card_data={"problem":card["problem"],"result":card["result"]} if card and card["status"]=="ready" else None
        return messages,card_data,content_digest(messages,card_data)

    def enqueue_chat(self,chat_id):
        model=self.config.embedding_model
        messages,card,digest=self._source(self.db,chat_id)
        old=self.db.execute("SELECT content_hash,status FROM embedding_jobs WHERE chat_id=? AND model_name=?",(chat_id,model)).fetchone()
        if old and old["content_hash"]==digest and old["status"]=="ready": return False
        self.db.execute("INSERT INTO embedding_jobs(chat_id,model_name,content_hash,status,error,updated_at) VALUES(?,?,?,'pending',NULL,?) "
          "ON CONFLICT(chat_id,model_name) DO UPDATE SET content_hash=excluded.content_hash,status='pending',error=NULL,updated_at=excluded.updated_at",
          (chat_id,model,digest,now()))
        self.db.commit(); self.wakeup.set(); return True

    def enqueue_all(self):
        model=self.config.embedding_model
        self.db.execute("UPDATE embeddings SET stale=1 WHERE model_name<>?",(model,)); self.db.commit()
        self.db.execute("UPDATE embedding_jobs SET status='failed',error='Embedding model changed',updated_at=? WHERE model_name<>? AND status IN ('pending','running')",(now(),model)); self.db.commit()
        for row in self.db.execute("SELECT id FROM chats ORDER BY id").fetchall(): self.enqueue_chat(row[0])

    def progress(self):
        model=self.config.embedding_model
        row=self.db.execute("SELECT COUNT(*) total,SUM(status='failed') failed,SUM(status IN ('pending','running')) pending FROM embedding_jobs WHERE model_name=?",(model,)).fetchone()
        # A job's ready status is authoritative; this separate count is also
        # useful if a transcript changed while a progress request was in flight.
        return {"model":model,"total":row["total"] or 0,"embedded":self.db.execute("SELECT COUNT(*) FROM embedding_jobs WHERE model_name=? AND status='ready'",(model,)).fetchone()[0],
                "failed":row["failed"] or 0,"pending":row["pending"] or 0}

    def _worker(self):
        from .db import connect
        db=connect(self.config.db_path)
        while not self.stop_event.is_set():
            if not self.run_once(db):
                self.wakeup.wait(1.0); self.wakeup.clear()

    def run_once(self,db=None):
        db=db or self.db
        job=db.execute("SELECT * FROM embedding_jobs WHERE model_name=? AND status='pending' ORDER BY updated_at LIMIT 1",(self.config.embedding_model,)).fetchone()
        if not job: return False
        chat_id,model,digest=job["chat_id"],job["model_name"],job["content_hash"]
        db.execute("UPDATE embedding_jobs SET status='running',error=NULL,updated_at=? WHERE chat_id=? AND model_name=?",(now(),chat_id,model)); db.commit()
        try:
            self._embed_chat(db,chat_id,model,digest)
            db.execute("UPDATE embedding_jobs SET status='ready',error=NULL,updated_at=? WHERE chat_id=? AND model_name=?",(now(),chat_id,model))
        except Exception as exc:
            _,_,latest_hash=self._source(db,chat_id)
            if latest_hash!=digest:
                db.execute("UPDATE embedding_jobs SET content_hash=?,status='pending',error=NULL,updated_at=? WHERE chat_id=? AND model_name=?",(latest_hash,now(),chat_id,model))
            else:
                db.execute("UPDATE embedding_jobs SET status='failed',error=?,updated_at=? WHERE chat_id=? AND model_name=?",(str(exc),now(),chat_id,model))
        db.commit()
        return True

    def _embed_chat(self,db,chat_id,model,job_hash):
        messages,card,digest=self._source(db,chat_id)
        if digest!=job_hash: raise RuntimeError("Chat changed while it was being embedded; it will be queued again")
        chunks=chunk_messages(messages,self.config.embedding_chunk_tokens,self.config.embedding_overlap_tokens)
        db.execute("UPDATE embeddings SET stale=1 WHERE chat_id=? AND model_name=?",(chat_id,model)); db.commit()
        work=[]
        for chunk in chunks:
            row=db.execute("SELECT id FROM embeddings WHERE chat_id=? AND message_start_idx=? AND message_end_idx=? AND kind='chunk' AND model_name=? AND content_hash=?",
              (chat_id,chunk["message_start_idx"],chunk["message_end_idx"],model,chunk["content_hash"])).fetchone()
            if row:
                db.execute("UPDATE embeddings SET stale=0 WHERE id=?",(row[0],)); continue
            work.append({**chunk,"kind":"chunk"})
        card_text=(card["problem"]+"\n\n"+card["result"]).strip() if card else ""
        if card_text:
            card_hash=hashlib.sha256(card_text.encode("utf-8")).hexdigest()
            row=db.execute("SELECT id FROM embeddings WHERE chat_id=? AND kind='card' AND model_name=? AND content_hash=?",(chat_id,model,card_hash)).fetchone()
            if row: db.execute("UPDATE embeddings SET stale=0 WHERE id=?",(row[0],))
            else: work.append({"message_start_idx":-1,"message_end_idx":-1,"kind":"card","text":card_text,"content_hash":card_hash})
        db.commit()
        for offset in range(0,len(work),self.batch_size):
            batch=work[offset:offset+self.batch_size]
            vectors=self.embedder([item["text"] for item in batch])
            if len(vectors)!=len(batch): raise ValueError("Embedding provider returned the wrong number of vectors")
            for item,vector in zip(batch,vectors):
                dim,blob=encode_vector(vector)
                db.execute("INSERT INTO embeddings(chat_id,message_start_idx,message_end_idx,kind,model_name,dim,vector,content_hash,created_at,stale) VALUES(?,?,?,?,?,?,?,?,?,0) "
                  "ON CONFLICT(chat_id,message_start_idx,message_end_idx,kind,model_name,content_hash) DO UPDATE SET dim=excluded.dim,vector=excluded.vector,created_at=excluded.created_at,stale=0",
                  (chat_id,item["message_start_idx"],item["message_end_idx"],item["kind"],model,dim,blob,item["content_hash"],now()))
            db.commit()
        if self.index: self.index.invalidate()
