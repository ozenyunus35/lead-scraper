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


def key_for(record: dict) -> str:
    """Same phone number means same business; without a phone, fall back to name + ZIP."""
    if record.get("phone"):
        return "tel:" + record["phone"]
    return "name:" + re.sub(r"[^a-z0-9]", "", record.get("name", "").lower()) + ":" + record.get("zip", "")


def dedupe(records: list[dict], merge_fields: tuple[str, ...] = ("category",)) -> tuple[list[dict], int]:
    """Merge records that describe the same business. Returns (records, duplicates_removed)."""
    out: dict[str, dict] = {}
    for r in records:
        k = key_for(r)
        if k not in out:
            out[k] = dict(r)
            continue
        kept = out[k]
        filled = lambda d: sum(1 for v in d.values() if v not in ("", None))
        if filled(r) > filled(kept):  # keep the more complete listing as the base
            kept, r = dict(r), kept
            out[k] = kept
        for f in merge_fields:
            values = [v for v in (kept.get(f, "") + "; " + r.get(f, "")).split("; ") if v]
            kept[f] = "; ".join(dict.fromkeys(values))
        for f, v in r.items():  # fill gaps from the duplicate
            if v and not kept.get(f):
                kept[f] = v
    return list(out.values()), len(records) - len(out)
