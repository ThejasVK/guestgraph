"""Normalization and hashing of personal identifiers.

Ad platforms (Meta Custom Audiences, Google Customer Match, The Trade Desk) match on
SHA-256 hashes of *normalized* identifiers. If two systems normalize differently, the
hashes differ and the match silently fails, so normalization is the part that has to be
exactly right.
"""

from __future__ import annotations

import hashlib
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def normalize_email(raw: str | None) -> str | None:
    """Lowercase and trim. For Gmail, drop dots and +tags in the local part (they route to
    the same inbox). Returns None when the value isn't a usable email."""
    if not raw:
        return None
    email = raw.strip().lower()
    if not _EMAIL_RE.match(email):
        return None
    local, domain = email.split("@", 1)
    if domain in _GMAIL_DOMAINS:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def normalize_phone(raw: str | None, default_country_code: str = "1") -> str | None:
    """Return E.164 digits without the plus sign (e.g. 15512353720).

    Ten-digit numbers are assumed to be in the default country (US/Canada)."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("00"):
        digits = digits[2:]
    if len(digits) == 10:
        digits = default_country_code + digits
    if not 11 <= len(digits) <= 15:
        return None
    return digits


def sha256(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hashed_email(raw: str | None) -> str | None:
    return sha256(normalize_email(raw))


def hashed_phone(raw: str | None) -> str | None:
    return sha256(normalize_phone(raw))
