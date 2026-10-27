import unittest
from lake.chunking import chunk_messages
from lake.config import Config
from lake.db import connect
from lake.embeddings import EmbeddingQueue
from lake.library import import_chats

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

if __name__=="__main__": unittest.main()

if __name__=="__main__": unittest.main()
