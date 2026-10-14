"""AutoScout24 (BE/NL/DE/LU/FR/AT/IT/ES) via de JSON die in elke resultaatpagina zit (__NEXT_DATA__)."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse

from ..config import As24Search, Model, Settings
from ..http import Fetcher
from ..listing import Listing, norm_fuel, norm_gearbox
from ..text import parse_int, parse_year
from . import SearchResult

log = logging.getLogger(__name__)

BASE = "https://www.autoscout24.be"
SOURCE = "autoscout24"
BODY_CODES = {2: "cabrio", 3: "coupe"}
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
_HP = re.compile(r"(\d+)\s*PK", re.I)


def build_url(search: As24Search, model: Model, countries: list[str], page: int) -> str:
    params = {
        "atype": "C",
        "ustate": "N,U",
        "cy": ",".join(countries),
        "mmmv": search.mmmv,
        "fregfrom": model.years[0],
        "fregto": model.years[1],
        "sort": "age",
        "desc": "1",
        "page": page,
    }
    if search.body:
        params["body"] = ",".join(str(b) for b in search.body)
    return f"{BASE}/nl/lst?{urllib.parse.urlencode(params)}"


def parse_page(html: str) -> dict:
    m = _NEXT_DATA.search(html)
    if not m:
        raise ValueError("Geen __NEXT_DATA__ gevonden (layout gewijzigd of geblokkeerd?)")
    return json.loads(m.group(1))["props"]["pageProps"]


def parse_listing(raw: dict, body_hint: str | None = None) -> Listing:
    v = raw.get("vehicle", {})
    tracking = raw.get("tracking", {})
    loc = raw.get("location", {})
    seller = raw.get("seller", {}) or {}
    details = {d.get("iconName"): d.get("data") for d in raw.get("vehicleDetails", [])}
    hp = None
    if details.get("speedometer"):
        m = _HP.search(details["speedometer"])
        hp = int(m.group(1)) if m else None
    price = (raw.get("price") or {}).get("priceRaw")
    old_price = parse_int((raw.get("superDeal") or {}).get("oldPriceFormatted"))
    images = raw.get("images") or []
    title = " ".join(x for x in [v.get("make"), v.get("model")] if x)
    return Listing(
        id=f"{SOURCE}:{raw['id']}",
        source=SOURCE,
        url=BASE + raw.get("url", ""),
        title=title,
        subtitle=(v.get("modelVersionInput") or v.get("variant") or "").strip(),
        year=parse_year(tracking.get("firstRegistration") or details.get("calendar")),
        km=parse_int(tracking.get("mileage")) if tracking.get("mileage") else parse_int(v.get("mileageInKm")),
        price=int(price) if price else None,
        price_type="FIXED",
        fuel=norm_fuel(v.get("fuel")),
        gearbox=norm_gearbox(v.get("transmission")),
        body=body_hint,
        hp=hp,
        country=loc.get("countryCode"),
        city=(loc.get("city") or "").title() or None,
        postcode=loc.get("zip"),
        old_price=old_price if old_price and price and old_price > int(price) else None,
        seller="dealer" if seller.get("type") == "Dealer" else "private" if seller.get("type") else None,
        image=images[0] if images else None,
    )


def _run(search_spec: As24Search, model: Model, countries: list[str], settings: Settings, fetcher: Fetcher,
         result: SearchResult, seen: set[str], split: bool) -> None:
    body_hint = BODY_CODES.get(search_spec.body[0]) if len(search_spec.body) == 1 else None
    page = 1
    while True:
        url = build_url(search_spec, model, countries, page)
        try:
            pp = parse_page(fetcher.get(url))
        except Exception as e:  # noqa: BLE001 - één mislukte pagina mag de run niet stoppen
            log.warning("AutoScout24 %s pagina %s: %s", model.id, page, e)
            result.errors.append(f"{url}: {e}")
            result.complete = False
            return
        pages = int(pp.get("numberOfPages") or 1)
        if page == 1 and split and pages > settings.as24_max_pages and len(countries) > 1:
            # AutoScout24 toont max. 20 pagina's: te veel resultaten -> per land opnieuw zoeken
            for country in countries:
                _run(search_spec, model, [country], settings, fetcher, result, seen, split=False)
            return
        for raw in pp.get("listings", []):
            if raw.get("isOcs") or raw.get("searchResultSection", "Main") != "Main":
                continue  # gesponsorde/aanbevolen blokken buiten de zoekopdracht
            try:
                listing = parse_listing(raw, body_hint)
            except Exception as e:  # noqa: BLE001
                result.errors.append(f"parse {raw.get('id')}: {e}")
                continue
            if listing.id not in seen:
                seen.add(listing.id)
                listing.model_id = model.id
                result.listings.append(listing)
        if page >= pages:
            return
        if page >= settings.as24_max_pages:
            result.complete = False  # niet alles opgehaald
            return
        page += 1


def search(model: Model, settings: Settings, fetcher: Fetcher) -> SearchResult:
    result = SearchResult(source=SOURCE, model_id=model.id)
    seen: set[str] = set()
    for s in model.as24:
        _run(s, model, settings.as24_countries, settings, fetcher, result, seen, split=True)
    return result
