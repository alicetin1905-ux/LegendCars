"""Bouwt het dashboard: één zelfstandig HTML-bestand met de data erin (werkt ook offline / dubbelklikken)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from dataclasses import fields

from .config import ROOT, Watchlist
from .listing import Listing
from .market import analyse
from .matching import match
from .store import Store

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
DEFAULT_OUTPUT = ROOT / "docs" / "index.html"
SOURCE_PRIORITY = {"autoscout24": 0, "2dehands": 1, "marktplaats": 2}


def _dedupe_key(r: dict):
    if not (r.get("year") and r.get("km") and r.get("price")):
        return None
    return (r["model_id"], r["year"], round(r["km"] / 1000), round(r["price"] / 250))


def dedupe(rows: list[dict]) -> list[dict]:
    """Zelfde auto op meerdere sites (vaak handelaars) -> één rij met links naar de andere bronnen."""
    rows = sorted(rows, key=lambda r: SOURCE_PRIORITY.get(r["source"], 9))
    kept: dict = {}
    out = []
    for r in rows:
        key = _dedupe_key(r)
        if key is not None and key in kept:
            kept[key].setdefault("also", []).append({"src": r["source"], "url": r["url"]})
            continue
        if key is not None:
            kept[key] = r
        out.append(r)
    return out


def _compact(r: dict, today: date) -> dict:
    first = r.get("first_seen")
    return {
        "id": r["id"],
        "src": r["source"],
        "url": r["url"],
        "title": " ".join(x for x in [r.get("title"), r.get("subtitle")] if x).strip(),
        "model": r["model_id"],
        "year": r.get("year"),
        "km": r.get("km"),
        "price": r["price"],
        "pt": r.get("price_type"),
        "fuel": r.get("fuel"),
        "gear": r.get("gearbox"),
        "body": r.get("body"),
        "hp": r.get("hp"),
        "cc": r.get("country"),
        "city": r.get("city"),
        "seller": r.get("seller"),
        "img": r.get("image"),
        "flags": r.get("flags", []),
        "variants": [label for label, _ in r.get("variants", [])],
        "tier": r.get("tier"),
        "fair": r.get("fair"),
        "comps": r.get("comps"),
        "conf": r.get("conf"),
        "rate": r.get("rate"),
        "first": first,
        "days": (today - date.fromisoformat(first)).days if first else None,
        "firstPrice": r.get("first_price"),
        "also": r.get("also", []),
    }


_LISTING_FIELDS = {f.name for f in fields(Listing)}


def rematch(records: list[dict], watchlist: Watchlist) -> list[dict]:
    """Past de huidige watchlist opnieuw toe op opgeslagen advertenties (uitvoeringen, risico's, uitsluitingen)."""
    models = {m.id: m for m in watchlist.models}
    out = []
    for rec in records:
        model = models.get(rec.get("model_id"))
        if model is None:
            continue
        m = match(Listing(**{k: v for k, v in rec.items() if k in _LISTING_FIELDS}), model, watchlist.settings)
        if m is None:
            continue
        out.append({**rec, "variants": [[label, bonus] for label, bonus in m.variants], "flags": m.flags})
    return out


def build_data(watchlist: Watchlist, store: Store, today: date | None = None) -> dict:
    today = today or date.today()
    records = rematch(list(store.records.values()), watchlist)
    rows, stats = analyse(records, watchlist, list(store.history()))
    rows = dedupe(rows)
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "defaults": watchlist.dashboard,
        "models": stats,
        "listings": [_compact(r, today) for r in rows],
    }


def render(data: dict, output: Path = DEFAULT_OUTPUT) -> Path:
    html = (DASHBOARD_DIR / "template.html").read_text(encoding="utf-8")
    for name in ("style.css", "valuation.js", "app.js"):
        html = html.replace(f"/*INLINE:{name}*/", (DASHBOARD_DIR / name).read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*INLINE:data*/null", payload)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
