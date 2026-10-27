"""Warmed NumPy memmap query benchmark at 100k vectors (default 768 dims)."""
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np

from lake.db import connect
from lake.vector_index import NumpyMemmapIndex

COUNT=100_000
DIM=768
MODEL="benchmark-768"

with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
    root=Path(folder);db=connect(str(root/"bench.db"));index=NumpyMemmapIndex(root/"index")
    chats=[]
    for i in range(COUNT):
        cid=f"bench-{i:06d}"
        chats.append((cid,"manual",cid,f"Benchmark chat {i}",None,"2026-01-01","2026-01-01","2026-01-01","hash"+str(i)))
    db.executemany("INSERT INTO chats(id,source,source_id,title,model_used,created_at,updated_at,imported_at,content_hash) VALUES(?,?,?,?,?,?,?,?,?)",chats)
    rng=np.random.default_rng(20261027)
    for start in range(0,COUNT,1000):
        stop=min(start+1000,COUNT);vectors=rng.standard_normal((stop-start,DIM),dtype=np.float32)
        batch=[]
        for j,vector in enumerate(vectors,start):
            batch.append((f"bench-{j:06d}",0,0,"chunk",MODEL,DIM,vector.astype("<f4",copy=False).tobytes(),f"hash-{j}","2026-01-01"))
        db.executemany("INSERT INTO embeddings(chat_id,message_start_idx,message_end_idx,kind,model_name,dim,vector,content_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)",batch)
        db.commit()
    query=rng.standard_normal(DIM,dtype=np.float32)
    warm=time.perf_counter();index.search(db,query,MODEL,{},20);build_ms=(time.perf_counter()-warm)*1000
    index._ensure(db,MODEL)
    start=time.perf_counter();scores=index.matrix @ (query/np.linalg.norm(query));dot_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();count=min(20,int(np.isfinite(scores).sum()));candidates=np.argpartition(scores,-count)[-count:];candidates=candidates[np.argsort(scores[candidates])[::-1]];topk_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();index._ensure(db,MODEL);ensure_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();finite=int(np.isfinite(scores).sum());finite_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();probe=index.search(db,query,MODEL,{},20);full_probe_ms=(time.perf_counter()-start)*1000
    timings={}
    for label,filters in (("unfiltered",{}),("default-archive-filter",{"archived":False})):
        index.search(db,query,MODEL,filters,20)
        samples=[]
        for _ in range(10):
            start=time.perf_counter();index.search(db,query,MODEL,filters,20);samples.append((time.perf_counter()-start)*1000)
        timings[label]=(statistics.median(samples),sorted(samples)[int(.95*(len(samples)-1))])
    p95=max(v[1] for v in timings.values())
    print(f"NumPy memmap | {COUNT:,} vectors × {DIM} dims | index warm: {build_ms:.1f} ms | dot: {dot_ms:.1f} ms | ensure: {ensure_ms:.1f} ms | unfiltered p50/p95: {timings['unfiltered'][0]:.1f}/{timings['unfiltered'][1]:.1f} ms | archive-filter p50/p95: {timings['default-archive-filter'][0]:.1f}/{timings['default-archive-filter'][1]:.1f} ms")
    index.invalidate();db.close()
    if p95>=300:raise SystemExit("Vector query exceeded the 300 ms target")
