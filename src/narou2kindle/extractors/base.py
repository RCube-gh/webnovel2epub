from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..models import EpisodeRef, Novel


MetadataCallback = Callable[[str, str, str, list[EpisodeRef]], None]
EpisodeCallback = Callable[[str, int, int, EpisodeRef], None]


class ExtractionError(RuntimeError):
    """A source site could not be read or is not supported."""


class NovelExtractor(Protocol):
    """Site-specific adapter that produces the shared Novel model."""

    def identifier(self, url: str) -> str: ...

    def download(
        self,
        url: str,
        on_metadata: MetadataCallback | None = None,
        on_episode: EpisodeCallback | None = None,
    ) -> Novel: ...
