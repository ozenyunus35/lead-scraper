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
    assert sum("; " in r["category"] for r in merged) >= 16


def test_max_pages_limits_listing_pages(demo_site):
    fetch = Fetcher(delay=0)
    rows = directory.scrape(demo_site, fetch, max_pages=1)
    assert 0 < len(rows) <= 6 * 10
