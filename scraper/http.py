"""A polite HTTP fetcher: robots.txt, a delay between requests, retries, one session."""
from __future__ import annotations

import re
import time
import urllib.robotparser
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "LeadScraperDemo/1.0 (+https://github.com/ozenyunus35/lead-scraper)"


class Fetcher:
    def __init__(self, delay: float = 1.0, retries: int = 3, timeout: float = 20.0):
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last = 0.0
        self.pages = 0
        self.skipped: list[str] = []
        self.seen: set[str] = set()

    def allowed(self, url: str) -> bool:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(urljoin(origin, "/robots.txt"), timeout=self.timeout)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[origin] = rp
                else:
                    self._robots[origin] = None  # no robots.txt: everything allowed
            except requests.RequestException:
                self._robots[origin] = None
        rp = self._robots[origin]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        """Return the page HTML, or None if robots.txt disallows it, it was already fetched, or it keeps failing."""
        url = url.split("#", 1)[0]
        if url in self.seen:  # a "next" link that points back: never fetch the same page twice
            return None
        self.seen.add(url)
        if not self.allowed(url):
            self.skipped.append(url)
            return None
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            retry_after = None
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    retry_after = self._retry_after(r.headers.get("Retry-After"))
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                if r.status_code in (401, 403, 404, 410):  # retrying will not change the answer
                    self.skipped.append(url)
                    return None
                r.raise_for_status()
                kind = r.headers.get("Content-Type", "text/html").lower()
                if "html" not in kind and "xml" not in kind:
                    self.skipped.append(url)
                    return None
                self.pages += 1
                return self._decode(r, kind)
            except requests.RequestException:
                if attempt == self.retries:
                    self.skipped.append(url)
                    return None
                # Back off before retrying: what the server asked for, else 1 s, 2 s, 4 s... at least.
                time.sleep(retry_after if retry_after is not None else max(self.delay, 0.5) * 2 ** attempt)
        return None

    def _retry_after(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            return min(float(value), 120.0)
        except ValueError:
            try:
                return max(0.0, min(120.0, parsedate_to_datetime(value).timestamp() - time.time()))
            except (TypeError, ValueError):
                return None

    @staticmethod
    def _decode(r: requests.Response, kind: str) -> str:
        """requests falls back to Latin-1 when the header names no charset, which garbles UTF-8 pages.
        Use the header, else the page's own <meta charset>, else UTF-8; Windows-1252 if that fails."""
        m = re.search(r"charset=[\"']?([\w.:-]+)", kind) or re.search(rb"<meta[^>]+charset=[\"']?([\w.:-]+)", r.content[:4096], re.I)
        names = [m.group(1).decode() if m and isinstance(m.group(1), bytes) else (m.group(1) if m else "utf-8"), "utf-8"]
        for name in names:
            try:
                return r.content.decode(name)
            except (LookupError, UnicodeDecodeError):
                continue
        return r.content.decode("cp1252", "replace")
