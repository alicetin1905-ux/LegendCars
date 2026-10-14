"""Kleinanzeigen.de (Duitsland, vooral particulieren). Resultaten staan als <article data-adid=...> in de HTML."""

from __future__ import annotations

import html as htmllib
import json
import logging
import re
import urllib.parse

from ..config import Model, Settings
from ..http import Fetcher
from ..listing import Listing
from ..text import normalize, parse_date, parse_int
from . import SearchResult

log = logging.getLogger(__name__)

BASE = "https://www.kleinanzeigen.de"
SOURCE = "kleinanzeigen"
CARS_CATEGORY = "c216"

_ARTICLE_SPLIT = re.compile(r"(?=<article [^>]*data-adid=)")
_ADID = re.compile(r'data-adid="(\d+)"')
_HREF = re.compile(r'data-href="([^"]+)"')
_LDJSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_STRIP = re.compile(r"<script.*?</script>|<svg.*?</svg>", re.S)
_TEXT = re.compile(r">([^<]+)<")
_PRICE = re.compile(r"^([\d.]+)\s*€(\s*VB)?$")
_KM = re.compile(r"^([\d.]+)\s*km$")
_DATE = re.compile(r"^(Heute|Gestern|\d{2}\.\d{2}\.\d{4})")
_EZ = re.compile(r"^EZ\s*(\d{1,2})/(\d{4})$")
_PLZ = re.compile(r"^(\d{5})\s+(.+)$")
_TOTAL = re.compile(r"([\d.]+)\s*Ergebnisse")
_AUTOMATIC = re.compile(r"\bautomatik|\bautomatic|\bautomaat|\btiptronic|\bsteptronic")
_MANUAL = re.compile(r"\bschaltgetriebe|\bschalter\b|\bhandschalter|\bmanuell|\b[56] ?gang")


def build_url(query: str, model: Model, page: int) -> str:
    slug = urllib.parse.quote(re.sub(r"\s+", "-", query.strip().lower()))
    page_part = f"seite:{page}/" if page > 1 else ""
    years = f"autos.ez_i:{model.years[0]}%2C{model.years[1]}"
    return f"{BASE}/s-autos/{page_part}{slug}/k0{CARS_CATEGORY}+{years}"


def _body_from_title(title: str) -> str | None:
    t = normalize(title)
    if re.search(r"cabrio|roadster|spider|spyder|barchetta", t):
        return "cabrio"
    if re.search(r"\bcoupe\b", t):
        return "coupe"
    return None


def parse_article(chunk: str) -> Listing | None:
    chunk = chunk.split("</article>")[0]
    adid = _ADID.search(chunk)
    href = _HREF.search(chunk)
    if not adid or not href:
        return None
    meta = {}
    for raw in _LDJSON.findall(chunk):
        try:
            meta = json.loads(raw)
            break
        except json.JSONDecodeError:
            continue
    texts = [htmllib.unescape(t).strip() for t in _TEXT.findall(_STRIP.sub("", chunk))]
    texts = [t for t in texts if t]

    price = km = year = None
    price_type = "UNKNOWN"
    city = plz = posted = old_price = None
    for t in texts:
        if price is None and (m := _PRICE.match(t)):
            price = parse_int(m.group(1))
            price_type = "MIN_BID" if m.group(2) else "FIXED"  # VB = Verhandlungsbasis
        elif price is not None and old_price is None and (m := _PRICE.match(t)):
            old_price = parse_int(m.group(1))  # doorstreepte vroegere prijs
        elif posted is None and _DATE.match(t):
            posted = parse_date(t)
        elif km is None and (m := _KM.match(t)):
            km = parse_int(m.group(1))
        elif year is None and (m := _EZ.match(t)):
            year = int(m.group(2))
        elif city is None and (m := _PLZ.match(t)):
            plz, city = m.group(1), m.group(2)

    title = (meta.get("title") or "").strip()
    if not title:
        title = next((t for t in texts if len(t) > 12 and not _PLZ.match(t)), "")
    description = (meta.get("description") or "")[:500]
    full = normalize(title, description)
    gearbox = "automatic" if _AUTOMATIC.search(full) else "manual" if _MANUAL.search(full) else None
    return Listing(
        id=f"{SOURCE}:{adid.group(1)}",
        source=SOURCE,
        url=BASE + href.group(1),
        title=title,
        description=description,
        year=year,
        km=km or None,
        price=price or None,
        price_type=price_type,
        gearbox=gearbox,
        body=_body_from_title(title),
        country="D",
        city=city,
        postcode=plz,
        posted=posted,
        old_price=old_price if old_price and price and old_price > price else None,
        image=meta.get("contentUrl"),
    )


def parse_page(html: str) -> tuple[list[Listing], int | None]:
    listings = []
    for chunk in _ARTICLE_SPLIT.split(html)[1:]:
        listing = parse_article(chunk)
        if listing is not None:
            listings.append(listing)
    total = _TOTAL.search(html)
    return listings, parse_int(total.group(1)) if total else None


def search(model: Model, settings: Settings, fetcher: Fetcher) -> SearchResult:
    result = SearchResult(source=SOURCE, model_id=model.id)
    seen: set[str] = set()
    for query in model.query:
        fetched = 0
        for page in range(1, settings.kleinanzeigen_max_pages + 1):
            url = build_url(query, model, page)
            try:
                listings, total = parse_page(fetcher.get(url))
            except Exception as e:  # noqa: BLE001
                log.warning("Kleinanzeigen %s '%s': %s", model.id, query, e)
                result.errors.append(f"{url}: {e}")
                result.complete = False
                break
            fetched += len(listings)
            for listing in listings:
                if listing.id not in seen:
                    seen.add(listing.id)
                    listing.model_id = model.id
                    result.listings.append(listing)
            if not listings or total is None or fetched >= total:
                break
            if page == settings.kleinanzeigen_max_pages:
                result.complete = False
    return result
