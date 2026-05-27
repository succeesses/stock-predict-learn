# -*- coding: utf-8 -*-
"""
Formatting helpers used by notifications and image rendering.
"""

from __future__ import annotations

import re
from typing import List

import markdown2


TRUNCATION_SUFFIX = "\n\n...(本段内容过长已截断)"
MIN_MAX_WORDS = 10

_EMOJI_RANGES = [
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
    (0x1F300, 0x1F5FF),
    (0x1F600, 0x1F64F),
    (0x1F650, 0x1F67F),
    (0x1F680, 0x1F6FF),
    (0x1F900, 0x1F9FF),
    (0x1F1E0, 0x1F1FF),
]


def _is_emoji(char: str) -> bool:
    if len(char) != 1:
        return False
    code_point = ord(char)
    return any(lower <= code_point <= upper for lower, upper in _EMOJI_RANGES)


def _effective_len(text: str, emoji_len: int = 2) -> int:
    length = len(text)
    length += sum(emoji_len - 1 for char in text if _is_emoji(char))
    return length


def _slice_at_effective_len(text: str, effective_len: int, emoji_len: int = 2) -> tuple[str, str]:
    if _effective_len(text, emoji_len) <= effective_len:
        return text, ""

    length = 0
    for index, char in enumerate(text):
        length += emoji_len if _is_emoji(char) else 1
        if length > effective_len:
            return text[:index], text[index:]
    return text, ""


def slice_at_max_bytes(text: str, max_bytes: int) -> tuple[str, str]:
    """
    Split text without breaking UTF-8 characters.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, ""

    head = encoded[:max_bytes]
    while head and (head[-1] & 0xC0) == 0x80:
        head = head[:-1]
    first = head.decode("utf-8", errors="ignore")
    return first, text[len(first):]


def markdown_to_plain_text(markdown_text: str) -> str:
    """
    Convert Markdown to readable plain text.
    """
    html = markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
    )
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|h\d|li|tr|blockquote)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_to_html_document(markdown_text: str) -> str:
    html_content = markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
    )

    css_style = """
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.5;
                color: #24292e;
                font-size: 14px;
                padding: 15px;
                max-width: 900px;
                margin: 0 auto;
            }
            h1 {
                font-size: 20px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.2em;
                margin-bottom: 0.8em;
                color: #0366d6;
            }
            h2 {
                font-size: 18px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.0em;
                margin-bottom: 0.6em;
            }
            h3 {
                font-size: 16px;
                margin-top: 0.8em;
                margin-bottom: 0.4em;
            }
            p {
                margin-top: 0;
                margin-bottom: 8px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 12px 0;
                display: block;
                overflow-x: auto;
                font-size: 13px;
            }
            th, td {
                border: 1px solid #dfe2e5;
                padding: 6px 10px;
                text-align: left;
            }
            th {
                background-color: #f6f8fa;
                font-weight: 600;
            }
            tr:nth-child(2n) {
                background-color: #f8f8f8;
            }
            blockquote {
                color: #6a737d;
                border-left: 0.25em solid #dfe2e5;
                padding: 0 1em;
                margin: 0 0 10px 0;
            }
            code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: rgba(27,31,35,0.05);
                border-radius: 3px;
                font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            }
            pre {
                padding: 12px;
                overflow: auto;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 3px;
                margin-bottom: 10px;
            }
            hr {
                height: 0.25em;
                padding: 0;
                margin: 16px 0;
                background-color: #e1e4e8;
                border: 0;
            }
            ul, ol {
                padding-left: 20px;
                margin-bottom: 10px;
            }
            li {
                margin: 2px 0;
            }
        """

    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                {css_style}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """


def format_feishu_markdown(content: str) -> str:
    """
    Convert standard Markdown into a Feishu-friendly lark_md subset.
    """

    def _flush_table_rows(buffer: List[str], output: List[str]) -> None:
        if not buffer:
            return

        def _parse_row(row: str) -> List[str]:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            return [cell for cell in cells if cell]

        rows = []
        for raw in buffer:
            if re.match(r"^\s*\|?\s*[:-]+\s*(\|\s*[:-]+\s*)+\|?\s*$", raw):
                continue
            parsed = _parse_row(raw)
            if parsed:
                rows.append(parsed)

        if not rows:
            return

        header = rows[0]
        for row in rows[1:]:
            pairs = []
            for index, cell in enumerate(row):
                key = header[index] if index < len(header) else f"列{index + 1}"
                pairs.append(f"{key}：{cell}")
            output.append(f"• {' | '.join(pairs)}")

    lines = []
    table_buffer: List[str] = []
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("|"):
            table_buffer.append(line)
            continue

        if table_buffer:
            _flush_table_rows(table_buffer, lines)
            table_buffer = []

        if re.match(r"^#{1,6}\s+", line):
            title = re.sub(r"^#{1,6}\s+", "", line).strip()
            line = f"**{title}**" if title else ""
        elif line.startswith("> "):
            quote = line[2:].strip()
            line = f"💬 {quote}" if quote else ""
        elif line.strip() == "---":
            line = "────────"
        elif line.startswith("- "):
            line = f"• {line[2:].strip()}"

        lines.append(line)

    if table_buffer:
        _flush_table_rows(table_buffer, lines)

    return "\n".join(lines).strip()


def _chunk_by_separators(content: str) -> tuple[list[str], str]:
    if "\n---\n" in content:
        parts = content.split("\n---\n")
        return parts, "\n---\n"
    if "\n## " in content:
        parts = content.split("\n## ")
        return [parts[0]] + [f"## {part}" for part in parts[1:]], "\n"
    if "\n### " in content:
        parts = content.split("\n### ")
        return [parts[0]] + [f"### {part}" for part in parts[1:]], "\n"
    if "\n**" in content:
        parts = content.split("\n**")
        return [parts[0]] + [f"**{part}" for part in parts[1:]], "\n"
    return [content], ""


def _chunk_by_max_words(content: str, max_words: int, emoji_len: int = 2) -> list[str]:
    if _effective_len(content, emoji_len) <= max_words:
        return [content]
    if max_words < MIN_MAX_WORDS:
        raise ValueError(f"max_words={max_words} < {MIN_MAX_WORDS}, 可能陷入无限递归。")

    chunks = []
    suffix = TRUNCATION_SUFFIX
    effective_max_words = max_words - len(suffix)
    if effective_max_words <= 0:
        effective_max_words = max_words
        suffix = ""

    while True:
        chunk, content = _slice_at_effective_len(content, effective_max_words, emoji_len)
        chunks.append(chunk + suffix)
        if _effective_len(content, emoji_len) <= effective_max_words:
            if content:
                chunks.append(content)
            break
    return chunks


def chunk_content_by_max_words(content: str, max_words: int, emoji_len: int = 2) -> list[str]:
    if max_words < MIN_MAX_WORDS:
        raise ValueError(f"max_words={max_words} < {MIN_MAX_WORDS}, 可能陷入无限递归。")
    if _effective_len(content, emoji_len) <= max_words:
        return [content]

    sections, separator = _chunk_by_separators(content)
    if not separator:
        return _chunk_by_max_words(content, max_words, emoji_len)

    chunks = []
    current_chunk: List[str] = []
    current_length = 0
    effective_max_words = max_words - len(separator)

    for section in sections:
        section_text = section + separator
        section_length = _effective_len(section_text, emoji_len)

        if section_length > max_words:
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_length = 0
            split_chunks = chunk_content_by_max_words(section, effective_max_words, emoji_len)
            split_chunks[-1] = split_chunks[-1] + separator
            chunks.extend(split_chunks)
            continue

        if current_length + section_length > max_words:
            if current_chunk:
                chunks.append("".join(current_chunk))
            current_chunk = [section_text]
            current_length = section_length
        else:
            current_chunk.append(section_text)
            current_length += section_length

    if current_chunk:
        chunks.append("".join(current_chunk))

    if chunks and chunks[-1].endswith(separator):
        chunks[-1] = chunks[-1][: -len(separator)]
    return chunks


def chunk_content_by_max_bytes(content: str, max_bytes: int, add_page_marker: bool = False) -> list[str]:
    """
    Split content by UTF-8 byte size without breaking separators when possible.
    """
    if len(content.encode("utf-8")) <= max_bytes:
        return [content]

    sections, separator = _chunk_by_separators(content)
    if not separator:
        chunks = []
        remaining = content
        suffix = TRUNCATION_SUFFIX if add_page_marker else ""
        budget = max_bytes - len(suffix.encode("utf-8"))
        while remaining:
            head, remaining = slice_at_max_bytes(remaining, max(1, budget))
            if remaining and suffix:
                chunks.append(head + suffix)
            else:
                chunks.append(head)
        if add_page_marker and len(chunks) > 1:
            return [f"{chunk}\n\n📄 ({index}/{len(chunks)})" for index, chunk in enumerate(chunks, start=1)]
        return chunks

    chunks = []
    current_chunk: List[str] = []
    current_bytes = 0
    separator_bytes = len(separator.encode("utf-8"))

    for section in sections:
        section_text = section + separator
        section_bytes = len(section_text.encode("utf-8"))
        if section_bytes > max_bytes:
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_bytes = 0
            head, tail = slice_at_max_bytes(section, max_bytes - 200)
            chunks.append(head + TRUNCATION_SUFFIX)
            if tail:
                chunks.extend(chunk_content_by_max_bytes(tail, max_bytes, add_page_marker=False))
            continue

        if current_bytes + section_bytes > max_bytes:
            if current_chunk:
                chunks.append("".join(current_chunk))
            current_chunk = [section_text]
            current_bytes = section_bytes
        else:
            current_chunk.append(section_text)
            current_bytes += section_bytes

    if current_chunk:
        chunks.append("".join(current_chunk))

    if chunks and chunks[-1].endswith(separator):
        chunks[-1] = chunks[-1][: -len(separator)]

    if add_page_marker and len(chunks) > 1:
        paged = []
        for index, chunk in enumerate(chunks, start=1):
            paged.append(f"{chunk}\n\n📄 ({index}/{len(chunks)})")
        return paged
    return chunks
