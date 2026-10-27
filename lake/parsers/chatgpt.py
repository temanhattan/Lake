from datetime import datetime, timezone

def _iso(value):
    try: return datetime.fromtimestamp(float(value), timezone.utc).isoformat() if value else None
    except (ValueError, TypeError, OSError): return value if isinstance(value,str) else None


def parse(data):
    """Convert ChatGPT conversations, following current_node parent links only."""
    if isinstance(data, dict):
        data = data.get("conversations", [data])
    if not isinstance(data, list):
        raise ValueError("ChatGPT export must be an object or array")
    out = []
    for conv in data:
        if not isinstance(conv, dict):
            continue
        mapping = conv.get("mapping") or {}
        current = conv.get("current_node")
        path, seen = [], set()
        while current and current in mapping and current not in seen:
            seen.add(current)
            node = mapping[current]
            path.append(node)
            current = node.get("parent")
        path.reverse()
        messages = []
        for node in path:
            msg = (node or {}).get("message") or {}
            author = (msg.get("author") or {}).get("role", "user")
            if author not in {"user", "assistant", "system", "tool"}:
                author = "tool"
            content = msg.get("content") or {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
            body = "\n".join(p if isinstance(p, str) else str(p) for p in parts)
            if not body and content.get("text"):
                body = content["text"]
            if not body:
                continue
            ts = msg.get("create_time")
            try:
                ts = datetime.fromtimestamp(float(ts), timezone.utc).isoformat() if ts else None
            except (ValueError, TypeError, OSError):
                ts = None
            messages.append({"role": author, "content": body, "created_at": ts})
        if messages:
            out.append({"source": "chatgpt", "source_id": str(conv.get("conversation_id") or conv.get("id") or ""),
                        "title": conv.get("title") or "Untitled conversation", "model_used": None,
                        "created_at": _iso(conv.get("create_time")), "updated_at": _iso(conv.get("update_time")),
                        "messages": messages})
    return out
