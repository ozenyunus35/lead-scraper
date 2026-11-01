"""Normalising and de-duplicating scraped records."""
from __future__ import annotations

import re

import phonenumbers


def phone_e164(raw: str, region: str = "US") -> str:
    """'(415) 555-0134', '415.555.0134', '+1 415 555 0134' -> '+14155550134'. Empty if unparseable."""
    try:
        n = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return ""
    if not phonenumbers.is_possible_number(n):
        return ""
    return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)


def phone_pretty(e164: str) -> str:
    if not e164:
        return ""
    return phonenumbers.format_number(phonenumbers.parse(e164), phonenumbers.PhoneNumberFormat.NATIONAL)


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


SUFFIXES = {"llc", "inc", "co", "corp", "corporation", "ltd", "the", "and", "company", "pc", "pllc"}


def name_tokens(name: str) -> list[str]:
    """'The Harbor Grill, LLC (Main Office)' -> ['harbor', 'grill']."""
    name = re.sub(r"\([^)]*\)", " ", (name or "").lower()).replace("&", " and ")
    return [t for t in re.findall(r"[a-z0-9]+", name) if t not in SUFFIXES]


def same_name(a: str, b: str) -> bool:
    """Close enough to be one business: one name contains the other once suffixes are dropped."""
    ta, tb = set(name_tokens(a)), set(name_tokens(b))
    return bool(ta and tb) and (ta <= tb or tb <= ta)


def place_key(record: dict) -> str:
    return "".join(name_tokens(record.get("name", ""))) + ":" + (record.get("zip") or record.get("city", "").lower())


def dedupe(records: list[dict], merge_fields: tuple[str, ...] = ("category",)) -> tuple[list[dict], int]:
    """Merge records that describe the same business. Returns (records, duplicates_removed).

    The same phone number with a matching name is one business (a shared switchboard with a
    different name is not). A listing without a phone joins the listing with the same name and
    ZIP, with or without a phone."""
    groups: list[dict] = []
    by_phone: dict[str, list[dict]] = {}
    by_place: dict[str, dict] = {}

    def merge(kept: dict, r: dict) -> None:
        filled = lambda d: sum(1 for v in d.values() if v not in ("", None))
        base, extra = (r, dict(kept)) if filled(r) > filled(kept) else (dict(kept), r)
        for f in merge_fields:
            values = [v for v in (base.get(f, "") + "; " + extra.get(f, "")).split("; ") if v]
            base[f] = "; ".join(dict.fromkeys(values))
        for f, v in extra.items():  # fill gaps from the duplicate
            if v not in ("", None) and base.get(f) in ("", None):
                base[f] = v
        kept.clear()
        kept.update(base)

    # Listings with a phone first, so a phone-less copy can find its match whatever the order.
    for r in sorted(records, key=lambda r: not r.get("phone")):
        r = dict(r)
        match = None
        if r.get("phone"):
            match = next((g for g in by_phone.get(r["phone"], []) if same_name(g["name"], r.get("name", ""))), None)
        else:
            match = by_place.get(place_key(r))
        if match is None:
            groups.append(r)
            match = r
            if r.get("phone"):
                by_phone.setdefault(r["phone"], []).append(match)
        else:
            merge(match, r)
        by_place.setdefault(place_key(r), match)
    return groups, len(records) - len(groups)
