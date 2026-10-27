"""Run the requested local FTS timing check: 5,000 chats / 100,000 messages."""
import time
from lake.db import connect
from lake.library import search

db=connect(":memory:")
db.execute("BEGIN")
rows=[]
for i in range(5000):
    cid=f"bench-{i}"; rows.append((cid,"manual",None,f"Benchmark conversation {i}",None,"2026-01-01","2026-01-01","2026-01-01","hash"+str(i)))
db.executemany("INSERT INTO chats(id,source,source_id,title,model_used,created_at,updated_at,imported_at,content_hash) VALUES(?,?,?,?,?,?,?,?,?)",rows)
for i in range(5000):
    cid=f"bench-{i}"; batch=[]
    for j in range(20):
        content=f"message number {j} with common text"+(" needle_performance_term" if i==4321 and j==10 else "")
        batch.append((cid,j,"user" if j%2==0 else "assistant",content))
    db.executemany("INSERT INTO messages(chat_id,idx,role,content) VALUES(?,?,?,?)",batch)
db.commit()
db.execute("INSERT INTO message_fts(chat_id,message_id,title,content) SELECT m.chat_id,m.id,c.title,m.content FROM messages m JOIN chats c ON c.id=m.chat_id")
db.commit()
start=time.perf_counter(); result=search(db,"needle_performance_term"); elapsed=(time.perf_counter()-start)*1000
print(f"5,000 chats / 100,000 messages: {elapsed:.1f} ms, hits={len(result)}")
