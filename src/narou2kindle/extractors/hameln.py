from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import CookieJar

from bs4 import BeautifulSoup, Tag

from ..formatter import format_blocks
from ..models import Episode, EpisodeRef, Novel
from ..richtext import extract_rich_lines
from .base import EpisodeCallback, ExtractionError, MetadataCallback


_HOSTS = {"syosetu.org", "h.syosetu.org"}
_R18_HOST = "h.syosetu.org"
_NOVEL_ID_RE = re.compile(r"^\d+$")
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass(frozen=True)
class HamelnUrl:
    novel_id: str
    base_url: str
    host: str


def parse_hameln_url(value: str) -> HamelnUrl:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _HOSTS:
        raise ExtractionError("Please provide a Hameln novel URL from syosetu.org.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[0] != "novel" or not _NOVEL_ID_RE.fullmatch(parts[1]):
        raise ExtractionError("Please provide the Hameln novel top-page URL (for example, https://syosetu.org/novel/12345/).")
    return HamelnUrl(novel_id=parts[1], base_url=f"https://{parsed.hostname}/novel/{parts[1]}/", host=parsed.hostname)


def _text_lines(element: Tag | None) -> list[str]:
    if element is None:
        return []
    return [line.strip(" \t\r\n") for line in element.get_text("\n").splitlines() if line.strip()]


class HamelnExtractor:
    def __init__(
        self, pause_seconds: float = 0.5, paragraph_length: int = 220, section_length: int = 1000
    ) -> None:
        self.pause_seconds = pause_seconds
        self.paragraph_length = paragraph_length
        self.section_length = section_length
        self._last_request = 0.0
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._confirmed_r18_novels: set[str] = set()

    @staticmethod
    def handles(url: str) -> bool:
        return urlparse(url).hostname in _HOSTS

    def identifier(self, url: str) -> str:
        return f"Hameln {parse_hameln_url(url).novel_id}"

    def _fetch(self, url: str, referer: str | None = None) -> str:
        wait = self.pause_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        headers = dict(_BROWSER_HEADERS)
        if referer:
            headers["Referer"] = referer
        request = Request(url, headers=headers)
        try:
            with self._opener.open(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except OSError as exc:
            raise ExtractionError(f"Could not fetch the Hameln novel page: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

    def _confirm_r18(self, source: HamelnUrl) -> None:
        if source.host != _R18_HOST or source.novel_id in self._confirmed_r18_novels:
            return
        # Hameln expects the visitor to load the age-gate page first.  Going
        # straight to the confirmation endpoint is rejected with HTTP 403.
        gate = BeautifulSoup(self._fetch(source.base_url), "html.parser")
        confirmation_link = gate.select_one('a[href*="mode=r18_cs_end"]')
        confirmation_url = (
            urljoin(source.base_url, confirmation_link["href"])
            if confirmation_link is not None
            else f"https://{_R18_HOST}/novel/?mode=r18_cs_end&nid={source.novel_id}&volume="
        )
        try:
            headers = dict(_BROWSER_HEADERS)
            headers["Referer"] = source.base_url
            request = Request(confirmation_url, headers=headers)
            with self._opener.open(request, timeout=30) as response:
                response.read()
        except OSError as exc:
            raise ExtractionError(f"Could not complete Hameln R18 age confirmation: {exc}") from exc
        finally:
            self._last_request = time.monotonic()
        self._confirmed_r18_novels.add(source.novel_id)

    def inspect(self, source: HamelnUrl) -> tuple[str, str, str, list[EpisodeRef]]:
        self._confirm_r18(source)
        soup = BeautifulSoup(self._fetch(source.base_url), "html.parser")
        listing = soup.select_one(".episode-list")
        if listing is None:
            raise ExtractionError("Could not find the Hameln episode list. The site's HTML may have changed.")
        title_element = soup.select_one('#maind [itemprop="name"]')
        title = title_element.get_text(" ", strip=True) if title_element else source.novel_id
        author_element = soup.select_one('#maind [itemprop="author"]')
        author = author_element.get_text(" ", strip=True) if author_element else ""
        synopsis_container = listing.find_parent("div", class_="ss")
        synopsis_element = synopsis_container.find_previous_sibling("div", class_="ss") if synopsis_container else None
        synopsis = "\n".join(_text_lines(synopsis_element))
        episodes = _episode_refs(listing, source)
        if not episodes:
            raise ExtractionError("Could not find Hameln episodes. The site's HTML may have changed.")
        return title, author, synopsis, episodes

    def download(
        self,
        url: str,
        on_metadata: MetadataCallback | None = None,
        on_episode: EpisodeCallback | None = None,
    ) -> Novel:
        source = parse_hameln_url(url)
        title, author, synopsis, refs = self.inspect(source)
        if on_metadata:
            on_metadata(title, author, synopsis, refs)
        episodes = []
        for index, ref in enumerate(refs, 1):
            if on_episode:
                on_episode("Downloading", index, len(refs), ref)
            episodes.append(self._download_episode(ref, source.base_url))
            if on_episode:
                on_episode("Formatted", index, len(refs), ref)
        return Novel(f"HM{source.novel_id}", title, author, synopsis, source.base_url, episodes)

    def _download_episode(self, ref: EpisodeRef, source_url: str) -> Episode:
        soup = BeautifulSoup(self._fetch(ref.url, referer=source_url), "html.parser")
        blocks = format_blocks(extract_rich_lines(soup.select_one("#honbun")), self.paragraph_length, self.section_length)
        if not blocks:
            raise ExtractionError(f"Could not read the body of Hameln episode {ref.number}: {ref.url}")
        return Episode(title=ref.title, blocks=blocks, chapter=ref.chapter)


def _episode_refs(listing: Tag, source: HamelnUrl) -> list[EpisodeRef]:
    refs: list[EpisodeRef] = []
    chapter: str | None = None
    for item in listing.select("li"):
        if "episode-list__chapter" in item.get("class", []):
            heading = item.select_one(".episode-list__chapter-title")
            chapter = heading.get_text(" ", strip=True) if heading else None
            continue
        link = item.select_one("a.episode-list__link[href]")
        if link is None:
            continue
        title = link.select_one(".episode-list__title")
        href = link["href"]
        match = re.search(r"/(\d+)\.html$", urljoin(source.base_url, href))
        if match is None:
            continue
        refs.append(
            EpisodeRef(
                number=int(match.group(1)),
                title=title.get_text(" ", strip=True) if title else f"Episode {match.group(1)}",
                url=urljoin(source.base_url, href),
                chapter=chapter,
            )
        )
    return refs
