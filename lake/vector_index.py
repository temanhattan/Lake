"""VectorIndex abstraction with sqlite-vec preference and a NumPy memmap fallback."""
import hashlib
import json
import os
import threading
from pathlib import Path

import numpy as np

from .embeddings import encode_vector


def vector_signature(db,model):
    row=db.execute("SELECT COUNT(*) n,COALESCE(MAX(id),0) mx,COALESCE(SUM(id),0) sm,COALESCE(MAX(created_at),'') ts FROM embeddings WHERE model_name=? AND stale=0",(model,)).fetchone()
    dims=[r[0] for r in db.execute("SELECT DISTINCT dim FROM embeddings WHERE model_name=? AND stale=0 ORDER BY dim",(model,))]
    return f"{row['n']}:{row['mx']}:{row['sm']}:{row['ts']}:{','.join(map(str,dims))}",dims


def allowed_chat_ids(db,filters):
    clauses=[];args=[]
    for key,col in (("source","source"),("model","model_used"),("project","project_id"),("pinned","pinned"),("archived","archived"),("from","created_at"),("to","created_at")):
        if filters.get(key) is not None:
            op="<=" if key=="to" else (">=" if key=="from" else "=")
            clauses.append(f"c.{col}{op}?"); value=int(filters[key]) if key in ("pinned","archived") else filters[key]; args.append(value)
    if filters.get("tag"):
        clauses.append("EXISTS(SELECT 1 FROM chat_tags ct JOIN tags t ON t.id=ct.tag_id WHERE ct.chat_id=c.id AND t.name=?)");args.append(filters["tag"])
    if filters.get("_allowed_project_ids") is not None:
        ids=sorted(filters["_allowed_project_ids"])
        if ids:
            clauses.append("c.project_id IN ("+",".join("?" for _ in ids)+")");args.extend(ids)
        else: clauses.append("0")
    rows=db.execute("SELECT c.id FROM chats c"+(" WHERE "+" AND ".join(clauses) if clauses else ""),args)
    return {r[0] for r in rows}


class VectorIndex:
    name="abstract"
    def invalidate(self): pass
    def search(self,db,query_vector,model_name,filters=None,limit=200): raise NotImplementedError


class NumpyMemmapIndex(VectorIndex):
    name="numpy-memmap"
    def __init__(self,cache_path):
        self.cache=Path(cache_path); self.cache.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.signature=None;self.model=None;self.matrix=None;self.codes=None;self.ids=None;self.starts=None;self.ends=None;self.kinds=None;self.chat_ids=[];self.code_by_chat={}
    def invalidate(self):
        with self.lock:
            self._close_maps();self.signature=None
    def _close_maps(self):
        for name in ("matrix","codes","ids","starts","ends","kinds"):
            value=getattr(self,name,None)
            if value is not None and getattr(value,"_mmap",None) is not None:
                value._mmap.close()
            setattr(self,name,None)
    def _paths(self,model):
        key=hashlib.sha256(model.encode()).hexdigest()[:18]
        base=self.cache/('vectors-'+key)
        return {name:Path(str(base)+suffix) for name,suffix in (("meta",".json"),("matrix",".f32"),("ids",".ids.i64"),("codes",".codes.i32"),("starts",".starts.i32"),("ends",".ends.i32"),("kinds",".u8"))}
    def _ensure(self,db,model):
        signature,dims=vector_signature(db,model)
        if len(dims)>1: raise ValueError(f"Model {model} has mixed vector dimensions: {dims}")
        if not dims:return None
        dim=dims[0];paths=self._paths(model)
        if self.signature==signature and self.model==model and self.matrix is not None:return dim
        with self.lock:
            if self.signature==signature and self.model==model and self.matrix is not None:return dim
            meta=None
            try: meta=json.loads(paths["meta"].read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError): pass
            if meta and meta.get("signature")==signature and meta.get("dim")==dim and all(paths[k].exists() for k in ("matrix","ids","codes","starts","ends","kinds")):
                n=meta["count"]
                if n:
                    self.matrix=np.memmap(paths["matrix"],dtype="<f4",mode="r",shape=(n,dim));self.ids=np.memmap(paths["ids"],dtype="<i8",mode="r",shape=(n,));self.codes=np.memmap(paths["codes"],dtype="<i4",mode="r",shape=(n,));self.starts=np.memmap(paths["starts"],dtype="<i4",mode="r",shape=(n,));self.ends=np.memmap(paths["ends"],dtype="<i4",mode="r",shape=(n,));self.kinds=np.memmap(paths["kinds"],dtype="u1",mode="r",shape=(n,))
                else:self._close_maps()
                self.chat_ids=meta["chat_ids"]
            else:
                self._close_maps()
                rows=db.execute("SELECT id,chat_id,message_start_idx,message_end_idx,kind,dim,vector FROM embeddings WHERE model_name=? AND stale=0 ORDER BY id",(model,)).fetchall();n=len(rows)
                temps={k:Path(str(paths[k])+'.tmp') for k in ("matrix","ids","codes","starts","ends","kinds")}
                if n:
                    mats=np.memmap(temps["matrix"],dtype="<f4",mode="w+",shape=(n,dim));ids=np.memmap(temps["ids"],dtype="<i8",mode="w+",shape=(n,));codes=np.memmap(temps["codes"],dtype="<i4",mode="w+",shape=(n,));starts=np.memmap(temps["starts"],dtype="<i4",mode="w+",shape=(n,));ends=np.memmap(temps["ends"],dtype="<i4",mode="w+",shape=(n,));kinds=np.memmap(temps["kinds"],dtype="u1",mode="w+",shape=(n,))
                    chats=[];code_map={}
                    for i,row in enumerate(rows):
                        if row["dim"]!=dim: raise ValueError("Embedding dimension changed within the active model")
                        vec=np.frombuffer(row["vector"],dtype="<f4")
                        if len(vec)!=dim: raise ValueError("Stored embedding has an invalid vector size")
                        norm=float(np.linalg.norm(vec));mats[i]=vec/norm if norm else vec
                        ids[i]=row["id"]
                        if row["chat_id"] not in code_map: code_map[row["chat_id"]]=len(chats);chats.append(row["chat_id"])
                        codes[i]=code_map[row["chat_id"]];starts[i]=row["message_start_idx"];ends[i]=row["message_end_idx"];kinds[i]=1 if row["kind"]=="card" else 0
                    maps=(mats,ids,codes,starts,ends,kinds)
                    for mapped in maps:mapped.flush()
                    del maps,mapped,mats,ids,codes,starts,ends,kinds
                    for key,tmp in temps.items():os.replace(tmp,paths[key])
                else: chats=[]
                meta={"signature":signature,"dim":dim,"count":n,"chat_ids":chats}
                temp_meta=Path(str(paths["meta"])+'.tmp');temp_meta.write_text(json.dumps(meta,separators=(",",":")),encoding="utf-8");os.replace(temp_meta,paths["meta"])
                self.matrix=np.memmap(paths["matrix"],dtype="<f4",mode="r",shape=(n,dim)) if n else None
                self.ids=np.memmap(paths["ids"],dtype="<i8",mode="r",shape=(n,)) if n else None
                self.codes=np.memmap(paths["codes"],dtype="<i4",mode="r",shape=(n,)) if n else None
                self.starts=np.memmap(paths["starts"],dtype="<i4",mode="r",shape=(n,)) if n else None
                self.ends=np.memmap(paths["ends"],dtype="<i4",mode="r",shape=(n,)) if n else None
                self.kinds=np.memmap(paths["kinds"],dtype="u1",mode="r",shape=(n,)) if n else None
                self.chat_ids=chats
            self.code_by_chat={chat:i for i,chat in enumerate(self.chat_ids)};self.signature=signature;self.model=model
        return dim
    def search(self,db,query_vector,model_name,filters=None,limit=200):
        with self.lock:return self._search(db,query_vector,model_name,filters,limit)
    def _search(self,db,query_vector,model_name,filters=None,limit=200):
        filters=filters or {}
        dim=self._ensure(db,model_name)
        if dim is None or self.matrix is None:return []
        q=np.asarray(query_vector,dtype=np.float32)
        if q.ndim!=1 or len(q)!=dim:raise ValueError(f"Query vector dimension {len(q)} does not match active model dimension {dim}")
        norm=float(np.linalg.norm(q))
        if not norm:return []
        scores=self.matrix @ (q/norm)
        allowed=allowed_chat_ids(db,filters) if filters else None
        if filters:
            valid_codes=np.fromiter((self.code_by_chat[c] for c in allowed if c in self.code_by_chat),dtype=np.int32)
            if not len(valid_codes):return []
            scores[~np.isin(self.codes,valid_codes)]=-np.inf
        count=min(int(limit),int(np.isfinite(scores).sum()))
        if count<=0:return []
        candidates=np.argpartition(scores,-count)[-count:]
        candidates=candidates[np.argsort(scores[candidates])[::-1]]
        hits=[]
        for i in candidates:
            hits.append({"embedding_id":int(self.ids[i]),"chat_id":self.chat_ids[int(self.codes[i])],"kind":"card" if self.kinds[i] else "chunk","message_start_idx":int(self.starts[i]),"message_end_idx":int(self.ends[i]),"score":float(scores[i])})
        return hits


class SQLiteVecIndex(VectorIndex):
    """sqlite-vec adapter. Filtered searches use the exact NumPy path."""
    name="sqlite-vec"
    def __init__(self,cache_path):self.fallback=NumpyMemmapIndex(cache_path);self.cache=Path(cache_path);self.cache.mkdir(parents=True,exist_ok=True)
    def invalidate(self):self.fallback.invalidate()
    def search(self,db,query_vector,model_name,filters=None,limit=200):
        try:
            import sqlite_vec
            sqlite_vec.load(db)
            signature,dims=vector_signature(db,model_name)
            if not dims:return []
            if len(dims)!=1:raise ValueError("Active vectors have mixed dimensions")
            dim=dims[0];table=f"lake_semantic_vec_{dim}"
            db.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING vec0(model_name TEXT PARTITION KEY, embedding FLOAT[{dim}] distance_metric=cosine)")
            db.execute("CREATE TABLE IF NOT EXISTS vector_sync_state(model_name TEXT NOT NULL,dim INTEGER NOT NULL,signature TEXT NOT NULL,PRIMARY KEY(model_name,dim))")
            state=db.execute("SELECT signature FROM vector_sync_state WHERE model_name=? AND dim=?",(model_name,dim)).fetchone()
            if not state or state[0]!=signature:
                db.execute(f"DELETE FROM {table} WHERE model_name=?",(model_name,))
                rows=db.execute("SELECT id,vector FROM embeddings WHERE model_name=? AND stale=0",(model_name,))
                db.executemany(f"INSERT INTO {table}(rowid,model_name,embedding) VALUES(?,?,?)",((r["id"],model_name,r["vector"]) for r in rows))
                db.execute("INSERT INTO vector_sync_state(model_name,dim,signature) VALUES(?,?,?) ON CONFLICT(model_name,dim) DO UPDATE SET signature=excluded.signature",(model_name,dim,signature));db.commit()
            qdim,qblob=encode_vector(query_vector)
            if qdim!=dim:raise ValueError("Query embedding dimensions do not match stored vectors")
            total=db.execute("SELECT COUNT(*) FROM embeddings WHERE model_name=? AND stale=0",(model_name,)).fetchone()[0]
            allowed=allowed_chat_ids(db,filters or {}) if filters else None
            k=min(total,max(500,int(limit)*10));hits=[]
            while k:
                neighbors=db.execute(f"SELECT rowid,distance FROM {table} WHERE embedding MATCH ? AND k=? AND model_name=? ORDER BY distance",(qblob,k,model_name)).fetchall()
                ids=[r["rowid"] for r in neighbors]
                if not ids:break
                marks=",".join("?" for _ in ids)
                vectors=db.execute(f"SELECT id,chat_id,kind,message_start_idx,message_end_idx,text_content FROM embeddings WHERE model_name=? AND stale=0 AND id IN ({marks})",[model_name]+ids).fetchall()
                distance_by_id={r["rowid"]:r["distance"] for r in neighbors}
                hits=[{"embedding_id":r["id"],"chat_id":r["chat_id"],"kind":r["kind"],"message_start_idx":r["message_start_idx"],"message_end_idx":r["message_end_idx"],"text_content":r["text_content"],"score":1.0-distance_by_id[r["id"]]} for r in vectors if allowed is None or r["chat_id"] in allowed]
                hits.sort(key=lambda x:x["score"],reverse=True)
                if len(hits)>=limit or k>=total:break
                k=min(total,k*2)
            return hits[:limit]
        except Exception:
            # sqlite-vec is optional and platform-dependent; keep functionality
            # correct and local if loading the extension or its query fails.
            return self.fallback.search(db,query_vector,model_name,filters,limit)


def create_vector_index(db,cache_path,prefer_sqlite_vec=True):
    if prefer_sqlite_vec:
        try:
            import sqlite_vec  # noqa: F401
            if hasattr(db,"enable_load_extension"):return SQLiteVecIndex(cache_path)
        except Exception:pass
    return NumpyMemmapIndex(cache_path)
