from bs4 import BeautifulSoup

from narou2kindle.formatter import format_blocks
from narou2kindle.richtext import extract_rich_lines


def test_preserves_ruby_as_xhtml_without_counting_its_reading():
    body = BeautifulSoup('<div><p>魔法<ruby>騎士<rt>ナイト</rt></ruby>です。</p></div>', "html.parser").div
    blocks = format_blocks(extract_rich_lines(body), paragraph_length=6, section_length=0)
    assert blocks[0].text == "魔法騎士です。"
    assert blocks[0].xhtml == "魔法<ruby>騎士<rt>ナイト</rt></ruby>です。"
