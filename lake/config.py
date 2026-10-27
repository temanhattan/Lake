from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import tomllib


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8765
    db_path: str = "./data/lake.db"
    import_folder: str = "./imports"
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"
    vector_cache_path: str = "./data/vector-cache"
    embedding_chunk_tokens: int = 400
    embedding_overlap_tokens: int = 40
    duplicate_similarity_threshold: float = 0.82
    duplicate_scan_limit: int = 2500
    context_target_tokens: int = 500
    secret_scan: bool = True
    mcp_redact_secrets: bool = True
    mcp_allowed_projects: list = None
    mcp_audit_log: str = "./data/mcp-audit.jsonl"
    mcp_requests_per_minute: int = 60


def load_config(path="config.toml"):
    p = Path(path)
    if not p.exists():
        return Config()
    raw = tomllib.loads(p.read_text(encoding="utf-8")).get("lake", {})
    allowed = Config.__dataclass_fields__
    config=Config(**{k: v for k, v in raw.items() if k in allowed})
    host=urlparse(config.ollama_url).hostname
    if host not in {"localhost","127.0.0.1","::1"}:
        raise ValueError("ollama_url must point to this machine (localhost, 127.0.0.1, or ::1)")
    if config.host not in {"localhost","127.0.0.1","::1"}:
        raise ValueError("Lake only binds to this machine")
    if config.mcp_allowed_projects is not None and (not isinstance(config.mcp_allowed_projects,list) or any(not isinstance(x,str) for x in config.mcp_allowed_projects)):
        raise ValueError("mcp_allowed_projects must be a list of project names")
    if not isinstance(config.mcp_redact_secrets,bool):raise ValueError("mcp_redact_secrets must be true or false")
    if not isinstance(config.mcp_requests_per_minute,int) or config.mcp_requests_per_minute<1:
        raise ValueError("mcp_requests_per_minute must be a positive integer")
    return config
