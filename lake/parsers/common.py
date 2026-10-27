import re

MARKER = re.compile(r"(?im)^(User|Assistant|System|Tool):[ \t]*")


def manual_messages(text):
    matches = list(MARKER.finditer(text))
    if not matches:
        return [{"role": "user", "content": text}]
    messages = []
    if text[:matches[0].start()].strip():
        messages.append({"role": "user", "content": text[:matches[0].start()]})
    for i, match in enumerate(matches):
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        role = match.group(1).lower()
        messages.append({"role": "tool" if role == "tool" else role,
                         "content": text[match.end():end]})
    return messages
