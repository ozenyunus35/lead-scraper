"""Command line: python -m scraper directory|books [--url URL] [--out DIR] [--max-pages N] [--delay S]"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import changes, enrich, quality
from .clean import dedupe
from .export import write_crm_csv, write_csv, write_json, write_xlsx
from .http import Fetcher
from .sites import books, directory

SITES = {
    "directory": (directory, "https://ozenyunus35.github.io/lead-scraper/directory/index.html", "Business leads"),
    "books": (books, "https://books.toscrape.com/catalogue/page-1.html", "Books"),
}


def main(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(prog="scraper", description="Polite scraper with clean CSV/Excel output.")
    p.add_argument("site", choices=SITES)
    p.add_argument("--url", help="start URL (defaults to the public demo)")
    p.add_argument("--out", default="data", help="output folder")
    p.add_argument("--max-pages", type=int, default=None, help="limit listing pages per category")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    p.add_argument("--report-url", help="public start URL to show in the output when crawling a local copy")
    p.add_argument("--no-enrich", action="store_true", help="skip visiting each business's website for contacts")
    p.add_argument("--previous", help="last run's JSON, to report what opened, closed or changed since")
    a = p.parse_args(argv)

    module, default_url, label = SITES[a.site]
    start = a.url or default_url
    fetch = Fetcher(delay=a.delay)
    t0 = time.monotonic()
    rows = module.scrape(start, fetch, a.max_pages)
    removed = 0
    fields = list(module.FIELDS)
    extra: dict = {}
    if a.site == "directory":
        rows, removed = dedupe(rows)
        rows.sort(key=lambda r: (r["category"].split(";")[0], r["name"]))
        if not a.no_enrich:
            extra.update(enrich.apply(rows, fetch))
        quality.apply(rows)
        fields[fields.index("email") + 1:fields.index("email") + 1] = ["email_status", "other_emails", "linkedin", "facebook", "instagram", "x", "other_phones", "site_status"]
        fields.insert(fields.index("name") + 1, "score")

    if a.report_url:  # crawled a local copy of a site that is published at report_url
        base_local, base_public = start.rsplit("/", 1)[0], a.report_url.rsplit("/", 1)[0]
        for r in rows:
            for f in ("source_url", "url", "website"):
                if isinstance(r.get(f), str):
                    r[f] = r[f].replace(base_local, base_public)
        start = a.report_url

    if not rows:
        # The site was down or changed beyond recognition: writing an empty file would replace
        # the last good results with nothing. Fail instead, so the schedule keeps the old data.
        print(f"{label}: no records found at {start} ({fetch.pages} pages fetched, {len(fetch.skipped)} skipped); nothing written")
        raise SystemExit(1)

    if a.site == "directory":  # after the URLs are public, so they match last run's
        previous = None
        if a.previous and Path(a.previous).exists():
            try:
                last = json.loads(Path(a.previous).read_text(encoding="utf-8"))
                # A run from before change tracking stored other fields: start afresh from it.
                previous = last["rows"] if "changes" in last.get("meta", {}) else None
            except (ValueError, KeyError, TypeError, AttributeError):
                previous = None
        extra["changes"] = changes.compare(rows, previous, datetime.now(timezone.utc).date().isoformat())
        fields += ["change", "changes", "first_seen"]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "dataset": label,
        "source": start,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_s": round(time.monotonic() - t0, 1),
        "pages_fetched": fetch.pages,
        "records": len(rows),
        "duplicates_removed": removed,
        "skipped_urls": len(fetch.skipped),
        **extra,
    }
    write_csv(rows, fields, out / f"{a.site}.csv")
    write_xlsx(rows, fields, out / f"{a.site}.xlsx", label)
    write_json(rows, fields, meta, out / f"{a.site}.json")
    if a.site == "directory":
        write_crm_csv(rows, out / f"{a.site}-crm.csv")
    print(f"{label}: {len(rows)} records, {removed} duplicates merged, {fetch.pages} pages in {meta['duration_s']}s -> {out}/")
    return meta


if __name__ == "__main__":
    main()
