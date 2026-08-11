from pathlib import Path

from narou2kindle.cli import _output_path


def test_output_adds_epub_extension_when_omitted():
    assert _output_path(Path("books/my-novel"), "unused") == Path("books/my-novel.epub")


def test_output_keeps_epub_extension():
    assert _output_path(Path("books/my-novel.epub"), "unused") == Path("books/my-novel.epub")
