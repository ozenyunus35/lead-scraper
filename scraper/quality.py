"""E-mail checks and a lead score, without sending anything or calling a paid service.

Each address gets a status a sales team can act on:
  personal     a named person at the business's own domain: the best address to write to
  role         a shared inbox (info@, hello@): fine, but reaches whoever reads it
  free-mail    a Gmail/Yahoo/Outlook address: real small businesses use them, worth a check
  disposable   a throwaway inbox service: do not use
  invalid      not a deliverable address as written

The score (0-100) ranks leads by how much a salesperson can do with them.
"""
from __future__ import annotations

import re

from .enrich import is_role

SYNTAX = re.compile(r"^(?!\.)(?!.*\.\.)[a-z0-9._%+-]{1,64}(?<!\.)@(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$", re.I)
FREE = {"gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "aol.com", "icloud.com", "me.com", "proton.me", "protonmail.com", "gmx.com", "yandex.com", "mail.com"}
DISPOSABLE = {"mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com", "temp-mail.org", "yopmail.com", "trashmail.com", "sharklasers.com", "getnada.com", "dispostable.com", "maildrop.cc", "throwawaymail.com"}


def email_status(email: str) -> str:
    if not email:
        return ""
    email = email.strip().lower()
    if not SYNTAX.match(email):
        return "invalid"
    domain = email.rsplit("@", 1)[1]
    if domain in DISPOSABLE:
        return "disposable"
    if domain in FREE:
        return "free-mail"
    return "role" if is_role(email) else "personal"


def score(r: dict) -> int:
    """How useful the lead is: ways to reach it (40), contact quality (25), reputation (20), completeness (15)."""
    status = r.get("email_status", "")
    reach = 15 * bool(r.get("phone")) + 15 * (status in ("personal", "role", "free-mail")) + 10 * bool(r.get("website") and r.get("site_status") not in ("unreachable", "parked"))
    contact = {"personal": 20, "role": 10, "free-mail": 8}.get(status, 0) + 5 * any(r.get(n) for n in ("linkedin", "facebook", "instagram", "x"))
    try:
        rating, reviews = float(r.get("rating") or 0), int(r.get("reviews") or 0)
    except (TypeError, ValueError):
        rating, reviews = 0.0, 0
    reputation = round(10 * max(0.0, min(1.0, (rating - 3) / 2)) + 10 * min(1.0, reviews / 300))
    filled = sum(bool(r.get(f)) for f in ("street", "city", "zip", "category"))
    return min(100, reach + contact + reputation + round(15 * filled / 4))


def apply(records: list[dict]) -> None:
    for r in records:
        r["email_status"] = email_status(r.get("email", ""))
        r["score"] = score(r)
