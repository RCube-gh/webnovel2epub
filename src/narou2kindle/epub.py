from __future__ import annotations

import re
import uuid
import zipfile
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image

from .models import Episode, Novel, TextBlock


_COVER_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _cover_asset(cover_path: Path) -> tuple[str, str, bytes]:
    """Return a Kindle-compatible cover asset from a user-supplied image."""
    suffix = cover_path.suffix.lower()
    media_type = _COVER_MEDIA_TYPES.get(suffix)
    if not media_type:
        supported = ", ".join(_COVER_MEDIA_TYPES)
        raise ValueError(f"Unsupported cover image type. Use one of: {supported}")
    if suffix != ".webp":
        return f"cover{suffix}", media_type, cover_path.read_bytes()

    try:
        with Image.open(cover_path) as image:
            rgba = image.convert("RGBA")
            converted = Image.new("RGB", rgba.size, "white")
            converted.paste(rgba, mask=rgba.getchannel("A"))
            buffer = BytesIO()
            converted.save(buffer, format="JPEG", quality=95)
    except OSError as exc:
        raise ValueError(f"Could not convert WebP cover to JPEG: {exc}") from exc
    return "cover.jpg", "image/jpeg", buffer.getvalue()


def safe_filename(value: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", value).strip().rstrip(".")
    return name[:120] or "novel"


def _xhtml_document(title: str, content: str, body_class: str = "") -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja">
<head><title>{escape(title)}</title><link rel="stylesheet" type="text/css" href="style.css" /></head>
<body class="{body_class}">{content}</body></html>'''


def _paragraphs(lines: list[str], kind: str = "prose") -> str:
    return "\n".join(f'<p class="{kind}">{escape(line)}</p>' for line in lines)


def _blocks(blocks: list[TextBlock]) -> str:
    return "\n".join(
        f'<p class="{block.kind}">{block.xhtml if block.xhtml is not None else escape(block.text) if block.text else "&#160;"}</p>'
        for block in blocks
    )


def _navigation_items(episodes: list[Episode], filenames: list[str]) -> str:
    items: list[str] = []
    active_chapter: str | None = None
    for episode, filename in zip(episodes, filenames):
        if episode.chapter != active_chapter:
            if active_chapter is not None:
                items.append("</ol></li>")
            active_chapter = episode.chapter
            if active_chapter:
                items.append(f"<li class=\"chapter\"><span>{escape(active_chapter)}</span><ol>")
        items.append(f'<li><a href="{filename}">{escape(episode.title)}</a></li>')
    if active_chapter is not None:
        items.append("</ol></li>")
    return "\n".join(items)


def write_epub(
    novel: Novel,
    destination: Path,
    cover_path: Path | None = None,
    writing_mode: str = "vertical",
) -> Path:
    if writing_mode not in {"vertical", "horizontal"}:
        raise ValueError("writing_mode must be 'vertical' or 'horizontal'")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cover_media_type: str | None = None
    cover_filename: str | None = None
    cover_data: bytes | None = None
    if cover_path:
        cover_filename, cover_media_type, cover_data = _cover_asset(cover_path)
    book_id = f"urn:uuid:{uuid.uuid4()}"
    chapter_files = [f"chapter-{index:04}.xhtml" for index in range(1, len(novel.episodes) + 1)]
    nav_items = _navigation_items(novel.episodes, chapter_files)
    manifest = "\n".join(
        f'<item id="chapter-{index}" href="{filename}" media-type="application/xhtml+xml" />'
        for index, filename in enumerate(chapter_files, 1)
    )
    spine = "\n".join(f'<itemref idref="chapter-{index}" />' for index in range(1, len(chapter_files) + 1))
    cover_manifest = (
        f'<item id="cover-image" href="images/{cover_filename}" media-type="{cover_media_type}" properties="cover-image" />\n'
        '<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml" />'
        if cover_data
        else ""
    )
    cover_spine = '<itemref idref="cover-page" />\n' if cover_data else ""
    page_progression = "rtl" if writing_mode == "vertical" else "ltr"
    package = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" xml:lang="ja">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{book_id}</dc:identifier><dc:title>{escape(novel.title)}</dc:title>
<dc:creator>{escape(novel.author)}</dc:creator><dc:language>ja</dc:language><dc:date>{date.today().isoformat()}</dc:date>
</metadata><manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
<item id="front" href="front.xhtml" media-type="application/xhtml+xml" />
<item id="style" href="style.css" media-type="text/css" />
{cover_manifest}
{manifest}
</manifest><spine page-progression-direction="{page_progression}">{cover_spine}<itemref idref="front" />
{spine}</spine></package>'''
    nav = _xhtml_document(novel.title, f"<nav epub:type=\"toc\" id=\"toc\" xmlns:epub=\"http://www.idpf.org/2007/ops\"><h1>{escape(novel.title)}</h1><ol>{nav_items}</ol></nav>")
    synopsis = _paragraphs(novel.synopsis.splitlines(), "synopsis") if novel.synopsis else ""
    front = _xhtml_document(
        novel.title,
        f'''<section class="front-matter"><h1>{escape(novel.title)}</h1>
<p class="author">{escape(novel.author)}</p>{synopsis}
<nav epub:type="toc" id="toc" xmlns:epub="http://www.idpf.org/2007/ops"><h2>Contents</h2><ol>{nav_items}</ol></nav></section>''',
    )
    cover = (
        _xhtml_document(
            novel.title,
            f'<section class="cover"><img src="images/{cover_filename}" alt="Cover" /></section>',
            "cover-page",
        )
        if cover_data
        else None
    )
    container = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" /></rootfiles></container>'''
    writing_css = '''html {
  writing-mode: vertical-rl;
  -epub-writing-mode: vertical-rl;
  -webkit-writing-mode: vertical-rl;
  text-orientation: mixed;
}
''' if writing_mode == "vertical" else '''html {
  writing-mode: horizontal-tb;
  -epub-writing-mode: horizontal-tb;
  -webkit-writing-mode: horizontal-tb;
}
'''
    css = writing_css + '''

body { line-height: 1.8; }
p { margin: 0 0 1em; }
p.prose { text-indent: 1em; }
p.dialogue { text-indent: 0; }
p.scene-break { margin: 1.5em 0; text-align: center; text-indent: 0; }
p.blank { min-block-size: 1em; margin: 0; }
h1 { line-height: 1.4; }
h2 { line-height: 1.4; }
h1.episode-title { font-size: 1.25em; }
h2.chapter-title { font-size: 1.75em; margin: 0 0 2em; text-indent: 0; }
p.author { text-indent: 0; }
p.synopsis { text-indent: 1em; }
body.cover-page { margin: 0; padding: 0; writing-mode: horizontal-tb; }
section.cover { height: 100vh; width: 100vw; }
section.cover img { display: block; height: 100%; max-width: 100%; object-fit: contain; width: 100%; }
'''
    with zipfile.ZipFile(destination, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        epub.writestr("META-INF/container.xml", container)
        epub.writestr("OEBPS/content.opf", package)
        epub.writestr("OEBPS/nav.xhtml", nav)
        epub.writestr("OEBPS/front.xhtml", front)
        epub.writestr("OEBPS/style.css", css)
        if cover_data and cover_filename and cover:
            epub.writestr("OEBPS/cover.xhtml", cover)
            epub.writestr(f"OEBPS/images/{cover_filename}", cover_data)
        previous_chapter: str | None = None
        for filename, episode in zip(chapter_files, novel.episodes):
            sections = []
            chapter_heading = ""
            if episode.chapter and episode.chapter != previous_chapter:
                chapter_heading = f'<h2 class="chapter-title">{escape(episode.chapter)}</h2>'
            if episode.preface:
                sections.append('<section class="preface">' + _paragraphs(episode.preface) + "</section>")
            sections.append(_blocks(episode.blocks))
            if episode.afterword:
                sections.append('<section class="afterword">' + _paragraphs(episode.afterword) + "</section>")
            content = chapter_heading + f'<h1 class="episode-title">{escape(episode.title)}</h1>' + "\n".join(sections)
            epub.writestr(f"OEBPS/{filename}", _xhtml_document(episode.title, content))
            previous_chapter = episode.chapter
    return destination
