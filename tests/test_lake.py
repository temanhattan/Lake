import json, unittest
from lake.db import connect
from lake.library import (parse_import, import_chats, search, validate_card, chat_detail,
                          context_block, estimate_tokens, secret_warning, reindex_chat)
from lake.parsers.chatgpt import parse as parse_chatgpt

class LakeTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(":memory:")
    def tearDown(self): self.db.close()
    def test_chatgpt_active_branch(self):
        obj={"id":"x","title":"branch","current_node":"c","mapping":{
            "a":{"parent":None,"message":{"author":{"role":"user"},"content":{"parts":["start"]}}},
            "b":{"parent":"a","message":{"author":{"role":"assistant"},"content":{"parts":["old"]}}},
            "c":{"parent":"a","message":{"author":{"role":"assistant"},"content":{"parts":["active"]}}}}}
        chat=parse_chatgpt([obj])[0]
        self.assertEqual([m["content"] for m in chat["messages"]],["start","active"])
    def test_claude_manual_and_bad_files(self):
        c=parse_import("claude.json",json.dumps([{"uuid":"c1","chat_messages":[{"sender":"human","text":"Hi"},{"sender":"assistant","text":"Hello"}]}]))
        self.assertEqual([m["role"] for m in c[0]["messages"]],["user","assistant"])
        m=parse_import("notes.txt","User: hi\nAssistant: hello")
        self.assertEqual(len(m[0]["messages"]),2)
        self.assertEqual(parse_import("raw.txt","unmarked body")[0]["messages"][0]["content"],"unmarked body")
        with self.assertRaises(ValueError): parse_import("bad.json","{")
        manual=parse_import("manual.json",json.dumps({"title":"JSON note","messages":[{"role":"user","content":"Preserve exact words"}]}))
        self.assertEqual(manual[0]["messages"][0]["content"],"Preserve exact words")
    def test_secret_warning_is_read_only(self):
        fake="sk-"+"A"*25
        self.assertTrue(secret_warning("example key: "+fake))
        self.assertFalse(secret_warning("ordinary conversation text"))
    def test_dedup_and_updates(self):
        chat={"source":"manual","source_id":"a","title":"A","messages":[{"role":"user","content":"one"}]}
        self.assertEqual(import_chats(self.db,[chat])["added"],1)
        self.assertEqual(import_chats(self.db,[chat])["skipped"],1)
        changed={**chat,"messages":[{"role":"user","content":"two"}]}
        self.assertEqual(import_chats(self.db,[changed])["updated"],1)
    def test_fts_middle_snippet(self):
        body="first words "+"ordinary passage "*80+"heliotrope_unique_phrase"+" ending"
        report=import_chats(self.db,[{"source":"manual","title":"Long chat","messages":[{"role":"user","content":body}]}])
        row=search(self.db,"heliotrope_unique_phrase")
        self.assertEqual(len(row),1); self.assertIn("heliotrope_unique_phrase",row[0]["match_content"])
    def test_card_fields_are_searchable(self):
        import_chats(self.db,[{"source":"manual","title":"Card fields","messages":[{"role":"user","content":"ordinary text"}]}])
        cid=self.db.execute("SELECT id FROM chats").fetchone()[0]
        self.db.execute("UPDATE cards SET problem='cardonlyterm' WHERE chat_id=?",(cid,)); reindex_chat(self.db,cid)
        self.assertEqual(search(self.db,"cardonlyterm")[0]["id"],cid)
    def test_card_validation_context_limit(self):
        with self.assertRaises(ValueError): validate_card({"problem":2})
        card=validate_card({"problem":"x"*5000,"environment":"y"*5000,"solution_steps":["z"*5000],"result":"r"*5000,"caveats":["c"*5000],"suggested_tags":[]})
        self.assertEqual(len(card["suggested_tags"]),0)
        report=import_chats(self.db,[{"source":"manual","title":"long","messages":[{"role":"user","content":"text"*10000}]}])
        cid=self.db.execute("SELECT id FROM chats").fetchone()[0]
        d=chat_detail(self.db,cid); out=context_block(d,500)
        self.assertLessEqual(estimate_tokens(out),500)

if __name__=="__main__": unittest.main()
