"""Build the synthetic business directory that the demo scraper crawls.

Everything here is invented: phone numbers use the reserved 555-01xx range and
websites use the reserved .example domain. The data is deliberately messy, like
real directories: mixed phone formats, missing websites, and businesses listed
under two categories (duplicates the scraper has to merge).

Each business with a website also gets one (under web/<domain>/): a home page, a
contact page and sometimes a team page, written the many ways small businesses
write them, with the traps a contact finder meets on real sites.

The directory changes from day to day like a real one: every day since START one
business closes, one opens and one changes its details, so a daily run has news.
Usage: python demo_directory/generate.py [OUT] [YYYY-MM-DD]
"""
from __future__ import annotations

import html
import random
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

rnd = random.Random(2026)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "site/directory")
TODAY = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime.now(timezone.utc).date()
START = date(2026, 11, 1)  # the directory as first published; each later day brings a few changes
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
# Each city with its own streets, real ZIP range and area code, so an address reads like a real one.
CITIES = [
    ("San Francisco", "CA", "415", range(94102, 94135), ["Market St", "Mission St", "Valencia St", "Geary Blvd", "Irving St",
     "Divisadero St", "Columbus Ave", "Polk St", "Fillmore St", "Clement St", "Haight St", "24th St"]),
    ("Oakland", "CA", "510", range(94601, 94622), ["Broadway", "Telegraph Ave", "Grand Ave", "College Ave", "Lakeshore Ave",
     "Piedmont Ave", "International Blvd"]),
    ("Berkeley", "CA", "510", range(94702, 94711), ["Shattuck Ave", "University Ave", "San Pablo Ave", "Solano Ave",
     "Ashby Ave", "Telegraph Ave"]),
    ("Daly City", "CA", "650", range(94014, 94018), ["Mission St", "Geneva Ave", "Westlake Ave", "Southgate Ave",
     "John Daly Blvd", "Skyline Blvd"]),
]
# Second listings only where a business really does both: a realtor that also does
# property tax returns, a tax office that also handles property sales.
RELATED = {"accountants": "real-estate", "real-estate": "accountants"}


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


def new_business(r: random.Random, slug_cat: str, seen: set[str], used_numbers: set[tuple[str, str]]) -> dict:
    label, suffixes = CATEGORIES[slug_cat]
    for attempt in range(200):
        name = f"{r.choice(NAMES)} {r.choice(suffixes)}" + ("" if attempt < 100 else f" {r.choice(['North', 'West', 'Two', 'East'])}")
        if name not in seen:
            seen.add(name)
            break
    city, state, area, zips, streets = r.choice(CITIES)
    while True:  # every business gets its own number
        line = f"{r.randint(0, 99):02d}"
        if (area, line) not in used_numbers:
            used_numbers.add((area, line))
            break
    slug = name.lower().replace("&", "and").replace(".", "").replace(" ", "-")
    domain = slug.replace("-", "") + ".example"
    return {
            "slug": slug,
            "name": name,
            "categories": [slug_cat],
            "street": f"{r.randint(10, 4999)} {r.choice(streets)}" + (f", Suite {r.randint(100, 450)}" if r.random() < 0.25 else ""),
            "city": city,
            "state": state,
            "zip": str(r.choice(zips)),
            "area": area,
            "line": line,
            "website": f"https://www.{domain}" if r.random() < 0.8 else "",
            "email": f"hello@{domain}" if r.random() < 0.55 else "",
            "rating": round(r.uniform(3.2, 5.0), 1),
            "reviews": r.randint(4, 640) if r.random() < 0.85 else r.randint(1000, 2600),
    }


def make_businesses() -> list[dict]:
    seen: set[str] = set()
    out = []
    used_numbers: set[tuple[str, str]] = set()
    for i in range(138):
        out.append(new_business(rnd, list(CATEGORIES)[i % len(CATEGORIES)], seen, used_numbers))
    # A few businesses are listed under a second category that fits what they do.
    for b in rnd.sample([b for b in out if b["categories"][0] in RELATED], 6):
        b["categories"].append(RELATED[b["categories"][0]])
    # The days since the directory was first published: one closes, one opens, one changes.
    for day in range((TODAY - START).days):
        r = random.Random(f"day-{START + timedelta(days=day + 1)}")
        out.remove(r.choice(out))
        out.append(new_business(r, r.choice(list(CATEGORIES)), seen, used_numbers))
        b = r.choice(out)
        change = r.choice(["phone", "rating", "address"])
        if change == "phone":  # a new number
            while True:
                line = f"{r.randint(0, 99):02d}"
                if (b["area"], line) not in used_numbers:
                    used_numbers.add((b["area"], line))
                    b["line"] = line
                    break
        elif change == "rating":
            b["reviews"] += r.randint(3, 40)
            b["rating"] = round(min(5.0, max(3.0, b["rating"] + r.choice([-0.1, 0.1, 0.2]))), 1)
        else:  # moved down the road
            b["street"] = f"{r.randint(10, 4999)} " + b["street"].split(" ", 1)[1].split(",")[0]
    # And some are listed twice as separate entries, with a slightly different name
    # and their phone written another way. Same phone number = same business.
    for b in random.Random(f"dups-{TODAY}").sample(out, 12):
        dup = dict(b)
        dup["name"] = b["name"] + rnd.choice([" LLC", " Inc.", " (Main Office)", " & Co"])
        dup["slug"] = b["slug"] + "-listing-2"
        dup["categories"] = list(b["categories"])  # the same business, entered again in its own category
        dup["website"] = "" if len(b["slug"]) % 2 else b["website"]
        dup["email"] = ""
        dup["no_phone"] = rnd.random() < 0.4  # some copies leave the phone out: name and ZIP still match
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


FIRST = ["Maria", "James", "Aiko", "Daniel", "Priya", "Lucas", "Sofia", "Omar", "Grace", "Mateo", "Hannah", "Wei"]
LAST = ["Lopez", "Chen", "Patel", "Nguyen", "Okafor", "Russo", "Kim", "Silva", "Novak", "Haddad", "Brooks", "Tanaka"]
SITE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><link rel="icon" href="data:,">
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:0 auto;padding:16px;color:#1f2937}}
nav a{{margin-right:14px}} footer{{margin-top:32px;border-top:1px solid #ddd;padding-top:12px;font-size:14px;color:#555}}
.demo{{background:#eef2ff;padding:6px 10px;font-size:13px}}</style></head><body>
<p class="demo">Fictional demo website for the Lead Scraper project.</p>
<header><strong>{name}</strong><nav>{nav}</nav></header>
<main>{body}</main><footer>{footer}</footer></body></html>"""


def website(b: dict) -> dict[str, str]:
    """The business's own site: pages by file name. Written the many ways small businesses
    do it, with the traps a contact finder meets: obfuscated addresses, an image named like
    an e-mail, a template placeholder, a contact form with no address at all, a dead site."""
    r = random.Random("site-" + b["website"])
    domain = b["website"].removeprefix("https://www.")
    handle = domain.removesuffix(".example")
    kind = r.choices(["mailto", "footer-text", "obfuscated", "form-only", "team", "dead", "parked"], [30, 15, 12, 10, 18, 8, 7])[0]
    if kind == "dead":
        return {}  # the link in the directory leads nowhere: 404
    if kind == "parked":
        return {"index.html": SITE.format(title=domain, name=domain, nav="", footer="", body="<h1>This domain is parked</h1><p>Interested in this domain? Contact the registrar.</p>")}
    first, last = r.choice(FIRST), r.choice(LAST)
    personal = f"{first.lower()}.{last.lower()}@{domain}"
    role = r.choice(["info", "hello", "office", "contact", "bookings"]) + "@" + domain
    socials = []
    for net, url in [("Instagram", f"https://www.instagram.com/{handle}/"), ("Facebook", f"https://www.facebook.com/{handle}"),
                     ("LinkedIn", f"https://www.linkedin.com/company/{handle}/"), ("X", f"https://x.com/{handle}")]:
        if r.random() < 0.55:
            socials.append(f'<a href="{url}" aria-label="{net}">{net}</a>')
    footer = " · ".join(socials) + f'<br>© 2026 {html.escape(b["name"])} · <img src="img/logo@2x.png" alt="" width="1" height="1">'
    if kind == "footer-text":
        footer += f"<br>Questions? Write to {role}"
    if kind == "obfuscated":
        footer += f"<br>Email: {role.replace('@', ' [at] ').replace('.example', ' [dot] example')}"
    contact_link = r.choice(["Contact", "Contact us", "Get in touch"])
    nav = f'<a href="index.html">Home</a><a href="about.html">About</a><a href="contact.html">{contact_link}</a>'
    pages = {
        "index.html": SITE.format(title=b["name"], name=html.escape(b["name"]), nav=nav, footer=footer,
                                  body=f"<h1>Welcome to {html.escape(b['name'])}</h1><p>Serving {b['city']} since {r.randint(1985, 2022)}.</p>"
                                       "<p>Template text: replace you@example.com with your address.</p>"),
        "about.html": SITE.format(title="About", name=html.escape(b["name"]), nav=nav, footer=footer,
                                  body=f"<h1>About us</h1><p>A local {CATEGORIES[b['categories'][0]][0].lower()} business in {b['city']}.</p>"),
    }
    tel = f"({b['area']}) 555-01{b['line']}"
    contact = f'<h1>{contact_link}</h1><p>Call <a href="tel:+1{b["area"]}55501{b["line"]}">{tel}</a>.</p>'
    if kind == "mailto":
        contact += f'<p>Email <a href="mailto:{role}?subject=Hello">{role}</a></p>'
    if kind == "form-only":
        contact += '<form><label>Your email <input type="email" placeholder="name@example.com"></label><button>Send</button></form>'
    if kind == "team":
        contact += f'<p>General enquiries: <a href="mailto:{role}">{role}</a></p>'
        nav += '<a href="team.html">Our team</a>'
        pages["team.html"] = SITE.format(title="Team", name=html.escape(b["name"]), nav=nav, footer=footer,
                                         body=f"<h1>Our team</h1><p><strong>{first} {last}</strong>, owner. "
                                              f'Reach {first} directly at <a href="mailto:{personal}">{personal}</a>.</p>')
    pages["contact.html"] = SITE.format(title="Contact", name=html.escape(b["name"]), nav=nav, footer=footer, body=contact)
    return pages


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
<div class="meta"><span class="addr">{html.escape(b['street'])}, {b['city']}</span> · <span class="tel">{'' if b.get('no_phone') else phone_variants(b['area'], b['line'])}</span>
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
        # The website link leads to the business's own (demo) site, served next to the directory.
        domain = b["website"].removeprefix("https://www.")
        web = f'<dt>Website</dt><dd><a class="website" href="../web/{domain}/index.html">www.{domain}</a></dd>' if b["website"] else ""
        mail = f'<dt>Email</dt><dd><a class="email" href="mailto:{b["email"]}">{b["email"]}</a></dd>' if b["email"] else ""
        body = f"""<article class="business" itemscope itemtype="https://schema.org/LocalBusiness">
<h2 itemprop="name">{html.escape(b['name'])}</h2>
<p class="categories">{cats}</p>
<dl>
<dt>Address</dt><dd class="address" itemprop="address">{html.escape(b['street']).replace(', Suite', '<br>Suite')}<br>{b['city']}, {b['state']} {b['zip']}</dd>
{'' if b.get('no_phone') else f"<dt>Phone</dt><dd class='phone' itemprop='telephone'>{phone_variants(b['area'], b['line'])}</dd>"}
{web}{mail}
<dt>Rating</dt><dd class="rating">{b['rating']} ({b['reviews']:,} reviews)</dd>
</dl></article>"""
        write(OUT / "biz" / f"{b['slug']}.html", b["name"], body, "../")

    sites = 0
    for b in {b["website"]: b for b in biz if b["website"] and not b["slug"].endswith("-listing-2")}.values():
        for name, page in website(b).items():
            (OUT / "web" / b["website"].removeprefix("https://www.") / name).parent.mkdir(parents=True, exist_ok=True)
            (OUT / "web" / b["website"].removeprefix("https://www.") / name).write_text(page, encoding="utf-8")
            sites += name == "index.html"

    print(f"directory ({TODAY}): {len(biz)} businesses, {sites} websites, {sum(len(v) for v in by_cat.values())} listings -> {OUT}")


if __name__ == "__main__":
    main()
