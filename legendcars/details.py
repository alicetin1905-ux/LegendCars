"""Detailpagina's van de beste kandidaten ophalen: volledige beschrijving en staat-signalen.

Enkel afgeleide gegevens worden bewaard (staat-score, redenen, publicatiedatum, eigenaars,
views). De beschrijving zelf niet: die bevat vaak telefoonnummers en namen.
"""

from __future__ import annotations

import html as htmllib
import json
import logging
import re
from datetime import date

from . import geo
from .condition import assess
from .config import Watchlist
from .http import Fetcher
from .text import parse_date, parse_int

log = logging.getLogger(__name__)

REFRESH_DAYS = 30
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
_TAGS = re.compile(r"<[^>]+>")


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(_TAGS.sub(" ", html or ""))).strip()


def _next_data(html: str) -> dict:
    m = _NEXT_DATA.search(html)
    if not m:
        raise ValueError("Geen __NEXT_DATA__")
    return json.loads(m.group(1))["props"]["pageProps"]


def _flatten(o, out: list[str]) -> list[str]:
    if isinstance(o, dict):
        for v in o.values():
            _flatten(v, out)
    elif isinstance(o, list):
        for v in o:
            _flatten(v, out)
    elif isinstance(o, str):
        out.append(o)
    return out


def parse_autoscout24(html: str) -> dict:
    ld = _next_data(html)["listingDetails"]
    v = ld.get("vehicle") or {}
    cond = ((v.get("rawData") or {}).get("condition")) or {}
    owners = None
    owners_raw = (cond.get("numberOfPreviousOwners") or {}) if isinstance(cond.get("numberOfPreviousOwners"), dict) else {}
    if owners_raw.get("raw") is not None:
        owners = parse_int(owners_raw.get("raw"))
    accident_free = ((cond.get("damage") or {}).get("accidentFree"))
    if accident_free is None and v.get("hadAccident") is not None:
        accident_free = not v.get("hadAccident")
    facts = " ".join(_flatten(cond, []))
    return {
        "text": _strip(ld.get("description") or "") + " " + facts,
        "posted": parse_date(ld.get("createdTimestampWithOffset")),
        "owners": owners,
        "accident_free": accident_free,
    }


def parse_adevinta(html: str) -> dict:
    m = re.search(r"window\.__CONFIG__\s*=\s*(\{.*?\});\s*(?:window\.|</script>)", html, re.S)
    listing = json.loads(m.group(1)).get("listing", {}) if m else {}
    d = re.search(r'data-collapsable="description"[^>]*>(.*?)</div>', html, re.S)
    stats = listing.get("stats") or {}
    car = listing.get("carDetails") or {}
    text = _strip(d.group(1)) if d else ""
    if car.get("carPassUrl"):
        text += " car-pass"
    if car.get("hasNapStatus"):
        text += " nap"
    return {
        "text": text,
        "posted": parse_date(stats.get("since")),
        "views": stats.get("viewCount"),
        "favs": stats.get("favoritedCount"),
    }


def parse_kleinanzeigen(html: str) -> dict:
    d = re.search(r'id="viewad-description-text"[^>]*>(.*?)</p>', html, re.S)
    details = re.findall(r'<li class="addetailslist--detail">\s*(.*?)<span class="addetailslist--detail--value"[^>]*>(.*?)</span>',
                         html, re.S)
    facts = {_strip(k): _strip(v) for k, v in details}
    posted = re.search(r'id="viewad-extra-info".*?(\d{2}\.\d{2}\.\d{4})', html, re.S)
    state = facts.get("Fahrzeugzustand", "")
    accident_free = True if "Unbesch" in state else False if "Besch" in state else None
    return {
        "text": (_strip(d.group(1)) if d else "") + " " + " ".join(f"{k} {v}" for k, v in facts.items()),
        "posted": parse_date(posted.group(1)) if posted else None,
        "accident_free": accident_free,
    }


def parse_willhaben(html: str) -> dict:
    ad = _next_data(html).get("advertDetails") or {}
    attrs = {a["name"]: (a.get("values") or [None])[0] for a in (ad.get("attributes") or {}).get("attribute", [])}
    text = _strip(attrs.get("DESCRIPTION") or ad.get("description") or "")
    if attrs.get("CONDITION_REPORT") == "Ja":
        text += f" pickerl bis {attrs.get('CONDITION_REPORT_VALID_UNTIL', '')}"
    owners = parse_int(attrs.get("NUMBER_OF_OWNERS") or attrs.get("PREVIOUS_OWNERS"))
    return {
        "text": text,
        "posted": parse_date(ad.get("firstPublishedDate") or ad.get("publishedDate")),
        "owners": owners,
    }


PARSERS = {
    "autoscout24": parse_autoscout24,
    "2dehands": parse_adevinta,
    "marktplaats": parse_adevinta,
    "kleinanzeigen": parse_kleinanzeigen,
    "willhaben": parse_willhaben,
}


def to_detail(parsed: dict, today: str) -> dict:
    cond = assess(parsed.get("text", ""), parsed.get("owners"), parsed.get("accident_free"))
    out = {"fetched": today, "cond": cond.to_dict()}
    for k in ("posted", "owners", "views", "favs"):
        if parsed.get(k) is not None:
            out[k] = parsed[k]
    return out


def candidates(records: list[dict], wl: Watchlist, today: str) -> list[dict]:
    """Actieve advertenties binnen de standaardfilters van het dashboard zonder (recente) details."""
    d = wl.dashboard
    pmin, pmax = d.get("price_min") or 0, d.get("price_max") or 10**9
    max_km = d.get("max_km") or 10**9
    home = (d.get("home_lat"), d.get("home_lon"))
    max_dist = d.get("max_distance_km")
    model_ids = {m.id for m in wl.models}
    cutoff = date.fromordinal(date.fromisoformat(today).toordinal() - REFRESH_DAYS).isoformat()
    out = []
    for r in records:
        if not r.get("active") or r["source"] not in PARSERS or r.get("model_id") not in model_ids:
            continue
        if not r.get("price") or not (pmin <= r["price"] <= pmax) or (r.get("km") or 0) > max_km:
            continue
        if (r.get("detail") or {}).get("fetched", "") >= cutoff:
            continue
        if max_dist and home[0] is not None:
            loc = geo.locate(r.get("country"), r.get("postcode"), r.get("city"), r.get("lat"), r.get("lon"))
            if loc is None or geo.haversine_km(home[0], home[1], *loc) > max_dist:
                continue
        out.append(r)
    out.sort(key=lambda r: r.get("first_seen", ""), reverse=True)  # nieuwste eerst
    return out


def enrich(records: list[dict], wl: Watchlist, fetcher: Fetcher, today: str, limit: int = 800) -> dict:
    todo = candidates(records, wl, today)[:limit]
    stats = {"todo": len(todo), "ok": 0, "failed": 0, "gone": 0}
    for i, r in enumerate(todo, 1):
        try:
            parsed = PARSERS[r["source"]](fetcher.get(r["url"]))
        except Exception as e:  # noqa: BLE001 - verwijderde advertentie, layout gewijzigd, ...
            code = getattr(e, "code", None)
            if code in (404, 410):
                stats["gone"] += 1
                r["detail"] = {"fetched": today, "gone": True}
            else:
                stats["failed"] += 1
                log.warning("Details %s: %s", r["url"], e)
            continue
        r["detail"] = to_detail(parsed, today)
        stats["ok"] += 1
        if i % 50 == 0:
            print(f"  details {i}/{len(todo)}", flush=True)
    return stats
