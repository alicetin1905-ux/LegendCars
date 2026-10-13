"""Locatie van een advertentie (coördinaten, postcode of gemeente) en afstand tot thuis.

De postcodetabel komt uit GeoNames (CC-BY 4.0, https://www.geonames.org/) en staat
compact in legendcars/geodata/postcodes.json.gz. Opnieuw opbouwen:

    python -m legendcars.geo <map met BE.txt, NL.txt, ...>
"""

from __future__ import annotations

import gzip
import json
import math
import re
import statistics
import sys
from functools import lru_cache
from pathlib import Path

from .text import normalize

DATA_FILE = Path(__file__).resolve().parent / "geodata" / "postcodes.json.gz"
COUNTRIES = ["BE", "NL", "DE", "LU", "FR", "AT", "IT", "ES"]
# Bronnen gebruiken verschillende landcodes (AutoScout24 "B"/"BE", Kleinanzeigen "D" ...): alles naar ISO
COUNTRY_ISO = {"B": "BE", "D": "DE", "A": "AT", "E": "ES", "F": "FR", "I": "IT", "L": "LU"}
MAX_NAME_SPREAD = 0.5  # graden; gemeentenamen die verder uiteen liggen zijn dubbelzinnig


def iso(country: str | None) -> str | None:
    return COUNTRY_ISO.get(country, country) if country else None


def norm_postcode(country: str, code: str | None) -> str | None:
    if not code:
        return None
    code = re.sub(r"\s+", "", str(code)).upper()
    if country == "NL":
        code = code[:4]  # "8401 DT" -> "8401"
    return code or None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _table() -> dict:
    if not DATA_FILE.exists():
        return {"codes": {}, "names": {}}
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def locate(country: str | None, postcode: str | None = None, city: str | None = None,
           lat: float | None = None, lon: float | None = None) -> tuple[float, float] | None:
    """Beste schatting van de coördinaten: exacte coördinaten > postcode > gemeentenaam."""
    if lat and lon:
        return round(float(lat), 3), round(float(lon), 3)
    cc = iso(country)
    if not cc:
        return None
    t = _table()
    code = norm_postcode(cc, postcode)
    if code and code in t["codes"].get(cc, {}):
        return tuple(t["codes"][cc][code])
    if city:
        names = t["names"].get(cc, {})
        name = normalize(city)
        if name in names:
            return tuple(names[name])
        first = name.split(" ")[0]  # "Bonn Stadt", "Düren Nord" ...
        if first in names:
            return tuple(names[first])
    return None


def build(src_dir: Path, out: Path = DATA_FILE) -> dict:
    codes: dict[str, dict[str, list[float]]] = {}
    names: dict[str, dict[str, list[tuple[float, float]]]] = {}
    pc_points: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for cc in COUNTRIES:
        path = Path(src_dir) / cc / f"{cc}.txt"
        if not path.exists():
            path = Path(src_dir) / f"{cc}.txt"
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < 11 or not f[9] or not f[10]:
                    continue
                lat, lon = float(f[9]), float(f[10])
                code = norm_postcode(cc, f[1])
                if code:
                    pc_points.setdefault((cc, code), []).append((lat, lon))
                if f[2]:
                    names.setdefault(cc, {}).setdefault(normalize(f[2]), []).append((lat, lon))
    for (cc, code), pts in pc_points.items():
        codes.setdefault(cc, {})[code] = [round(statistics.fmean(p[0] for p in pts), 3),
                                         round(statistics.fmean(p[1] for p in pts), 3)]
    clean_names: dict[str, dict[str, list[float]]] = {}
    for cc, by_name in names.items():
        for name, pts in by_name.items():
            lats = [p[0] for p in pts]
            lons = [p[1] for p in pts]
            if max(lats) - min(lats) > MAX_NAME_SPREAD or max(lons) - min(lons) > MAX_NAME_SPREAD:
                continue
            clean_names.setdefault(cc, {})[name] = [round(statistics.fmean(lats), 3), round(statistics.fmean(lons), 3)]
    data = {"source": "GeoNames postal codes, CC-BY 4.0", "codes": codes, "names": clean_names}
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), sort_keys=True)
    _table.cache_clear()
    return data


if __name__ == "__main__":
    d = build(Path(sys.argv[1]))
    print({cc: len(v) for cc, v in d["codes"].items()}, {cc: len(v) for cc, v in d["names"].items()}, DATA_FILE)
