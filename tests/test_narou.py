from narou2kindle.narou import _episode_refs, parse_novel_url
from bs4 import BeautifulSoup


def test_parse_supported_urls():
    source = parse_novel_url("https://ncode.syosetu.com/n4298mo/")
    assert source.code == "N4298MO"
    assert source.base_url == "https://ncode.syosetu.com/n4298mo/"

    r18_source = parse_novel_url("https://novel18.syosetu.com/n2281fz/")
    assert r18_source.code == "N2281FZ"
    assert r18_source.base_url == "https://novel18.syosetu.com/n2281fz/"


def test_parse_rejects_episode_url():
    try:
        parse_novel_url("https://ncode.syosetu.com/n4298mo/1/")
    except Exception as exc:
        assert "top-page" in str(exc)
    else:
        raise AssertionError("episode URL should be rejected")


def test_finds_episode_links_and_chapters():
    source = parse_novel_url("https://ncode.syosetu.com/n4298mo/")
    soup = BeautifulSoup('''<div class="p-eplist__chapter-title">第一章</div>
    <a href="/n4298mo/1/">はじまり</a><a href="/n4298mo/2/">次の話</a>''', "html.parser")
    refs = _episode_refs(soup, source)
    assert [ref.number for ref in refs] == [1, 2]
    assert refs[0].chapter == "第一章"
