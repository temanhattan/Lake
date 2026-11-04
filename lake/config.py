from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlparse
import tomllib


def default_data_dir():
    override = os.getenv("LAKE_DATA_DIR")
    if override:
        return str(Path(override).expanduser())
    if os.name == "nt":
        root = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return str(Path(root) / "Lake")
    if os.name == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "Lake")
    return str(Path.home() / ".local" / "share" / "lake")


@dataclass
class Config:
    data_dir: str = default_data_dir()
    host: str = "127.0.0.1"
    port: int = 8765
    db_path: str = None
    import_folder: str = None
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:3b"
    num_ctx: int = 8192
    card_chunk_tokens: int = 5000
    embedding_model: str = "nomic-embed-text"
    vector_cache_path: str = None
    embedding_chunk_tokens: int = 400
    embedding_overlap_tokens: int = 40
    duplicate_similarity_threshold: float = 0.82
    duplicate_scan_limit: int = 2500
    context_target_tokens: int = 500
    secret_scan: bool = True
    mcp_redact_secrets: bool = True
    mcp_allowed_projects: list = None
    mcp_audit_log: str = None
    mcp_requests_per_minute: int = 60

    def __post_init__(self):
        data_dir = Path(self.data_dir).expanduser()
        self.data_dir = str(data_dir)
        if self.db_path is None:
            self.db_path = str(data_dir / "lake.db")
        if self.import_folder is None:
            self.import_folder = str(data_dir / "imports")
        if self.vector_cache_path is None:
            self.vector_cache_path = str(data_dir / "vector-cache")
        if self.mcp_audit_log is None:
            self.mcp_audit_log = str(data_dir / "mcp-audit.jsonl")


def load_config(path="config.toml"):
    p = Path(path)
    if not p.exists():
        return Config()
    raw = tomllib.loads(p.read_text(encoding="utf-8")).get("lake", {})
    if os.getenv("LAKE_DATA_DIR"):
        raw = {key: value for key, value in raw.items()
               if key not in {"db_path", "import_folder", "vector_cache_path", "mcp_audit_log"}}
        raw["data_dir"] = os.environ["LAKE_DATA_DIR"]
    allowed = Config.__dataclass_fields__
    config=Config(**{k: v for k, v in raw.items() if k in allowed})
    host=urlparse(config.ollama_url).hostname
    if host not in {"localhost","127.0.0.1","::1"}:
        raise ValueError("ollama_url must point to this machine (localhost, 127.0.0.1, or ::1)")
    if config.host not in {"localhost","127.0.0.1","::1"}:
        raise ValueError("Lake only binds to this machine")
    if not isinstance(config.num_ctx,int) or config.num_ctx<4096:
        raise ValueError("num_ctx must be an integer of at least 4096")
    if not isinstance(config.card_chunk_tokens,int) or config.card_chunk_tokens<256 or config.card_chunk_tokens>=config.num_ctx:
        raise ValueError("card_chunk_tokens must be at least 256 and smaller than num_ctx")
    if config.mcp_allowed_projects is not None and (not isinstance(config.mcp_allowed_projects,list) or any(not isinstance(x,str) for x in config.mcp_allowed_projects)):
        raise ValueError("mcp_allowed_projects must be a list of project names")
    if not isinstance(config.mcp_redact_secrets,bool):raise ValueError("mcp_redact_secrets must be true or false")
    if not isinstance(config.mcp_requests_per_minute,int) or config.mcp_requests_per_minute<1:
        raise ValueError("mcp_requests_per_minute must be a positive integer")
    return config
