import zipfile

from PIL import Image

from narou2kindle.epub import write_epub
from narou2kindle.models import Episode, Novel, TextBlock


def test_writes_valid_epub_layout(tmp_path):
    novel = Novel("N1", "題名", "作者", "紹介", "https://example.test/", [Episode("第一話", [TextBlock("本文")])])
    output = write_epub(novel, tmp_path / "book.epub")
    with zipfile.ZipFile(output) as archive:
        assert archive.read("mimetype") == b"application/epub+zip"
        assert "OEBPS/chapter-0001.xhtml" in archive.namelist()
        assert "OEBPS/front.xhtml" in archive.namelist()
        assert b"<h2>Contents</h2>" in archive.read("OEBPS/front.xhtml")
        assert b'page-progression-direction="rtl"' in archive.read("OEBPS/content.opf")
        assert b"writing-mode: vertical-rl" in archive.read("OEBPS/style.css")
        assert b'p.prose { text-indent: 1em; }' in archive.read("OEBPS/style.css")


def test_contents_nests_episodes_under_chapter_names(tmp_path):
    novel = Novel(
        "N1",
        "Title",
        "Author",
        "",
        "https://example.test/",
        [
            Episode("First", [TextBlock("Text")], chapter="Part one"),
            Episode("Second", [TextBlock("Text")], chapter="Part one"),
            Episode("Third", [TextBlock("Text")], chapter="Part two"),
        ],
    )
    output = write_epub(novel, tmp_path / "book.epub")
    with zipfile.ZipFile(output) as archive:
        contents = archive.read("OEBPS/front.xhtml")
        assert b'class="chapter"' in contents
        assert b"Part one" in contents
        assert b"Part two" in contents


def test_chapter_name_appears_at_the_start_of_its_first_episode(tmp_path):
    novel = Novel(
        "N1",
        "Title",
        "Author",
        "",
        "https://example.test/",
        [
            Episode("First", [TextBlock("Text")], chapter="Part one"),
            Episode("Second", [TextBlock("Text")], chapter="Part one"),
        ],
    )
    output = write_epub(novel, tmp_path / "book.epub")
    with zipfile.ZipFile(output) as archive:
        first = archive.read("OEBPS/chapter-0001.xhtml")
        second = archive.read("OEBPS/chapter-0002.xhtml")
        assert b'chapter-title' in first
        assert b'Part one' in first
        assert b'episode-title' in first
        assert b'chapter-title' not in second


def test_writes_preserved_ruby_markup(tmp_path):
    novel = Novel(
        "N1",
        "Title",
        "Author",
        "",
        "https://example.test/",
        [Episode("First", [TextBlock("魔法騎士", xhtml="魔法<ruby>騎士<rt>ナイト</rt></ruby>")])],
    )
    output = write_epub(novel, tmp_path / "book.epub")
    with zipfile.ZipFile(output) as archive:
        assert b"<ruby>" in archive.read("OEBPS/chapter-0001.xhtml")


def test_writes_horizontal_ltr_epub(tmp_path):
    novel = Novel("N1", "Title", "Author", "", "https://example.test/", [Episode("First", [TextBlock("Text")])])
    output = write_epub(novel, tmp_path / "book.epub", writing_mode="horizontal")
    with zipfile.ZipFile(output) as archive:
        assert b'page-progression-direction="ltr"' in archive.read("OEBPS/content.opf")
        css = archive.read("OEBPS/style.css")
        assert b"writing-mode: horizontal-tb" in css
        assert b"column-count" not in css


def test_converts_webp_cover_to_jpeg_for_kindle_compatibility(tmp_path):
    cover = tmp_path / "cover.webp"
    Image.new("RGBA", (4, 6), (255, 0, 0, 128)).save(cover, "WEBP")
    novel = Novel("N1", "Title", "Author", "", "https://example.test/", [Episode("First", [TextBlock("Text")])])
    output = write_epub(novel, tmp_path / "book.epub", cover)
    with zipfile.ZipFile(output) as archive:
        package = archive.read("OEBPS/content.opf")
        assert b'images/cover.jpg' in package
        assert b'media-type="image/jpeg"' in package
        assert archive.read("OEBPS/images/cover.jpg").startswith(b"\xff\xd8\xff")
