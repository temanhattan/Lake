from datetime import datetime, timezone


def parse(data):
    if isinstance(data, dict):
        data = data.get("conversations", [data])
    if not isinstance(data, list):
        raise ValueError("Claude export must be an object or array")
    out = []
    for conv in data:
        if not isinstance(conv, dict):
            continue
        messages = []
        for item in conv.get("chat_messages", conv.get("messages", [])):
            sender = item.get("sender", item.get("role", "user"))
            role = {"human": "user", "user": "user", "assistant": "assistant"}.get(sender, "tool")
            text = item.get("text")
            if text is None:
                content = item.get("content", "")
                if isinstance(content, list):
                    text = "\n".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content)
                else:
                    text = str(content)
            if not text:
                continue
            ts = item.get("created_at")
            messages.append({"role": role, "content": text, "created_at": ts})
        if messages:
            out.append({"source": "claude", "source_id": str(conv.get("uuid") or conv.get("id") or ""),
                        "title": conv.get("name") or conv.get("title") or "Untitled conversation",
                        "model_used": conv.get("model"), "created_at": conv.get("created_at"),
                        "updated_at": conv.get("updated_at"), "messages": messages})
    return out
