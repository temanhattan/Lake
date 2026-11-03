# Import formats

Lake accepts ChatGPT `conversations.json`, Claude JSON exports, Markdown, text, and pasted transcripts. Use **Import chats** in the library or run `python -m lake import-folder PATH` to import every supported file under a folder.

Markdown and text imports split `User:` and `Assistant:` labels into messages; unmarked text stays together as one message. JSON imports are parsed by source-specific modules under `lake/parsers/`. Re-importing identical content is skipped; changed content updates the existing chat.

The [manual sample](../demo/manual/transcript.md) is fictional and safe to use for a first import.
