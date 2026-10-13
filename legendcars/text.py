"""Tekstnormalisatie zodat de regex'en in watchlist.toml voorspelbaar werken."""

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9.]+")
_LOOSE_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_SPACES = re.compile(r"\s+")


def normalize(*parts: str | None) -> str:
    """Kleine letters, zonder accenten, leestekens -> spatie. Een punt tussen cijfers blijft ("2.8")."""
    text = " ".join(p for p in parts if p)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = _NON_ALNUM.sub(" ", text)
    text = _LOOSE_DOT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def parse_int(value) -> int | None:
    """'116.303 km' -> 116303, '03-1999' is niet de bedoeling (gebruik parse_year)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def parse_year(value) -> int | None:
    """Haalt een jaartal (1900-2099) uit '03-1999', '1999', '1999-03-01'."""
    if value is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group(0)) if m else None
