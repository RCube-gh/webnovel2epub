from bs4 import BeautifulSoup

from narou2kindle.extractors.hameln import _episode_refs, parse_hameln_url


def test_parse_hameln_url():
    source = parse_hameln_url("https://syosetu.org/novel/418773/")
    assert source.novel_id == "418773"
    assert source.base_url == "https://syosetu.org/novel/418773/"

    r18_source = parse_hameln_url("https://h.syosetu.org/novel/222119/")
    assert r18_source.novel_id == "222119"
    assert r18_source.host == "h.syosetu.org"


def test_finds_hameln_chapters_and_episodes():
    source = parse_hameln_url("https://syosetu.org/novel/418773/")
    listing = BeautifulSoup('''<section class="episode-list"><ul>
    <li class="episode-list__chapter"><div class="episode-list__chapter-title">Part one</div></li>
    <li><a class="episode-list__link" href="./1.html"><span class="episode-list__title">First</span></a></li>
    <li><a class="episode-list__link" href="./2.html"><span class="episode-list__title">Second</span></a></li>
    </ul></section>''', "html.parser").select_one(".episode-list")
    refs = _episode_refs(listing, source)
    assert [(ref.number, ref.title, ref.chapter) for ref in refs] == [
        (1, "First", "Part one"),
        (2, "Second", "Part one"),
    ]
