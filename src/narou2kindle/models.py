from dataclasses import dataclass, field


@dataclass(frozen=True)
class EpisodeRef:
    number: int
    title: str
    url: str
    chapter: str | None = None


@dataclass
class TextBlock:
    text: str
    kind: str = "prose"
    xhtml: str | None = None


@dataclass
class Episode:
    title: str
    blocks: list[TextBlock]
    preface: list[str] = field(default_factory=list)
    afterword: list[str] = field(default_factory=list)
    chapter: str | None = None


@dataclass
class Novel:
    code: str
    title: str
    author: str
    synopsis: str
    source_url: str
    episodes: list[Episode]
