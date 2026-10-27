import io, json, unittest
from email.message import Message
from lake.config import Config
from lake.db import connect
from lake.web import Handler

class HttpHandlerTests(unittest.TestCase):
    def setUp(self):
        self.h=object.__new__(Handler); self.h.db=connect(":memory:"); self.h.config=Config()
        self.h.jobs=type("Jobs",(),{"enqueue":lambda *a,**k:None,"enqueue_context":lambda *a,**k:"job","context_results":{}})()
        self.h.headers=Message(); self.h.wfile=io.BytesIO(); self.h.rfile=io.BytesIO()
        self.h.send_response=lambda *a:None; self.h.send_header=lambda *a:None; self.h.end_headers=lambda *a:None
    def tearDown(self): self.h.db.close()
    def response(self): return json.loads(self.h.wfile.getvalue())
    def test_page_import_search_and_reader(self):
        self.h.path="/"; self.h.do_GET(); self.assertIn(b"Lake",self.h.wfile.getvalue())
        self.h.headers["Content-Type"]="application/json"; self.h.wfile=io.BytesIO()
        body=json.dumps({"filename":"Pasted transcript.txt","text":"User: keep a heliotrope phrase\nAssistant: saved"}).encode()
        self.h.rfile=io.BytesIO(body); self.h.headers["Content-Length"]=str(len(body)); self.h.path="/api/import"; self.h.do_POST()
        self.assertEqual(self.response()["added"],1)
        self.h.wfile=io.BytesIO(); self.h.path="/api/search?q=heliotrope"; self.h.do_GET(); rows=self.response()
        self.assertEqual(len(rows),1)
        self.h.wfile=io.BytesIO(); self.h.path="/api/chat/"+rows[0]["id"]; self.h.do_GET(); d=self.response()
        self.assertEqual(d["messages"][1]["content"],"saved")

if __name__=="__main__": unittest.main()
