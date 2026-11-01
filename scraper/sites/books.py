"""books.toscrape.com, a public sandbox made for scraping practice."""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..clean import squash
from ..http import Fetcher

FIELDS = ["title", "price_gbp", "rating", "in_stock", "url"]
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_list(html: str, url: str) -> tuple[list[dict], str | None]:
    s = BeautifulSoup(html, "html.parser")
    rows = []
    for card in s.select("article.product_pod"):
        a = card.select_one("h3 a[href]")
        if not a:  # a card without a link is not a book we can point to
            continue
        price = card.select_one(".price_color")
        digits = "".join(ch for ch in price.get_text() if ch.isdigit() or ch == ".") if price else ""
        stars = card.select_one("p.star-rating")
        rating_cls = [c for c in stars.get("class", []) if c != "star-rating"] if stars else []
        stock = card.select_one(".availability")
        rows.append({
            "title": squash(a.get("title") or a.get_text()),
            "price_gbp": float(digits) if digits.count(".") <= 1 and digits.strip(".") else "",
            "rating": RATINGS.get(rating_cls[0], "") if rating_cls else "",
            "in_stock": "In stock" in stock.get_text() if stock else "",
            "url": urljoin(url, a["href"]),
        })
    nxt = s.select_one("li.next a[href]")
    return rows, (urljoin(url, nxt["href"]) if nxt else None)


def scrape(start_url: str, fetch: Fetcher, max_pages: int | None = None) -> list[dict]:
    url, pages, out = start_url, 0, []
    while url and (max_pages is None or pages < max_pages):
        html = fetch.get(url)
        if html is None:
            break
        rows, url = parse_list(html, url)
        out.extend(rows)
        pages += 1
    return out
