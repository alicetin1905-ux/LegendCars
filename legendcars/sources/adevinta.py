"""2dehands.be en Marktplaats.nl delen hetzelfde platform en dezelfde zoek-API."""

from __future__ import annotations

import logging
import urllib.parse

from ..config import Model, Settings
from ..http import Fetcher
from ..listing import Listing, norm_body, norm_fuel, norm_gearbox
from ..text import parse_int, parse_year
from . import SearchResult

log = logging.getLogger(__name__)

SITES = {
    "2dehands": "https://www.2dehands.be",
    "marktplaats": "https://www.marktplaats.nl",
}
CARS_CATEGORY = 91
PAGE_SIZE = 100
PRICED_TYPES = {"FIXED", "MIN_BID"}
COUNTRIES = {"belgie": "B", "belgië": "B", "nederland": "NL", "duitsland": "D", "frankrijk": "F", "luxemburg": "L"}


def build_url(site: str, query: str, model: Model, offset: int) -> str:
    params = [
        ("query", query),
        ("l1CategoryId", CARS_CATEGORY),
        ("limit", PAGE_SIZE),
        ("offset", offset),
        ("attributeRanges[]", f"constructionYear:{model.years[0]}:{model.years[1]}"),
        ("sortBy", "SORT_INDEX"),
        ("sortOrder", "DECREASING"),
    ]
    return f"{SITES[site]}/lrp/api/search?{urllib.parse.urlencode(params)}"


def parse_listing(raw: dict, site: str) -> Listing:
    attrs = {a["key"]: a.get("value") for a in raw.get("attributes", [])}
    price_info = raw.get("priceInfo") or {}
    price_type = price_info.get("priceType", "")
    cents = price_info.get("priceCents") or 0
    price = cents // 100 if price_type in PRICED_TYPES and cents > 0 else None
    loc = raw.get("location") or {}
    country = loc.get("countryName") or ""
    pictures = raw.get("pictures") or []
    image = pictures[0].get("mediumUrl") if pictures else None
    if not image and raw.get("imageUrls"):
        image = "https:" + raw["imageUrls"][0] if raw["imageUrls"][0].startswith("//") else raw["imageUrls"][0]
    km = parse_int(attrs.get("mileage"))
    return Listing(
        id=f"{site}:{raw['itemId']}",
        source=site,
        url=SITES[site] + raw.get("vipUrl", ""),
        title=raw.get("title", "").strip(),
        description=(raw.get("description") or "")[:500],
        year=parse_year(attrs.get("constructionYear")),
        km=km if km else None,  # 0 km betekent bij particulieren meestal "niet ingevuld"
        price=price,
        price_type=price_type or "UNKNOWN",
        fuel=norm_fuel(attrs.get("fuel")),
        gearbox=norm_gearbox(attrs.get("transmission")),
        body=norm_body(attrs.get("body")),
        country=COUNTRIES.get(country.lower(), country or None),
        city=loc.get("cityName"),
        lat=loc.get("latitude") or None,
        lon=loc.get("longitude") or None,
        seller=None,
        image=image,
        extra={"carpass": attrs.get("carPassUrl")} if attrs.get("carPassUrl") else {},
    )


def search(model: Model, settings: Settings, fetcher: Fetcher, site: str) -> SearchResult:
    result = SearchResult(source=site, model_id=model.id)
    seen: set[str] = set()
    for query in model.query:
        offset = 0
        for page in range(settings.adevinta_max_pages):
            url = build_url(site, query, model, offset)
            try:
                data = fetcher.get_json(url)
            except Exception as e:  # noqa: BLE001
                log.warning("%s %s '%s': %s", site, model.id, query, e)
                result.errors.append(f"{url}: {e}")
                result.complete = False
                break
            listings = data.get("listings", [])
            for raw in listings:
                try:
                    listing = parse_listing(raw, site)
                except Exception as e:  # noqa: BLE001
                    result.errors.append(f"parse {raw.get('itemId')}: {e}")
                    continue
                if listing.id not in seen:
                    seen.add(listing.id)
                    listing.model_id = model.id
                    result.listings.append(listing)
            total = int(data.get("totalResultCount") or 0)
            offset += PAGE_SIZE
            if offset >= total or not listings:
                break
            if page == settings.adevinta_max_pages - 1:
                result.complete = False
    return result
