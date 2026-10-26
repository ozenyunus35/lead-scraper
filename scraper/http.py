"""A polite HTTP fetcher: robots.txt, a delay between requests, retries, one session."""
from __future__ import annotations

import time
import urllib.robotparser
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
        """Return the page HTML, or None if robots.txt disallows it or it keeps failing."""
        if not self.allowed(url):
            self.skipped.append(url)
            return None
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                r.encoding = r.encoding or "utf-8"
                self.pages += 1
                return r.text
            except requests.RequestException:
                if attempt == self.retries:
                    self.skipped.append(url)
                    return None
                time.sleep(self.delay * 2 ** attempt)  # back off before retrying
        return None
