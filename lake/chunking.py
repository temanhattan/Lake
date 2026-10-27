"""Transcript chunking that prefers user/reply groups and preserves code fences."""
import hashlib
import re

FENCED = re.compile(r"```[^\n]*\n[\s\S]*?```", re.M)


def _cut_at_boundary(text, end):
    cut = max(text.rfind("\n", 0, end), text.rfind(" ", 0, end))
    return cut if cut > end * 0.55 else end


def _split_plain(text, max_chars, overlap_chars):
    parts=[]; pos=0
    while pos < len(text):
        end=min(len(text),pos+max_chars)
        if end < len(text): end=_cut_at_boundary(text[pos:],max_chars)+pos
        parts.append(text[pos:end])
        if end>=len(text): break
        pos=max(pos+1,end-overlap_chars)
    return parts


def _split_code(block, max_chars, overlap_chars):
    first=block.find("\n")
    opening=block[:first+1] if first>=0 else "``\n"
    closing="```"
    body=block[first+1:-3] if first>=0 and block.endswith(closing) else block[first+1:]
    budget=max(32,max_chars-len(opening)-len(closing)-2)
    pieces=_split_plain(body,budget,overlap_chars)
    return [opening+piece+("\n" if piece and not piece.endswith("\n") else "")+closing for piece in pieces]


def split_message(content, max_tokens=400, overlap_tokens=40):
    """Return text pieces; small fenced blocks remain intact when they fit."""
    max_chars=max(256,int(max_tokens)*4); overlap=max(0,int(overlap_tokens)*4)
    pieces=[]; pos=0
    for match in FENCED.finditer(content):
        pieces.extend(_split_plain(content[pos:match.start()],max_chars,overlap) if len(content[pos:match.start()])>max_chars else ([content[pos:match.start()]] if content[pos:match.start()] else []))
        block=match.group(0)
        pieces.extend([block] if len(block)<=max_chars else _split_code(block,max_chars,overlap))
        pos=match.end()
    tail=content[pos:]
    if tail: pieces.extend(_split_plain(tail,max_chars,overlap) if len(tail)>max_chars else [tail])
    return pieces or [""]


def chunk_messages(messages, max_tokens=400, overlap_tokens=40):
    """Build bounded chunks from user/reply groups, with hashes for idempotency."""
    max_chars=max(256,int(max_tokens)*4); groups=[]; current=[]
    for message in messages:
        if message.get("role")=="user" and current:
            groups.append(current); current=[]
        current.append(message)
    if current: groups.append(current)
    chunks=[]; buffered=[]; buffer_start=None; buffer_end=None; buffer_chars=0

    def emit(text,start,end):
        if not text.strip(): return
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks.append({"message_start_idx":start,"message_end_idx":end,"text":text,"content_hash":digest})
    def flush():
        nonlocal buffered,buffer_start,buffer_end,buffer_chars
        if buffered: emit("\n\n".join(buffered),buffer_start,buffer_end)
        buffered=[];buffer_start=buffer_end=None;buffer_chars=0

    for group in groups:
        start=int(group[0]["idx"]); end=int(group[-1]["idx"])
        rendered="\n\n".join(f"[{m.get('role','user')}]\n{m.get('content','')}" for m in group)
        if len(rendered)>max_chars:
            flush()
            for message in group:
                idx=int(message["idx"]); role=message.get("role","user")
                for piece in split_message(message.get("content", ""),max_tokens,overlap_tokens):
                    emit(f"[{role}]\n{piece}",idx,idx)
            continue
        if buffered and buffer_chars+len(rendered)>max_chars: flush()
        if not buffered: buffer_start=start
        buffered.append(rendered); buffer_end=end; buffer_chars+=len(rendered)+2
    flush()
    return chunks
