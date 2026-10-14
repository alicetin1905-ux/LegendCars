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


_NL_MONTHS = {"jan": 1, "feb": 2, "mrt": 3, "mar": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8,
              "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dec": 12}
_RELATIVE = {"vandaag": 0, "heute": 0, "today": 0, "gisteren": 1, "gestern": 1, "yesterday": 1, "eergisteren": 2}


def parse_date(value, today=None) -> str | None:
    """'Vandaag', 'Gisteren', '30 sep 26', '09.10.2026', 'Heute, 20:33', ISO -> 'YYYY-MM-DD'."""
    import datetime as _dt

    if not value:
        return None
    today = today or _dt.date.today()
    v = str(value).strip().lower()
    first = re.split(r"[ ,]", v)[0]
    if first in _RELATIVE:
        return (today - _dt.timedelta(days=_RELATIVE[first])).isoformat()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", v)
    if m:
        return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    m = re.match(r"(\d{1,2}) ([a-z]{3})\.? '?(\d{2,4})", v)
    if m and m.group(2) in _NL_MONTHS:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        return _dt.date(y, _NL_MONTHS[m.group(2)], int(m.group(1))).isoformat()
    return None
