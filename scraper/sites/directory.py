"""Business directory: categories -> paginated listings -> detail pages."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..clean import phone_e164, phone_pretty, squash
from ..http import Fetcher

FIELDS = ["name", "category", "phone", "phone_display", "street", "city", "state", "zip", "website", "email", "rating", "reviews", "source_url"]


def parse_address(lines: list[str]) -> tuple[str, str, str, str]:
    """['742 Valencia St', 'Suite 3', 'San Francisco, CA 94110-1234'] -> street, city, state, ZIP."""
    lines = [l for l in lines if l]
    if not lines:
        return "", "", "", ""
    m = re.match(r"(.+?),\s*([A-Za-z]{2})\.?\s+(\d{5})(?:-\d{4})?\s*$", lines[-1])
    if not m:  # no recognisable "City, ST 12345" line: keep everything as the street
        return ", ".join(lines), "", "", ""
    city, state, zip_ = m.groups()
    return ", ".join(lines[:-1]), city.strip(), state.upper(), zip_


def parse_rating(text: str) -> tuple[float | str, int | str]:
    """'4.5 (1,234 reviews)', '4.5/5 · 87 reviews', 'Rated 4 out of 5 (12)' -> (4.5, 1234)."""
    text = squash(text)
    rating = reviews = ""
    m = re.search(r"(\d(?:[.,]\d)?)\s*(?:/\s*5|out of 5|stars?)?", text)
    if m:
        value = float(m.group(1).replace(",", "."))
        rating = value if 0 <= value <= 5 else ""
    m = re.search(r"\(?\s*([\d,.\u202f ]+?)\s*(?:reviews?|ratings?|\))", text[m.end():] if m else text)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        reviews = int(digits) if digits else ""
    return rating, reviews


def parse_detail(html: str, url: str) -> dict | None:
    """One business page. None when the page is not a business page at all (moved, redesigned, an error page)."""
    s = BeautifulSoup(html, "html.parser")
    card = s.select_one("article.business") or s
    name_el = card.select_one("[itemprop=name]") or card.select_one("h1")
    name = squash(name_el.get_text()) if name_el else ""
    if not name:
        return None
    cats = "; ".join(dict.fromkeys(squash(a.get_text()) for a in card.select(".categories a") if squash(a.get_text())))
    addr = card.select_one(".address")
    street, city, state, zip_ = parse_address([squash(t) for t in addr.stripped_strings] if addr else [])
    phone_el = card.select_one(".phone") or card.select_one('a[href^="tel:"]')
    e164 = phone_e164(phone_el.get_text()) if phone_el else ""
    web = card.select_one("a.website[href]")
    mail = card.select_one("a.email") or card.select_one('a[href^="mailto:"]')
    rating_el = card.select_one(".rating")
    rating, reviews = parse_rating(rating_el.get_text()) if rating_el else ("", "")
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
    category_urls = list(dict.fromkeys(urljoin(start_url, a["href"]) for a in soup.select("ul.categories a[href]")))

    detail_urls: dict[str, None] = {}  # ordered set
    for url in category_urls:
        pages = 0
        while url and (max_pages is None or pages < max_pages):
            page = fetch.get(url)
            if page is None:
                break
            pages += 1
            s = BeautifulSoup(page, "html.parser")
            for a in s.select("article.listing h2 a[href]"):
                detail_urls[urljoin(url, a["href"])] = None
            nxt = s.select_one('a[rel="next"][href]')
            url = urljoin(url, nxt["href"]) if nxt else None

    records = []
    for url in detail_urls:
        page = fetch.get(url)
        record = parse_detail(page, url) if page else None
        if record:
            records.append(record)
        elif page:
            fetch.skipped.append(url)  # fetched, but not a business page
    return records
