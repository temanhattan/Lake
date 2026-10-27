import unittest
from lake.chunking import chunk_messages

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

if __name__=="__main__": unittest.main()
