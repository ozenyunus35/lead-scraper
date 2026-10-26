"""Build the synthetic business directory that the demo scraper crawls.

Everything here is invented: phone numbers use the reserved 555-01xx range and
websites use the reserved .example domain. The data is deliberately messy, like
real directories: mixed phone formats, missing websites, and businesses listed
under two categories (duplicates the scraper has to merge).
"""
from __future__ import annotations

import html
import random
import shutil
import sys
from pathlib import Path

rnd = random.Random(2026)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "site/directory")
PER_PAGE = 10

CATEGORIES = {
    "restaurants": ("Restaurants", ["Bistro", "Kitchen", "Grill", "Trattoria", "Noodle Bar", "Taqueria"]),
    "dentists": ("Dentists", ["Dental Care", "Family Dentistry", "Smile Studio", "Dental Clinic"]),
    "plumbers": ("Plumbers", ["Plumbing", "Pipe & Drain", "Plumbing Co.", "Rooter Service"]),
    "accountants": ("Accountants", ["Accounting", "Tax & Advisory", "CPA Group", "Bookkeeping"]),
    "fitness": ("Fitness", ["Fitness Club", "Yoga Studio", "CrossFit", "Pilates"]),
    "real-estate": ("Real Estate", ["Realty", "Properties", "Real Estate Group", "Homes"]),
}
NAMES = ["Harbor", "Golden Gate", "Bayview", "Mission", "Sunset", "Pacific", "Union", "Market Street", "Presidio",
         "Marina", "Nob Hill", "Castro", "Dogpatch", "Embarcadero", "Twin Peaks", "Hayes", "Fillmore", "Ocean",
         "Lakeside", "Redwood", "Cedar", "Summit", "Bridgeview", "Northpoint", "Cypress", "Alameda"]
STREETS = ["Market St", "Mission St", "Valencia St", "Geary Blvd", "Irving St", "Divisadero St", "Columbus Ave",
           "Polk St", "Fillmore St", "Clement St", "Haight St", "24th St", "Folsom St", "Bryant St"]
CITIES = [("San Francisco", "CA", "941"), ("Oakland", "CA", "946"), ("Berkeley", "CA", "947"), ("Daly City", "CA", "940")]


def phone_variants(area: str, line: str) -> str:
    """Same number, written the way different people type it."""
    n = f"555-01{line}"
    return rnd.choice([
        f"({area}) {n}",
        f"{area}.{n.replace('-', '.')}",
        f"+1 {area} {n.replace('-', ' ')}",
        f"{area}-{n}",
        f"1-{area}-{n}",
    ])


def make_businesses() -> list[dict]:
    seen: set[str] = set()
    out = []
    used_numbers: set[tuple[str, str]] = set()
    for i in range(138):
        slug_cat = list(CATEGORIES)[i % len(CATEGORIES)]
        label, suffixes = CATEGORIES[slug_cat]
        while True:
            name = f"{rnd.choice(NAMES)} {rnd.choice(suffixes)}"
            if name not in seen:
                seen.add(name)
                break
        city, state, zip3 = rnd.choice(CITIES)
        area = {"San Francisco": "415", "Oakland": "341", "Berkeley": "510", "Daly City": "650"}[city]
        while True:  # every business gets its own number
            line = f"{rnd.randint(0, 99):02d}"
            if (area, line) not in used_numbers:
                used_numbers.add((area, line))
                break
        slug = name.lower().replace("&", "and").replace(".", "").replace(" ", "-")
        domain = slug.replace("-", "") + ".example"
        out.append({
            "slug": slug,
            "name": name,
            "categories": [slug_cat],
            "street": f"{rnd.randint(10, 4999)} {rnd.choice(STREETS)}" + (f", Suite {rnd.randint(100, 450)}" if rnd.random() < 0.25 else ""),
            "city": city,
            "state": state,
            "zip": f"{zip3}{rnd.randint(10, 99)}",
            "area": area,
            "line": line,
            "website": f"https://www.{domain}" if rnd.random() < 0.8 else "",
            "email": f"hello@{domain}" if rnd.random() < 0.55 else "",
            "rating": round(rnd.uniform(3.2, 5.0), 1),
            "reviews": rnd.randint(4, 640),
        })
    # Some businesses are listed under a second category, e.g. a gym that also does physio.
    for b in rnd.sample(out, 16):
        other = rnd.choice([c for c in CATEGORIES if c not in b["categories"]])
        b["categories"].append(other)
    # And some are listed twice as separate entries, with a slightly different name
    # and their phone written another way. Same phone number = same business.
    for b in rnd.sample(out[:120], 12):
        dup = dict(b)
        dup["name"] = b["name"] + rnd.choice([" LLC", " Inc.", " (Main Office)", " & Co"])
        dup["slug"] = b["slug"] + "-listing-2"
        dup["categories"] = [rnd.choice([c for c in CATEGORIES if c not in b["categories"]])]
        dup["website"] = "" if rnd.random() < 0.5 else b["website"]
        dup["email"] = ""
        out.append(dup)
    return out


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Bay Area Business Directory (demo)</title>
<style>
body{{font-family:Georgia,serif;max-width:860px;margin:0 auto;padding:16px;color:#222;background:#fdfcf8}}
header{{border-bottom:3px double #b8860b;margin-bottom:16px}} header a{{color:#222;text-decoration:none}}
.demo{{background:#fff3cd;border:1px solid #e0c36b;padding:8px 12px;font:14px/1.4 system-ui,sans-serif}}
.listing{{border-bottom:1px solid #ddd;padding:12px 0}} .listing h2{{margin:0;font-size:20px}}
.meta{{color:#555;font-size:15px}} nav.pager a{{margin-right:12px}} footer{{margin-top:24px;color:#777;font-size:13px}}
</style></head><body>
<header><h1><a href="{root}index.html">Bay Area Business Directory</a></h1></header>
<p class="demo">Demo site with invented businesses, built to show web scraping safely. Phone numbers use the fictional 555-01xx range.</p>
{body}
<footer>Fictional data · for scraping demos only</footer>
</body></html>"""


def write(path: Path, title: str, body: str, root: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.format(title=html.escape(title), body=body, root=root), encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    biz = make_businesses()
    by_cat = {c: [b for b in biz if c in b["categories"]] for c in CATEGORIES}

    items = "".join(
        f'<li><a href="{c}/page-1.html">{html.escape(CATEGORIES[c][0])}</a> ({len(by_cat[c])})</li>' for c in CATEGORIES
    )
    write(OUT / "index.html", "Categories", f"<h2>Browse by category</h2><ul class='categories'>{items}</ul>", "")

    for c, members in by_cat.items():
        members = sorted(members, key=lambda b: b["name"])
        pages = [members[i:i + PER_PAGE] for i in range(0, len(members), PER_PAGE)]
        for n, chunk in enumerate(pages, 1):
            rows = "".join(
                f"""<article class="listing"><h2><a href="../biz/{b['slug']}.html">{html.escape(b['name'])}</a></h2>
<div class="meta"><span class="addr">{html.escape(b['street'])}, {b['city']}</span> · <span class="tel">{phone_variants(b['area'], b['line'])}</span>
· <span class="stars">★ {b['rating']}</span></div></article>"""
                for b in chunk
            )
            nav = ""
            if n > 1:
                nav += f'<a rel="prev" href="page-{n - 1}.html">← Previous</a>'
            if n < len(pages):
                nav += f'<a rel="next" href="page-{n + 1}.html">Next →</a>'
            body = f"<h2>{CATEGORIES[c][0]} <small>page {n} of {len(pages)}</small></h2>{rows}<nav class='pager'>{nav}</nav>"
            write(OUT / c / f"page-{n}.html", f"{CATEGORIES[c][0]} page {n}", body, "../")

    for b in biz:
        cats = ", ".join(f'<a href="../{c}/page-1.html">{CATEGORIES[c][0]}</a>' for c in b["categories"])
        web = f'<dt>Website</dt><dd><a class="website" href="{b["website"]}">{b["website"].removeprefix("https://")}</a></dd>' if b["website"] else ""
        mail = f'<dt>Email</dt><dd><a class="email" href="mailto:{b["email"]}">{b["email"]}</a></dd>' if b["email"] else ""
        body = f"""<article class="business" itemscope itemtype="https://schema.org/LocalBusiness">
<h2 itemprop="name">{html.escape(b['name'])}</h2>
<p class="categories">{cats}</p>
<dl>
<dt>Address</dt><dd class="address" itemprop="address">{html.escape(b['street'])}<br>{b['city']}, {b['state']} {b['zip']}</dd>
<dt>Phone</dt><dd class="phone" itemprop="telephone">{phone_variants(b['area'], b['line'])}</dd>
{web}{mail}
<dt>Rating</dt><dd class="rating">{b['rating']} ({b['reviews']} reviews)</dd>
</dl></article>"""
        write(OUT / "biz" / f"{b['slug']}.html", b["name"], body, "../")

    print(f"directory: {len(biz)} businesses, {sum(len(v) for v in by_cat.values())} listings -> {OUT}")


if __name__ == "__main__":
    main()
