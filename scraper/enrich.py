"""Contact finder: visits a business's own website and collects the e-mail addresses,
social profiles and phone numbers it publishes.

It reads the home page and up to a few pages that usually hold contact details
(contact, about, team, imprint), on the same site only, through the same polite
fetcher. Addresses written to dodge bots ("info [at] shop [dot] com") are decoded;
things that only look like addresses (an image "logo@2x.png", a template's
"you@example.com", a form's placeholder) are not taken.
"""
from __future__ import annotations

import html as htmllib
import re
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from .clean import phone_e164, phone_pretty
from .http import Fetcher

EMAIL = re.compile(r"[a-z0-9][a-z0-9._%+-]{0,63}@(?:[a-z0-9-]+\.)+[a-z]{2,24}", re.I)
OBFUSCATED = re.compile(r"([a-z0-9._%+-]+)\s*[\[(]\s*at\s*[\])]\s*([a-z0-9-]+(?:\s*[\[(]\s*dot\s*[\])]\s*[a-z0-9-]+)+)", re.I)
NOT_MAIL = re.compile(r"\.(png|jpe?g|gif|svg|webp|avif|css|js)$", re.I)
PLACEHOLDER = re.compile(r"^(you|your|name|user|email|someone|john\.?doe|jane\.?doe)@|@(example\.(com|org|net)|domain\.com|email\.com|sentry\.io|wixpress\.com)$", re.I)
CONTACT_PAGE = re.compile(r"contact|get in touch|about|team|staff|people|impressum|imprint|kontakt|iletisim|iletişim", re.I)
SOCIAL = {
    "linkedin": re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/(company|in)/[^/?#]+", re.I),
    "facebook": re.compile(r"^https?://(www\.|m\.)?facebook\.com/(?!sharer|share|dialog|plugins|tr\b)[^/?#]+", re.I),
    "instagram": re.compile(r"^https?://(www\.)?instagram\.com/(?!p/|explore/)[^/?#]+", re.I),
    "x": re.compile(r"^https?://(www\.)?(twitter|x)\.com/(?!intent|share|home)[^/?#]+", re.I),
}
MAX_PAGES = 4  # home page plus three likely contact pages


def emails_in(soup: BeautifulSoup) -> list[str]:
    """Addresses on one page: mailto links first (the ones meant to be used), then text."""
    found: list[str] = []
    for a in soup.select('a[href^="mailto:" i]'):
        found.append(unquote(a["href"].split(":", 1)[1].split("?")[0]))
    for tag in soup(["script", "style", "input", "textarea"]):
        tag.decompose()  # placeholders and tracking code are not contact details
    text = htmllib.unescape(soup.get_text(" "))
    found += EMAIL.findall(text)
    for user, rest in OBFUSCATED.findall(text):
        found.append(f"{user}@" + re.sub(r"\s*[\[(]\s*dot\s*[\])]\s*", ".", rest))
    out = []
    for e in found:
        e = e.strip().strip(".").lower()
        if EMAIL.fullmatch(e) and not NOT_MAIL.search(e) and not PLACEHOLDER.search(e) and e not in out:
            out.append(e)
    return out


def socials_in(soup: BeautifulSoup, base: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in soup.select("a[href]"):
        href = urljoin(base, a["href"].strip())
        for net, pattern in SOCIAL.items():
            m = pattern.match(href)
            if m and net not in out:
                out[net] = m.group(0).rstrip("/")
    return out


def phones_in(soup: BeautifulSoup) -> list[str]:
    out = []
    for a in soup.select('a[href^="tel:" i]'):
        e = phone_e164(a["href"].split(":", 1)[1])
        if e and e not in out:
            out.append(e)
    return out


def enrich(record: dict, fetch: Fetcher) -> dict:
    """Contact details from the record's website. Returns only the new fields:
    emails (all found, best first), socials, extra phones and what happened ('site_status')."""
    site = record.get("website") or ""
    result = {"emails": [], "linkedin": "", "facebook": "", "instagram": "", "x": "", "site_phones": [], "site_status": "no website"}
    if not site:
        return result
    home = fetch.get(site)
    if home is None:
        result["site_status"] = "unreachable"
        return result
    host = urlparse(site).netloc
    soup = BeautifulSoup(home, "html.parser")
    if re.search(r"domain (is )?(parked|for sale)|under construction|coming soon", soup.get_text(" "), re.I) and len(soup.select("a[href]")) < 3:
        result["site_status"] = "parked"
        return result
    # Likely contact pages on the same site, in the order the menus list them; a team page is
    # often linked only from the contact page, so pages found on those pages count too.
    def contact_links(base: str, page: BeautifulSoup) -> list[str]:
        out = []
        for a in page.select("a[href]"):
            url = urljoin(base, a["href"]).split("#")[0]
            if urlparse(url).netloc == host and CONTACT_PAGE.search(a.get_text(" ") + " " + a["href"]):
                out.append(url)
        return out

    pages = [(site, soup)]
    queue = contact_links(site, soup)
    done = {site}
    while queue and len(pages) < MAX_PAGES:
        url = queue.pop(0)
        if url in done:
            continue
        done.add(url)
        page = fetch.get(url)
        if page:
            parsed = BeautifulSoup(page, "html.parser")
            pages.append((url, parsed))
            queue += contact_links(url, parsed)
    emails: list[str] = []
    for url, s in pages:
        for net, link in socials_in(s, url).items():
            result[net] = result[net] or link
        result["site_phones"] += [p for p in phones_in(s) if p not in result["site_phones"]]
        emails += [e for e in emails_in(s) if e not in emails]
    result["emails"] = rank(emails, record.get("domain") or host.removeprefix("www."))
    result["site_status"] = "ok" if emails or any(result[n] for n in SOCIAL) else "no contacts"
    return result


def rank(emails: list[str], domain: str) -> list[str]:
    """The business's own domain first, then a person's address before a shared inbox."""
    return sorted(dict.fromkeys(emails), key=lambda e: (not e.endswith("@" + domain), is_role(e)))


ROLE = re.compile(r"^(info|hello|office|contact|bookings?|admin|sales|support|team|mail|enquiries|inquiries|reception|help|service)@", re.I)


def is_role(email: str) -> bool:
    """A shared inbox (info@, hello@) rather than a person."""
    return bool(ROLE.match(email))


def apply(records: list[dict], fetch: Fetcher) -> dict:
    """Enrich every record in place; returns counts for the run summary."""
    counts = {"sites_visited": 0, "emails_found": 0, "socials_found": 0}
    cache: dict[str, dict] = {}
    for r in records:
        site = r.get("website") or ""
        if site and site not in cache:
            cache[site] = enrich(r, fetch)
            counts["sites_visited"] += 1
        found = cache.get(site) or enrich({}, fetch)
        emails = rank(([r["email"]] if r.get("email") else []) + found["emails"], r.get("domain", ""))
        r["email"] = emails[0] if emails else ""
        r["other_emails"] = "; ".join(emails[1:])
        for net in SOCIAL:
            r[net] = found[net]
        extra = [p for p in found["site_phones"] if p != r.get("phone")]
        if not r.get("phone") and extra:
            r["phone"], r["phone_display"] = extra[0], phone_pretty(extra[0])
            extra = extra[1:]
        r["other_phones"] = "; ".join(phone_pretty(p) for p in extra)
        r["site_status"] = found["site_status"]
        counts["emails_found"] += bool(found["emails"])
        counts["socials_found"] += any(found[n] for n in SOCIAL)
    return counts
