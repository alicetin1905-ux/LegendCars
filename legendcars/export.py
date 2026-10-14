"""Bouwt het dashboard: één zelfstandig HTML-bestand met de data erin (werkt ook offline / dubbelklikken)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from dataclasses import fields

from . import geo
from .condition import assess
from .config import ROOT, Watchlist
from .listing import Listing
from .market import analyse
from .matching import match
from .store import Store

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
DEFAULT_OUTPUT = ROOT / "docs" / "index.html"
SOURCE_PRIORITY = {"autoscout24": 0, "2dehands": 1, "marktplaats": 2, "kleinanzeigen": 3, "willhaben": 4, "coches": 5}


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


def display_title(title: str, subtitle: str) -> str:
    """AutoScout24: titel = "BMW Z4", ondertitel vaak "BMW Z4 M Coupé ..." -> geen herhaling."""
    title, subtitle = (title or "").strip(), (subtitle or "").strip()
    if not subtitle:
        return title
    if subtitle.lower().startswith(title.lower()):
        return subtitle
    make = title.split(" ")[0].lower() if title else ""
    if make and subtitle.lower().startswith(make):
        return subtitle
    return f"{title} {subtitle}"


def _compact(r: dict, today: date, moves: dict | None = None) -> dict:
    first = r.get("first_seen")
    detail = r.get("detail") or {}
    posted = detail.get("posted") or r.get("posted")
    since = min(x for x in [posted, first] if x) if (posted or first) else None
    mv = (moves or {}).get(r["id"], {})
    top = max(x for x in [mv.get("max"), r.get("old_price"), r.get("first_price"), r["price"]] if x)
    drop = top - r["price"] if top > r["price"] else 0
    loc = geo.locate(r.get("country"), r.get("postcode"), r.get("city"), r.get("lat"), r.get("lon"))
    return {
        "id": r["id"],
        "src": r["source"],
        "url": r["url"],
        "title": display_title(r.get("title"), r.get("subtitle")),
        "model": r["model_id"],
        "year": r.get("year"),
        "km": r.get("km"),
        "price": r["price"],
        "pt": r.get("price_type"),
        "fuel": r.get("fuel"),
        "gear": r.get("gearbox"),
        "body": r.get("body"),
        "hp": r.get("hp"),
        "cc": geo.iso(r.get("country")),
        "lat": round(loc[0], 2) if loc else None,
        "lon": round(loc[1], 2) if loc else None,
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
        "posted": posted,
        "days": (today - date.fromisoformat(since)).days if since else None,
        "drop": drop,
        "dropPct": round(drop / top, 3) if drop else 0,
        "changed": mv.get("changed") if drop else None,
        "cond": r.get("cond"),
        "owners": detail.get("owners"),
        "views": detail.get("views"),
        "favs": detail.get("favs"),
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
        detail = rec.get("detail") or {}
        if detail.get("cond"):
            cond = {**detail["cond"], "src": "detail"}
        else:
            c = assess(" ".join(x for x in [rec.get("title"), rec.get("subtitle"), rec.get("description")] if x))
            cond = {**c.to_dict(), "src": "lijst"}
        out.append({**rec, "variants": [[label, bonus] for label, bonus in m.variants], "flags": m.flags, "cond": cond})
    return out


def price_moves(history) -> dict[str, dict]:
    """Per advertentie: hoogste waargenomen prijs en datum van de laatste prijswijziging."""
    out: dict[str, dict] = {}
    for lid, d, price in history:
        cur = out.setdefault(lid, {"max": price, "last": price, "changed": None})
        if price != cur["last"]:
            cur["changed"] = d
        cur["max"] = max(cur["max"], price)
        cur["last"] = price
    return out


def build_data(watchlist: Watchlist, store: Store, today: date | None = None) -> dict:
    today = today or date.today()
    records = rematch(list(store.records.values()), watchlist)
    history = list(store.history())
    rows, stats = analyse(records, watchlist, history)
    moves = price_moves(history)
    rows = dedupe(rows)
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "defaults": watchlist.dashboard,
        "models": stats,
        "listings": [_compact(r, today, moves) for r in rows],
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
