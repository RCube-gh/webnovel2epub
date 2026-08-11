from __future__ import annotations

from dataclasses import dataclass
from html import escape

from bs4 import NavigableString, Tag


@dataclass
class RichLine:
    text: str
    xhtml: str

    def without_full_width_indent(self) -> RichLine:
        removed = len(self.text) - len(self.text.lstrip("　"))
        if not removed:
            return self
        return RichLine(self.text[removed:], self.xhtml[removed:])


def extract_rich_lines(element: Tag | None) -> list[RichLine]:
    """Convert a site's body HTML into lines while retaining simple ruby markup."""
    if element is None:
        return []

    lines: list[RichLine] = []
    plain_parts: list[str] = []
    xhtml_parts: list[str] = []

    def flush() -> None:
        text = "".join(plain_parts)
        if text.strip():
            lines.append(RichLine(text, "".join(xhtml_parts)))
        plain_parts.clear()
        xhtml_parts.clear()

    def append_text(text: str) -> None:
        if not text or not text.strip():
            return
        plain_parts.append(text)
        xhtml_parts.append(escape(text))

    def ruby_base(tag: Tag) -> str:
        parts: list[str] = []
        for descendant in tag.descendants:
            if isinstance(descendant, NavigableString) and not any(
                parent.name in {"rt", "rp"} for parent in descendant.parents if isinstance(parent, Tag)
            ):
                parts.append(str(descendant))
        return "".join(parts)

    def walk(node: object) -> None:
        if isinstance(node, NavigableString):
            append_text(str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name == "br":
            flush()
            return
        if node.name == "ruby":
            base = ruby_base(node)
            reading_element = node.find("rt")
            reading = reading_element.get_text("", strip=True) if reading_element else ""
            if reading:
                plain_parts.append(base)
                xhtml_parts.append(f"<ruby>{escape(base)}<rt>{escape(reading)}</rt></ruby>")
            else:
                append_text(base)
            return
        for child in node.children:
            walk(child)
        if node.name in {"p", "div", "li", "section", "article"}:
            flush()

    for child in element.children:
        walk(child)
    flush()
    return lines
