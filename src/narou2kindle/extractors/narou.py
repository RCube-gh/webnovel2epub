from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

from ..formatter import format_blocks
from ..models import Episode, EpisodeRef, Novel
from ..richtext import extract_rich_lines
from .base import EpisodeCallback, ExtractionError, MetadataCallback


_HOSTS = {"ncode.syosetu.com", "novel18.syosetu.com"}
_CODE_RE = re.compile(r"^n[0-9a-z]+$", re.IGNORECASE)


@dataclass(frozen=True)
class NarouUrl:
    code: str
    base_url: str


def parse_narou_url(value: str) -> NarouUrl:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _HOSTS:
        raise ExtractionError("Please provide a novel URL from syosetu.com or novel18.syosetu.com.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1 or not _CODE_RE.fullmatch(parts[0]):
        raise ExtractionError("Please provide the novel top-page URL (for example, https://ncode.syosetu.com/n1234ab/).")
    return NarouUrl(code=parts[0].upper(), base_url=f"https://{parsed.hostname}/{parts[0].lower()}/")


def _text_lines(element: Tag | None) -> list[str]:
    if element is None:
        return []
    return [line.strip(" \t\r\n") for line in element.get_text("\n").splitlines() if line.strip()]


class NarouExtractor:
    def __init__(
        self, pause_seconds: float = 0.5, paragraph_length: int = 220, section_length: int = 1000
    ) -> None:
        self.pause_seconds = pause_seconds
        self.paragraph_length = paragraph_length
        self.section_length = section_length
        self._last_request = 0.0

    @staticmethod
    def handles(url: str) -> bool:
        return urlparse(url).hostname in _HOSTS

    def identifier(self, url: str) -> str:
        return parse_narou_url(url).code

    def _fetch(self, url: str) -> str:
        wait = self.pause_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": "narou2kindle/0.1 (+personal ebook conversion)"}
        if urlparse(url).hostname == "novel18.syosetu.com":
            headers["Cookie"] = "over18=yes"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except OSError as exc:
            raise ExtractionError(f"Could not fetch the novel page: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

    def inspect(self, source: NarouUrl) -> tuple[str, str, str, list[EpisodeRef]]:
        soup = BeautifulSoup(self._fetch(source.base_url), "html.parser")
        title = _first_text(soup, ".novel_title", ".p-novel__title", "h1") or source.code
        author = _first_text(soup, ".novel_writername", ".p-novel__author", ".p-author__name") or ""
        synopsis = "\n".join(_text_lines(soup.select_one("#novel_ex")))
        episodes = self._all_episode_refs(soup, source)
        if not episodes:
            if soup.select_one("#novel_honbun, .p-novel__body"):
                episodes = [EpisodeRef(1, title, source.base_url)]
            else:
                raise ExtractionError("Could not find the episode list. The site's HTML may have changed.")
        return title, author, synopsis, episodes

    def _all_episode_refs(self, first_page: BeautifulSoup, source: NarouUrl) -> list[EpisodeRef]:
        """Collect every page of a paginated episode list."""
        episodes: list[EpisodeRef] = []
        seen_episode_urls: set[str] = set()
        seen_page_urls = {source.base_url}
        page_soup = first_page
        page_url = source.base_url
        chapter: str | None = None

        while True:
            page_refs, chapter = _episode_refs_page(page_soup, source, chapter)
            for ref in page_refs:
                if ref.url not in seen_episode_urls:
                    seen_episode_urls.add(ref.url)
                    episodes.append(ref)

            next_page_url = _next_episode_list_page(page_soup, source, page_url)
            if next_page_url is None or next_page_url in seen_page_urls:
                break
            seen_page_urls.add(next_page_url)
            page_url = next_page_url
            page_soup = BeautifulSoup(self._fetch(page_url), "html.parser")

        return sorted(episodes, key=lambda ref: ref.number)

    def download(
        self,
        url: str,
        on_metadata: MetadataCallback | None = None,
        on_episode: EpisodeCallback | None = None,
    ) -> Novel:
        source = parse_narou_url(url)
        title, author, synopsis, refs = self.inspect(source)
        if on_metadata:
            on_metadata(title, author, synopsis, refs)
        episodes = []
        for index, ref in enumerate(refs, 1):
            if on_episode:
                on_episode("Downloading", index, len(refs), ref)
            episodes.append(self._download_episode(ref))
            if on_episode:
                on_episode("Formatted", index, len(refs), ref)
        return Novel(source.code, title, author, synopsis, source.base_url, episodes)

    def _download_episode(self, ref: EpisodeRef) -> Episode:
        soup = BeautifulSoup(self._fetch(ref.url), "html.parser")
        blocks = format_blocks(extract_rich_lines(soup.select_one("#novel_honbun, .p-novel__body")), self.paragraph_length, self.section_length)
        if not blocks:
            raise ExtractionError(f"Could not read the body of episode {ref.number}: {ref.url}")
        return Episode(
            title=ref.title,
            blocks=blocks,
            preface=_text_lines(soup.select_one("#novel_p")),
            afterword=_text_lines(soup.select_one("#novel_a")),
            chapter=ref.chapter,
        )


def _first_text(soup: BeautifulSoup, *selectors: str) -> str:
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if text:
                return text
    return ""


def _episode_refs(soup: BeautifulSoup, source: NarouUrl) -> list[EpisodeRef]:
    return _episode_refs_page(soup, source)[0]


def _episode_refs_page(
    soup: BeautifulSoup, source: NarouUrl, initial_chapter: str | None = None
) -> tuple[list[EpisodeRef], str | None]:
    refs: list[EpisodeRef] = []
    seen: set[str] = set()
    chapter = initial_chapter
    href_pattern = re.compile(rf"/{re.escape(source.code.lower())}/(\d+)/?$")
    for element in soup.find_all(["div", "a"]):
        classes = " ".join(element.get("class", []))
        if element.name == "div" and "chapter" in classes:
            candidate = element.get_text(" ", strip=True)
            if candidate:
                chapter = candidate
        if element.name != "a":
            continue
        href = element.get("href", "")
        match = href_pattern.search(href)
        if not match:
            continue
        episode_url = urljoin(source.base_url, href)
        if episode_url in seen:
            continue
        seen.add(episode_url)
        title = element.get_text(" ", strip=True) or f"Episode {match.group(1)}"
        refs.append(EpisodeRef(int(match.group(1)), title, episode_url, chapter))
    return refs, chapter


def _next_episode_list_page(soup: BeautifulSoup, source: NarouUrl, current_url: str) -> str | None:
    """Return the pager's next link only when it belongs to this novel."""
    current_page = int(parse_qs(urlparse(current_url).query).get("p", ["1"])[0])
    source_path = urlparse(source.base_url).path.rstrip("/")
    for link in soup.select("a.c-pager__item--next[href]"):
        target = urljoin(current_url, link["href"])
        parsed = urlparse(target)
        if parsed.hostname != urlparse(source.base_url).hostname or parsed.path.rstrip("/") != source_path:
            continue
        page_values = parse_qs(parsed.query).get("p", [])
        if len(page_values) != 1 or not page_values[0].isdigit() or int(page_values[0]) <= current_page:
            continue
        return target
    return None
