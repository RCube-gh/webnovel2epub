"""Compatibility imports for the original Narou-only module layout."""

from .extractors.base import ExtractionError
from .extractors.narou import (
    NarouExtractor,
    NarouUrl,
    _episode_refs,
    _text_lines,
    parse_narou_url,
)
from .formatter import format_blocks

NarouClient = NarouExtractor
NarouError = ExtractionError
NovelUrl = NarouUrl
parse_novel_url = parse_narou_url

__all__ = [
    "NarouClient",
    "NarouError",
    "NovelUrl",
    "_episode_refs",
    "_text_lines",
    "format_blocks",
    "parse_novel_url",
]
