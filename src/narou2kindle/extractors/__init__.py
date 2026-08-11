from .base import ExtractionError, NovelExtractor
from .hameln import HamelnExtractor
from .narou import NarouExtractor


def get_extractor(url: str, paragraph_length: int, section_length: int) -> NovelExtractor:
    if NarouExtractor.handles(url):
        return NarouExtractor(paragraph_length=paragraph_length, section_length=section_length)
    if HamelnExtractor.handles(url):
        return HamelnExtractor(paragraph_length=paragraph_length, section_length=section_length)
    raise ExtractionError("No extractor is available for this URL yet.")


__all__ = ["ExtractionError", "NovelExtractor", "get_extractor"]
