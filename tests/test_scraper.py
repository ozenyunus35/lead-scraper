import functools
import http.server
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from scraper.clean import dedupe, phone_e164
from scraper.http import Fetcher
from scraper.sites import books, directory

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.parametrize("raw", ["(415) 555-0134", "415.555.0134", "+1 415 555 0134", "415-555-0134", "1-415-555-0134"])
def test_phone_formats_normalise_to_one_number(raw):
    assert phone_e164(raw) == "+14155550134"


def test_unparseable_phone_is_empty():
    assert phone_e164("call us!") == ""


def test_dedupe_merges_by_phone_and_keeps_the_complete_listing():
    rows = [
        {"name": "Harbor Grill LLC", "category": "Fitness", "phone": "+14155550101", "email": "", "zip": "94110"},
        {"name": "Harbor Grill", "category": "Restaurants", "phone": "+14155550101", "email": "hi@harbor.example", "zip": "94110"},
        {"name": "Other", "category": "Dentists", "phone": "+14155550102", "email": "", "zip": "94110"},
    ]
    out, removed = dedupe(rows)
    assert removed == 1
    merged = next(r for r in out if r["phone"] == "+14155550101")
    assert merged["name"] == "Harbor Grill"
    assert merged["category"] == "Restaurants; Fitness"
    assert merged["email"] == "hi@harbor.example"


def test_books_list_page_is_parsed():
    rows, nxt = books.parse_list((FIXTURES / "books-page-1.html").read_text(encoding="utf-8"), "https://books.toscrape.com/catalogue/page-1.html")
    assert len(rows) == 20
    assert rows[0]["title"] == "A Light in the Attic"
    assert isinstance(rows[0]["price_gbp"], float) and rows[0]["rating"] in range(1, 6)
    assert nxt == "https://books.toscrape.com/catalogue/page-2.html"


@pytest.fixture(scope="module")
def demo_site(tmp_path_factory):
    """Generate the demo directory and serve it on a local port."""
    root = tmp_path_factory.mktemp("site")
    subprocess.run([sys.executable, str(ROOT / "demo_directory" / "generate.py"), str(root / "directory")], check=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/directory/index.html"
    httpd.shutdown()


def test_full_crawl_of_the_demo_directory(demo_site):
    fetch = Fetcher(delay=0)
    rows = directory.scrape(demo_site, fetch)
    assert len(rows) == 150  # every detail page, duplicates included
    merged, removed = dedupe(rows)
    assert removed == 12 and len(merged) == 138
    assert all(r["phone"].startswith("+1") and len(r["phone"]) == 12 for r in merged)
    assert all(r["city"] and r["state"] == "CA" and len(r["zip"]) == 5 for r in merged)
    assert sum("; " in r["category"] for r in merged) == 6  # only realtor + tax office cross-listings
    assert all("Restaurants" not in r["category"] or r["category"] == "Restaurants" for r in merged)


def test_max_pages_limits_listing_pages(demo_site):
    fetch = Fetcher(delay=0)
    rows = directory.scrape(demo_site, fetch, max_pages=1)
    assert 0 < len(rows) <= 6 * 10


# --- A directory that misbehaves the way real sites do -------------------------------------------

def _messy_site():
    """Pages a real directory serves: a pagination loop, a redesigned page, a dead link, a PDF,
    a server that is briefly overloaded, and UTF-8 text with no charset in the header."""
    calls: dict[str, int] = {}
    good = """<html><body><article class="business"><h1 itemprop="name">Café Ñandú &amp; Søn</h1>
<p class="categories"><a href="#">Restaurants</a> <a href="#">Restaurants</a></p>
<dd class="address">88 Shattuck Ave<br>Suite 4<br>Berkeley, ca 94704-1234</dd>
<dd class="phone">510.555.0177</dd><dd class="rating">4.5/5 · 1,234 reviews</dd></article></body></html>"""
    pages = {
        "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /private/\n"),
        "/index.html": (200, "text/html", '<ul class="categories"><li><a href="/cat/1.html">Food</a></li>'
                        '<li><a href="/cat/1.html">Food again</a></li><li><a>no link</a></li></ul>'),
        # page 1 -> page 2 -> back to page 1: a crawler without memory never stops
        "/cat/1.html": (200, "text/html", '<article class="listing"><h2><a href="/biz/good.html">Good</a></h2></article>'
                        '<article class="listing"><h2><a href="/biz/redesigned.html">New look</a></h2></article>'
                        '<article class="listing"><h2><a>no href</a></h2></article><a rel="next" href="/cat/2.html">next</a>'),
        "/cat/2.html": (200, "text/html", '<article class="listing"><h2><a href="/biz/gone.html">Gone</a></h2></article>'
                        '<article class="listing"><h2><a href="/biz/menu.pdf">Menu</a></h2></article>'
                        '<article class="listing"><h2><a href="/biz/busy.html">Busy</a></h2></article>'
                        '<article class="listing"><h2><a href="/private/x.html">Private</a></h2></article>'
                        '<a rel="next" href="/cat/1.html#top">next</a>'),
        "/biz/good.html": (200, "text/html", good),
        "/biz/redesigned.html": (200, "text/html", "<html><body><div class='hero'>We moved! Visit our new site.</div></body></html>"),
        "/biz/menu.pdf": (200, "application/pdf", "%PDF-1.4"),
        "/biz/busy.html": (200, "text/html; charset=utf-8", good.replace("Café Ñandú &amp; Søn", "Busy Bee Plumbing").replace("0177", "0178")),
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            calls[self.path] = calls.get(self.path, 0) + 1
            if self.path == "/biz/busy.html" and calls[self.path] == 1:  # overloaded once, then fine
                self.send_response(503)
                self.send_header("Retry-After", "0")
                self.end_headers()
                return
            if self.path not in pages:
                self.send_response(404)
                self.end_headers()
                return
            status, kind, body = pages[self.path]
            self.send_response(status)
            self.send_header("Content-Type", kind)  # note: no charset for the UTF-8 pages
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, calls


def test_a_messy_directory_is_crawled_without_crashing_or_looping():
    httpd, calls = _messy_site()
    try:
        fetch = Fetcher(delay=0)
        rows = directory.scrape(f"http://127.0.0.1:{httpd.server_address[1]}/index.html", fetch)
    finally:
        httpd.shutdown()
    assert [r["name"] for r in rows] == ["Café Ñandú & Søn", "Busy Bee Plumbing"]  # UTF-8 read right, no mojibake
    cafe = rows[0]
    assert cafe["category"] == "Restaurants"
    assert (cafe["street"], cafe["city"], cafe["state"], cafe["zip"]) == ("88 Shattuck Ave, Suite 4", "Berkeley", "CA", "94704")
    assert (cafe["rating"], cafe["reviews"], cafe["phone"]) == (4.5, 1234, "+15105550177")
    assert calls["/cat/1.html"] == 1 and calls["/cat/2.html"] == 1  # the loop was noticed
    assert calls["/biz/busy.html"] == 2  # retried once after the 503
    assert calls["/biz/gone.html"] == 1  # a 404 is not retried
    assert "/private/x.html" not in calls  # robots.txt respected
    skipped = {u.rsplit("/", 1)[-1] for u in fetch.skipped}
    assert skipped == {"redesigned.html", "gone.html", "menu.pdf", "x.html"}


@pytest.mark.parametrize("text, expected", [
    ("4.5 (1,234 reviews)", (4.5, 1234)),
    ("4.5/5 · 87 reviews", (4.5, 87)),
    ("Rated 4 out of 5 (12)", (4.0, 12)),
    ("3,8 stars · 1 234 reviews", (3.8, 1234)),
    ("No reviews yet", ("", "")),
])
def test_ratings_written_in_different_ways(text, expected):
    assert directory.parse_rating(text) == expected


@pytest.mark.parametrize("lines, expected", [
    (["742 Valencia St", "San Francisco, CA 94110"], ("742 Valencia St", "San Francisco", "CA", "94110")),
    (["742 Valencia St", "Suite 3", "San Francisco, CA 94110-2231"], ("742 Valencia St, Suite 3", "San Francisco", "CA", "94110")),
    (["PO Box 12, somewhere"], ("PO Box 12, somewhere", "", "", "")),
    ([], ("", "", "", "")),
])
def test_addresses_split_into_parts(lines, expected):
    assert directory.parse_address(lines) == expected


def test_a_page_that_is_not_a_business_page_is_skipped_not_fatal():
    assert directory.parse_detail("<html><body><p>Page not found</p></body></html>", "u") is None
    assert directory.parse_detail("", "u") is None


def test_retry_after_is_honoured_and_capped():
    f = Fetcher(delay=0)
    assert f._retry_after("3") == 3.0
    assert f._retry_after("99999") == 120.0
    assert f._retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert f._retry_after("soon") is None and f._retry_after(None) is None


def test_a_copy_without_a_phone_joins_the_listing_that_has_one():
    rows = [
        {"name": "Harbor Grill Inc.", "category": "Restaurants", "phone": "", "email": "", "zip": "94110", "website": "https://harbor.example"},
        {"name": "The Harbor Grill", "category": "Restaurants", "phone": "+14155550101", "email": "hi@harbor.example", "zip": "94110", "website": ""},
    ]
    out, removed = dedupe(rows)
    assert removed == 1 and out[0]["phone"] == "+14155550101" and out[0]["website"] == "https://harbor.example"


def test_a_shared_switchboard_does_not_merge_different_businesses():
    rows = [
        {"name": "Bayview Dental Care", "category": "Dentists", "phone": "+14155550150", "zip": "94110"},
        {"name": "Pacific Plumbing", "category": "Plumbers", "phone": "+14155550150", "zip": "94110"},
        {"name": "Bayview Dental Care LLC (Main Office)", "category": "Dentists", "phone": "+14155550150", "zip": "94110"},
    ]
    out, removed = dedupe(rows)
    assert removed == 1 and sorted(r["name"] for r in out) == ["Bayview Dental Care", "Pacific Plumbing"]


def test_same_name_in_another_town_is_another_business():
    rows = [
        {"name": "Cedar Bookkeeping", "category": "Accountants", "phone": "", "zip": "94110"},
        {"name": "Cedar Bookkeeping", "category": "Accountants", "phone": "", "zip": "94704"},
    ]
    assert dedupe(rows)[1] == 0


def test_a_book_card_with_missing_parts_is_kept_or_skipped_not_fatal():
    html = """<article class="product_pod"><h3><a href="b.html" title="Partial">Partial</a></h3></article>
<article class="product_pod"><p>no link at all</p></article>"""
    rows, nxt = books.parse_list(html, "https://books.toscrape.com/catalogue/page-1.html")
    assert [r["title"] for r in rows] == ["Partial"] and rows[0]["price_gbp"] == "" and nxt is None


def test_a_site_that_returns_nothing_writes_nothing(tmp_path):
    from scraper.__main__ import main
    with pytest.raises(SystemExit) as e:
        main(["books", "--url", "http://127.0.0.1:9/none.html", "--delay", "0", "--out", str(tmp_path)])
    assert e.value.code == 1 and not list(tmp_path.iterdir())
