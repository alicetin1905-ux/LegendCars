"""Willhaben.at (Oostenrijk): zoekresultaten staan als JSON in __NEXT_DATA__."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse

from ..config import Model, Settings
from ..http import Fetcher
from ..listing import Listing, norm_body, norm_fuel, norm_gearbox
from ..text import parse_int
from . import SearchResult

log = logging.getLogger(__name__)

BASE = "https://www.willhaben.at"
SOURCE = "willhaben"
SEARCH = BASE + "/iad/gebrauchtwagen/auto/gebrauchtwagenboerse"
ROWS = 90
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def build_url(query: str, model: Model, page: int) -> str:
    params = {
        "keyword": query,
        "YEAR_MODEL_FROM": model.years[0],
        "YEAR_MODEL_TO": model.years[1],
        "rows": ROWS,
        "page": page,
    }
    return f"{SEARCH}?{urllib.parse.urlencode(params)}"


def parse_page(html: str) -> dict:
    m = _NEXT_DATA.search(html)
    if not m:
        raise ValueError("Geen __NEXT_DATA__ gevonden (layout gewijzigd of geblokkeerd?)")
    return json.loads(m.group(1))["props"]["pageProps"]["searchResult"]


def parse_advert(ad: dict) -> Listing:
    attrs = {a["name"]: (a.get("values") or [None])[0] for a in ad.get("attributes", {}).get("attribute", [])}
    images = (ad.get("advertImageList") or {}).get("advertImage") or []
    kw = parse_int(attrs.get("ENGINE/EFFECT"))
    spec = attrs.get("CAR_MODEL/MODEL_SPECIFICATION") or ""
    heading = attrs.get("HEADING") or ad.get("description") or ""
    price = parse_int((attrs.get("PRICE") or "").split(".")[0])
    seller = None
    if attrs.get("ISPRIVATE") is not None:
        seller = "private" if attrs.get("ISPRIVATE") == "1" else "dealer"
    return Listing(
        id=f"{SOURCE}:{ad['id']}",
        source=SOURCE,
        url=f"{BASE}/iad/{attrs.get('SEO_URL', '')}",
        title=heading.strip(),
        subtitle=spec if spec.lower() not in heading.lower() else "",
        description=(attrs.get("BODY_DYN") or "")[:500],
        year=parse_int(attrs.get("YEAR_MODEL")),
        km=parse_int(attrs.get("MILEAGE")) or None,
        price=price or None,
        price_type="FIXED",
        fuel=norm_fuel(attrs.get("ENGINE/FUEL_RESOLVED")),
        gearbox=norm_gearbox(attrs.get("TRANSMISSION_RESOLVED")),
        body=norm_body(attrs.get("CAR_TYPE")),
        hp=round(kw * 1.36) if kw else None,
        country="A",
        city=attrs.get("LOCATION"),
        seller=seller,
        image=images[0].get("mainImageUrl") if images else None,
    )


def search(model: Model, settings: Settings, fetcher: Fetcher) -> SearchResult:
    result = SearchResult(source=SOURCE, model_id=model.id)
    seen: set[str] = set()
    for query in model.query:
        for page in range(1, settings.willhaben_max_pages + 1):
            url = build_url(query, model, page)
            try:
                sr = parse_page(fetcher.get(url))
            except Exception as e:  # noqa: BLE001
                log.warning("Willhaben %s '%s': %s", model.id, query, e)
                result.errors.append(f"{url}: {e}")
                result.complete = False
                break
            ads = (sr.get("advertSummaryList") or {}).get("advertSummary") or []
            for ad in ads:
                try:
                    listing = parse_advert(ad)
                except Exception as e:  # noqa: BLE001
                    result.errors.append(f"parse {ad.get('id')}: {e}")
                    continue
                if listing.id not in seen:
                    seen.add(listing.id)
                    listing.model_id = model.id
                    result.listings.append(listing)
            found = int(sr.get("rowsFound") or 0)
            if not ads or page * ROWS >= found:
                break
            if page == settings.willhaben_max_pages:
                result.complete = False
    return result
