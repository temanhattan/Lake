import unittest
import tempfile
from pathlib import Path
from lake.chunking import chunk_messages
from lake.config import Config
from lake.db import connect
from lake.embeddings import EmbeddingQueue
from lake.library import import_chats
from lake.vector_index import NumpyMemmapIndex, create_vector_index
from lake.semantic_search import rrf_merge

class ChunkerTests(unittest.TestCase):
    def test_tiny_chat_and_user_reply_group(self):
        messages=[{"idx":0,"role":"user","content":"tiny question"},{"idx":1,"role":"assistant","content":"tiny answer"}]
        chunks=chunk_messages(messages)
        self.assertEqual(len(chunks),1)
        self.assertEqual((chunks[0]["message_start_idx"],chunks[0]["message_end_idx"]),(0,1))
    def test_small_code_block_stays_whole(self):
        code="```python\nprint('safe')\n```"
        messages=[{"idx":0,"role":"user","content":"Please explain this."},{"idx":1,"role":"assistant","content":code}]
        chunk=chunk_messages(messages,max_tokens=100)[0]
        self.assertIn(code,chunk["text"])
    def test_long_message_splits_with_overlap_and_code_fences(self):
        prose="word "*1200
        messages=[{"idx":0,"role":"user","content":prose}]
        chunks=chunk_messages(messages,max_tokens=80,overlap_tokens=12)
        self.assertGreater(len(chunks),2)
        self.assertTrue(all(c["message_start_idx"]==0 for c in chunks))
        self.assertTrue(any(set(c["content_hash"])!={"0"} for c in chunks))
        code="```python\n"+"\n".join(f"print({i})" for i in range(120))+"\n```"
        coded=chunk_messages([{"idx":4,"role":"assistant","content":code}],max_tokens=80,overlap_tokens=8)
        self.assertGreater(len(coded),1)
        self.assertTrue(all(c["text"].count("```")==2 for c in coded))

class EmbeddingQueueTests(unittest.TestCase):
    def setUp(self): self.db=connect(":memory:")
    def tearDown(self): self.db.close()
    def add_chat(self,content):
        import_chats(self.db,[{"source":"manual","title":"Embedding test","messages":[{"role":"user","content":content}]}])
        return self.db.execute("SELECT id FROM chats").fetchone()[0]
    def config(self,model="nomic-embed-text"):
        return Config(db_path=":memory:",embedding_model=model,embedding_chunk_tokens=80,embedding_overlap_tokens=10)
    def test_model_change_marks_vectors_stale_and_queues_new_model(self):
        cid=self.add_chat("A problem statement")
        self.db.execute("INSERT INTO embeddings(chat_id,kind,model_name,dim,vector,content_hash,created_at,stale) VALUES(?,'card','old-model',2,?,?, 'now',0)",(cid,b'12345678','old-hash')); self.db.commit()
        queue=EmbeddingQueue(self.db,self.config("new-model"),start_worker=False,schedule=False); queue.enqueue_all()
        self.assertEqual(self.db.execute("SELECT stale FROM embeddings").fetchone()[0],1)
        job=self.db.execute("SELECT model_name,status FROM embedding_jobs WHERE chat_id=?",(cid,)).fetchone()
        self.assertEqual((job["model_name"],job["status"]),("new-model","pending"))
    def test_failed_job_resumes_and_reuses_completed_chunk(self):
        cid=self.add_chat("start "+"details and observations "*180)
        calls=[]; failed=[False]
        def fake_embed(texts):
            calls.extend(texts)
            if len(calls)>=2 and not failed[0]: failed[0]=True; raise RuntimeError("simulated interruption")
            return [[1.0,0.0,0.0] for _ in texts]
        queue=EmbeddingQueue(self.db,self.config(),embedder=fake_embed,start_worker=False,schedule=False); queue.batch_size=1
        queue.enqueue_chat(cid); queue.run_once()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM embeddings WHERE stale=0").fetchone()[0],1)
        queue.enqueue_chat(cid); queue.run_once()
        self.assertEqual(self.db.execute("SELECT status FROM embedding_jobs WHERE chat_id=?",(cid,)).fetchone()[0],"ready")
        self.assertEqual(calls.count(calls[0]),1)

class VectorIndexTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(":memory:");self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.index=NumpyMemmapIndex(self.temp.name);self.addCleanup(self.cleanup)
    def cleanup(self):
        self.index.invalidate();self.db.close();self.temp.cleanup()
    def add_vector(self,title,vector,model="nomic-embed-text",kind="chunk"):
        import_chats(self.db,[{"source":"manual","title":title,"messages":[{"role":"user","content":title}]}])
        cid=self.db.execute("SELECT id FROM chats WHERE title=?",(title,)).fetchone()[0]
        import struct,hashlib
        blob=struct.pack("<"+"f"*len(vector),*vector)
        self.db.execute("INSERT INTO embeddings(chat_id,message_start_idx,message_end_idx,kind,model_name,dim,vector,content_hash,created_at) VALUES(?,0,0,?,?,?, ?,?,'2026-01-01')",
          (cid,kind,model,len(vector),blob,hashlib.sha256(title.encode()).hexdigest()));self.db.commit();return cid
    def test_memmap_cosine_search_and_model_isolation(self):
        first=self.add_vector("close",[1,0,0]);self.add_vector("far",[0,1,0]);self.add_vector("other model",[1,0,0],"different")
        hits=self.index.search(self.db,[.98,.02,0],"nomic-embed-text",{},10)
        self.assertEqual(hits[0]["chat_id"],first)
        self.assertEqual(len(hits),2)
        self.db.execute("UPDATE embeddings SET stale=1 WHERE model_name='nomic-embed-text' AND chat_id=?",(first,));self.db.commit();self.index.invalidate()
        hits=self.index.search(self.db,[1,0,0],"nomic-embed-text",{},10)
        self.assertEqual(len(hits),1)
        self.assertNotEqual(hits[0]["chat_id"],first)
    def test_vector_index_factory_selects_available_backend(self):
        index=create_vector_index(self.db,self.temp.name)
        self.assertIn(index.name,("sqlite-vec","numpy-memmap"))
        if index.name=="sqlite-vec":index.invalidate()

class HybridTests(unittest.TestCase):
    def test_rrf_combines_ranks_and_card_hit_boosts(self):
        merged=rrf_merge([{"id":"keyword-only","title":"Keyword"},{"id":"both","title":"Both"}],
          [{"chat_id":"both","score":0.8,"card_hit":True,"kind":"chunk"},{"chat_id":"semantic-only","score":0.9,"kind":"card"}],k=60)
        self.assertEqual(merged[0]["chat_id"],"both")
        self.assertTrue(merged[0]["card_hit"])
        self.assertEqual(merged[0]["keyword_rank"],2)
        self.assertEqual(merged[0]["semantic_rank"],1)

if __name__=="__main__": unittest.main()

if __name__=="__main__": unittest.main()

if __name__=="__main__": unittest.main()
