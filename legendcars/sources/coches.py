"""Coches.net (Spanje). Zoeken per merk met bouwjaarfilter; daarna matcht matching.py per model.

Eén merkpagina wordt per run maar één keer opgehaald, ook als er meerdere modellen van dat merk zijn.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from dataclasses import replace

from ..config import Model, Settings
from ..http import Fetcher
from ..listing import Listing, norm_fuel
from ..text import normalize
from . import SearchResult

log = logging.getLogger(__name__)

BASE = "https://www.coches.net"
SOURCE = "coches"
MAKE_SLUGS = {"Alfa Romeo": "alfa_romeo"}  # standaard: kleine letters, spaties -> "-"
BODY_IDS = {2: "coupe", 3: "cabrio"}
_PROPS = re.compile(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.*?)"\);', re.S)

_cache: dict[tuple[str, int], tuple[list[Listing], bool, list[str]]] = {}


def make_slug(make: str) -> str:
    return MAKE_SLUGS.get(make, re.sub(r"\s+", "-", make.strip().lower()))


def build_url(slug: str, max_year: int, page: int) -> str:
    params = {"MaxYear": max_year}
    if page > 1:
        params["pg"] = page
    return f"{BASE}/{slug}/segunda-mano/?{urllib.parse.urlencode(params)}"


def parse_page(html: str) -> dict:
    m = _PROPS.search(html)
    if not m:
        raise ValueError("Geen __INITIAL_PROPS__ gevonden (layout gewijzigd of geblokkeerd?)")
    return json.loads(json.loads('"' + m.group(1) + '"'))["initialResults"]


def parse_item(item: dict) -> Listing:
    loc = item.get("location") or {}
    return Listing(
        id=f"{SOURCE}:{item['id']}",
        source=SOURCE,
        url=BASE + item.get("url", ""),
        title=(item.get("title") or "").strip(),
        year=item.get("year"),
        km=item.get("km") or None,
        price=item.get("price") or None,
        price_type="FIXED",
        fuel=norm_fuel(item.get("fuelType")),
        body=BODY_IDS.get(item.get("bodyTypeId")),
        hp=item.get("hp") or None,
        country="E",
        city=loc.get("cityLiteral") or loc.get("mainProvince"),
        seller="dealer" if item.get("isProfessional") else "private",
        image=item.get("imgUrl") or item.get("img"),
    )


def _get_with_retry(url: str, fetcher: Fetcher, attempts: int = 3) -> dict:
    """Coches.net geeft af en toe een pagina zonder data terug; even wachten en opnieuw proberen helpt."""
    for attempt in range(attempts):
        try:
            return parse_page(fetcher.get(url))
        except ValueError:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def _fetch_make(make: str, settings: Settings, fetcher: Fetcher) -> tuple[list[Listing], bool, list[str]]:
    slug = make_slug(make)
    max_year = settings.max_year or 2100
    key = (slug, max_year)
    if key in _cache:
        return _cache[key]
    listings: list[Listing] = []
    errors: list[str] = []
    complete = True
    want = normalize(make).split(" ")[0]
    for page in range(1, settings.coches_max_pages + 1):
        url = build_url(slug, max_year, page)
        try:
            res = _get_with_retry(url, fetcher)
        except Exception as e:  # noqa: BLE001
            log.warning("Coches.net %s pagina %s: %s", make, page, e)
            errors.append(f"{url}: {e}")
            complete = False
            break
        items = res.get("items") or []
        # Onbekende merk-URL -> coches.net toont alle merken. Dat willen we niet doorzoeken.
        if items and not any(want in normalize(i.get("make")) for i in items):
            errors.append(f"{url}: merk-URL '{slug}' klopt niet")
            complete = False
            break
        listings.extend(parse_item(i) for i in items)
        if page >= int(res.get("totalPages") or 1):
            break
        if page == settings.coches_max_pages:
            complete = False
    _cache[key] = (listings, complete, errors)
    return _cache[key]


def search(model: Model, settings: Settings, fetcher: Fetcher) -> SearchResult:
    listings, complete, errors = _fetch_make(model.make, settings, fetcher)
    result = SearchResult(source=SOURCE, model_id=model.id, complete=complete, errors=list(errors))
    for listing in listings:
        if listing.year is None or model.years[0] <= listing.year <= model.years[1]:
            result.listings.append(replace(listing, model_id=model.id))
    return result
