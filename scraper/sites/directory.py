"""Business directory: categories -> paginated listings -> detail pages."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..clean import phone_e164, phone_pretty, squash
from ..http import Fetcher

FIELDS = ["name", "category", "phone", "phone_display", "street", "city", "state", "zip", "website", "email", "rating", "reviews", "source_url"]


def parse_detail(html: str, url: str) -> dict:
    s = BeautifulSoup(html, "html.parser")
    card = s.select_one("article.business")
    name = squash(card.select_one("[itemprop=name]").get_text())
    cats = "; ".join(squash(a.get_text()) for a in card.select(".categories a"))
    addr_lines = [squash(t) for t in card.select_one(".address").stripped_strings]
    street = addr_lines[0] if addr_lines else ""
    city = state = zip_ = ""
    if len(addr_lines) > 1:
        m = re.match(r"(.+),\s*([A-Z]{2})\s+(\d{5})", addr_lines[-1])
        if m:
            city, state, zip_ = m.groups()
    phone_el = card.select_one(".phone")
    e164 = phone_e164(phone_el.get_text()) if phone_el else ""
    web = card.select_one("a.website")
    mail = card.select_one("a.email")
    rating_el = card.select_one(".rating")
    rating = reviews = ""
    if rating_el:
        m = re.match(r"([\d.]+)\s*\((\d+)", rating_el.get_text())
        if m:
            rating, reviews = float(m.group(1)), int(m.group(2))
    return {
        "name": name,
        "category": cats,
        "phone": e164,
        "phone_display": phone_pretty(e164),
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_,
        "website": web["href"] if web else "",
        "email": mail.get_text(strip=True) if mail else "",
        "rating": rating,
        "reviews": reviews,
        "source_url": url,
    }


def scrape(start_url: str, fetch: Fetcher, max_pages: int | None = None) -> list[dict]:
    index = fetch.get(start_url)
    if index is None:
        return []
    soup = BeautifulSoup(index, "html.parser")
    category_urls = [urljoin(start_url, a["href"]) for a in soup.select("ul.categories a")]

    detail_urls: dict[str, None] = {}  # ordered set
    for url in category_urls:
        pages = 0
        while url and (max_pages is None or pages < max_pages):
            page = fetch.get(url)
            if page is None:
                break
            pages += 1
            s = BeautifulSoup(page, "html.parser")
            for a in s.select("article.listing h2 a"):
                detail_urls[urljoin(url, a["href"])] = None
            nxt = s.select_one('a[rel="next"]')
            url = urljoin(url, nxt["href"]) if nxt else None

    records = []
    for url in detail_urls:
        page = fetch.get(url)
        if page:
            records.append(parse_detail(page, url))
    return records
