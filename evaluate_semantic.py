"""Compute keyword, semantic, and hybrid recall@5 on the bundled 20-query set.

This script requires a running, local Ollama server and the configured embedding model.
It embeds missing sample chats through Lake's durable queue before scoring queries.
"""
import json
from pathlib import Path

from lake.config import load_config
from lake.db import connect
from lake.embeddings import EmbeddingQueue
from lake.library import import_chats
from lake.semantic_search import SemanticSearch
from lake.vector_index import create_vector_index
from lake.__main__ import seed


def main():
    cfg=load_config();db=connect(cfg.db_path)
    try:
        seed(db)
        queue=EmbeddingQueue(db,cfg,start_worker=False,schedule=True)
        while queue.run_once(db):pass
        failed=db.execute("SELECT COUNT(*) FROM embedding_jobs WHERE model_name=? AND status='failed'",(cfg.embedding_model,)).fetchone()[0]
        if failed:raise RuntimeError(f"{failed} embedding job(s) failed; check Ollama and model '{cfg.embedding_model}'")
        index=create_vector_index(db,cfg.vector_cache_path);queue.set_index(index)
        service=SemanticSearch(index,queue,cfg)
        evaluations=json.loads((Path(__file__).parent/"evaluation"/"semantic_queries.json").read_text(encoding="utf-8"))
        hits={mode:0 for mode in ("keyword","semantic","hybrid")};details=[]
        for item in evaluations:
            expected=db.execute("SELECT id FROM chats WHERE source_id=?",(item["expected_source_id"],)).fetchone()
            if not expected:raise RuntimeError(f"Missing sample chat {item['expected_source_id']}; run python -m lake --seed first")
            expected_id=expected[0];row={"query":item["query"],"expected_source_id":item["expected_source_id"],"top5":{}}
            for mode in hits:
                result=service.search(db,item["query"],{"archived":False},mode,5)
                ids=[x["id"] for x in result["results"][:5]]
                hit=expected_id in ids;hits[mode]+=int(hit);row["top5"][mode]=ids;row.setdefault("errors",{})[mode]=result.get("vector_error")
            details.append(row)
        report={"model":cfg.embedding_model,"queries":len(evaluations),"recall_at_5":{k:round(v/len(evaluations),3) for k,v in hits.items()},"hybrid_at_least_keyword":hits["hybrid"]>=hits["keyword"],"details":details}
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if not report["hybrid_at_least_keyword"]:raise SystemExit("Hybrid recall@5 is below keyword recall@5")
    finally:db.close()

if __name__=="__main__":main()
