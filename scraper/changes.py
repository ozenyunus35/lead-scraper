"""What changed since the last run: businesses that opened, closed or changed their details.

Records are matched by the page they came from (a directory keeps a business's page when
its phone or address changes), else by name and ZIP. Each record gets:
  change      "new", "changed" or ""
  changes     what changed, e.g. "phone (415) 555-0123 → (415) 555-0177"
  first_seen  the date the business first appeared in a run
"""
from __future__ import annotations

from .clean import place_key

WATCHED = {"phone_display": "phone", "street": "address", "website": "website", "email": "email", "category": "category", "rating": "rating"}


def _key(r: dict) -> str:
    return r.get("source_url") or place_key(r)


def compare(current: list[dict], previous: list[dict] | None, today: str) -> dict:
    """Mark `current` in place; returns the summary ({new, changed, closed, closed_names})."""
    if previous is None:  # first run: nothing to compare with
        for r in current:
            r["change"], r["changes"], r["first_seen"] = "", "", today
        return {"new": 0, "changed": 0, "closed": 0, "closed_names": [], "compared": False}
    before = {_key(r): r for r in previous}
    before_by_place = {place_key(r): r for r in previous}
    seen: set[str] = set()
    new = changed = 0
    for r in current:
        old = before.get(_key(r)) or before_by_place.get(place_key(r))
        if old is None:
            r["change"], r["changes"], r["first_seen"] = "new", "", today
            new += 1
            continue
        seen.add(_key(old))
        diffs = []
        for field, label in WATCHED.items():
            a, b = old.get(field, ""), r.get(field, "")
            if str(a) != str(b) and (a or b):
                diffs.append(f"{label} {a or '—'} → {b or '—'}")
        r["change"] = "changed" if diffs else ""
        r["changes"] = "; ".join(diffs)
        r["first_seen"] = old.get("first_seen") or today
        changed += bool(diffs)
    closed = [r for k, r in before.items() if k not in seen]
    return {"new": new, "changed": changed, "closed": len(closed), "closed_names": sorted(r.get("name", "") for r in closed), "compared": True}
