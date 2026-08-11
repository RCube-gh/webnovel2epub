from __future__ import annotations

import re
from html import escape

from .models import TextBlock
from .richtext import RichLine


_SCENE_BREAK_RE = re.compile(r"^(?:[◇♢◆□■△▲▽▼＊*#]+|[―—─\-]{3,})$")
_DIALOGUE_PREFIXES = ("「", "『", "（", "【", "〈", "《")
_SPEAKER_LABEL_RE = re.compile(r"^(?:\{[^{}\r\n]+\}|｛[^｛｝\r\n]+｝)\s*")


def _is_dialogue(text: str) -> bool:
    """Recognize dialogue with an optional Hameln-style speaker label."""
    without_label = _SPEAKER_LABEL_RE.sub("", text, count=1)
    return without_label.startswith(_DIALOGUE_PREFIXES)


def format_blocks(
    lines: list[str | RichLine], paragraph_length: int = 220, section_length: int = 1000
) -> list[TextBlock]:
    """Reflow sentence-per-line web fiction markup into ebook text blocks."""
    if paragraph_length < 1:
        raise ValueError("paragraph_length must be positive")
    if section_length < 0:
        raise ValueError("section_length must not be negative")

    blocks: list[TextBlock] = []
    prose_lines: list[RichLine] = []

    def flush_prose() -> None:
        if prose_lines:
            blocks.append(
                TextBlock(
                    "".join(line.text for line in prose_lines),
                    "prose",
                    "".join(line.xhtml for line in prose_lines),
                )
            )
            prose_lines.clear()

    for original_line in lines:
        line = original_line if isinstance(original_line, RichLine) else RichLine(original_line, escape(original_line))
        if not line.text.strip(" \t\r\n"):
            flush_prose()
            continue
        compact = re.sub(r"\s", "", line.text)
        if _SCENE_BREAK_RE.fullmatch(compact):
            flush_prose()
            blocks.append(TextBlock(line.text, "scene-break", line.xhtml))
            continue

        content = line.without_full_width_indent()
        if _is_dialogue(content.text):
            flush_prose()
            blocks.append(TextBlock(content.text, "dialogue", content.xhtml))
            continue

        if prose_lines and sum(len(item.text) for item in prose_lines) + len(content.text) > paragraph_length:
            flush_prose()
        prose_lines.append(content)

    flush_prose()
    return _insert_section_breaks(blocks, section_length)


def _insert_section_breaks(blocks: list[TextBlock], section_length: int) -> list[TextBlock]:
    """Insert sparse reading rests, never inside a consecutive dialogue run."""
    result: list[TextBlock] = []
    characters_since_break = 0

    for block in blocks:
        if block.kind == "scene-break":
            if result and result[-1].kind != "blank":
                result.append(TextBlock("", "blank"))
            result.append(block)
            result.append(TextBlock("", "blank"))
            characters_since_break = 0
            continue

        previous = result[-1] if result else None
        is_dialogue_run = previous and previous.kind == "dialogue" and block.kind == "dialogue"
        if (
            section_length
            and characters_since_break >= section_length
            and previous
            and previous.kind != "blank"
            and not is_dialogue_run
        ):
            result.append(TextBlock("", "blank"))
            characters_since_break = 0
        result.append(block)
        characters_since_break += len(block.text)

    return result
