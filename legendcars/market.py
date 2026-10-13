"""Marktwaarde per advertentie (vergelijkbare advertenties) en de jaarlijkse groeivoet-onderdelen.

De projectie over X jaar zelf gebeurt in het dashboard (valuation.js), zodat je daar
horizon en kosten live kunt aanpassen.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date

from .config import Model, Watchlist

MIN_COMPS = 4
MIN_REGRESSION = 12  # vanaf zoveel vergelijkbare advertenties: regressie op bouwjaar + km
KM_EFFECT_PER_10K = 0.01  # 1% marktwaarde per 10.000 km verschil met de mediaan
KM_EFFECT_CAP = 0.25
# Marktwaarde > 2x de vraagprijs is eerder een verkeerde match of een wrak dan een koopje
SUSPICIOUS_DEAL = 2.0
UNRELIABLE_FLAGS = {"Project/restauratie", "Defect", "Geen papieren", "Schade"}


def _tier(rec: dict) -> str:
    strong = [(b, label) for label, b in rec.get("variants", []) if b >= 1.5]
    return max(strong)[1] if strong else "base"


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gauss-eliminatie voor een klein stelsel (3x3)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        if abs(m[col][col]) < 1e-12:
            raise ZeroDivisionError
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


class PriceModel:
    """log(prijs) = a + b·(bouwjaar − gemiddeld) + c·(km / 100.000), met uitschieters eruit."""

    def __init__(self, comps: list[dict]):
        years = [c["year"] for c in comps if c.get("year")]
        kms = [c["km"] for c in comps if c.get("km")]
        self.year0 = statistics.fmean(years) if years else 0.0
        self.km0 = statistics.median(kms) if kms else 150_000
        self.n = len(comps)
        rows = [(self._x(c), math.log(c["price"])) for c in comps]
        self.beta = self._fit(rows)
        resid = [abs(y - self._dot(x)) for x, y in rows]
        cut = max(0.6, 2.5 * statistics.median(resid))
        kept = [r for r, e in zip(rows, resid) if e <= cut]
        if len(kept) >= MIN_REGRESSION:
            self.beta = self._fit(kept)
            self.n = len(kept)

    def _x(self, r: dict) -> list[float]:
        year = r.get("year") or self.year0
        km = r.get("km") or self.km0
        return [1.0, year - self.year0, km / 100_000]

    def _dot(self, x: list[float]) -> float:
        return sum(a * b for a, b in zip(self.beta, x))

    @staticmethod
    def _fit(rows) -> list[float]:
        ridge = [0.0, 1e-3, 1e-3]
        xtx = [[sum(x[i] * x[j] for x, _ in rows) + (ridge[i] if i == j else 0) for j in range(3)] for i in range(3)]
        xty = [sum(x[i] * y for x, y in rows) for i in range(3)]
        beta = _solve(xtx, xty)
        # km mag de prijs niet verhogen, en meer dan -60% per 100.000 km is onrealistisch
        beta[2] = max(-0.9, min(0.0, beta[2]))
        return beta

    def predict(self, r: dict) -> float:
        return math.exp(self._dot(self._x(r)))


def km_adjustment(km: int | None) -> float:
    if km is None:
        return 0.0
    if km < 50_000:
        return 1.0
    if km < 100_000:
        return 0.5
    if km > 300_000:
        return -2.0
    if km > 200_000:
        return -1.0
    return 0.0


def gearbox_adjustment(model: Model, gearbox: str | None) -> float:
    if not model.manual_premium or gearbox is None:
        return 0.0
    return 0.5 if gearbox == "manual" else -1.0


def condition_adjustment(flags: list[str]) -> float:
    adj = 0.0
    if "Schade" in flags:
        adj -= 1.0
    if "Defect" in flags:
        adj -= 0.5
    if "LPG" in flags:
        adj -= 0.5
    return adj


def observed_trend(model_ids_by_listing: dict[str, str], history: list[tuple[str, str, int]]) -> dict[str, dict]:
    """Jaarlijkse prijstrend per model uit eigen waarnemingen (log-lineaire regressie).

    Pas betrouwbaar na een paar maanden data; tot dan geeft het dashboard enkel de startinschatting.
    """
    points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for lid, d, price in history:
        mid = model_ids_by_listing.get(lid)
        if mid and price > 0:
            t = date.fromisoformat(d).toordinal() / 365.25
            points[mid].append((t, math.log(price)))
    out = {}
    for mid, pts in points.items():
        ts = [p[0] for p in pts]
        span = max(ts) - min(ts)
        if len(pts) < 20 or span < 0.5:
            continue
        mt = statistics.fmean(ts)
        my = statistics.fmean(p[1] for p in pts)
        var = sum((t - mt) ** 2 for t in ts)
        if var == 0:
            continue
        slope = sum((t - mt) * (y - my) for t, y in pts) / var
        out[mid] = {"annualPct": round((math.exp(slope) - 1) * 100, 2), "spanYears": round(span, 2), "n": len(pts)}
    return out


def blended_trend(model: Model, observed: dict | None) -> tuple[float, float]:
    """(gebruikte trend, gewicht eigen data). Eigen data telt zwaarder naarmate de reeks langer is (max 60%)."""
    if not observed:
        return model.trend, 0.0
    w = min(observed["spanYears"] / 3.0, 0.6)
    obs = max(min(observed["annualPct"], 15.0), -10.0)
    return round((1 - w) * model.trend + w * obs, 2), round(w, 2)


def clean_km(r: dict, current_year: int) -> dict:
    """< 5.000 km op een auto ouder dan 10 jaar is bijna altijd 'niet ingevuld' (1, 999, 1000 ...)."""
    if r.get("km") and r["km"] < 5_000 and r.get("year") and current_year - r["year"] > 10:
        return {**r, "km": None}
    return r


def analyse(records: list[dict], watchlist: Watchlist, history: list[tuple[str, str, int]]) -> tuple[list[dict], dict]:
    """Geeft (verrijkte actieve advertenties, modelstatistieken) terug."""
    current_year = date.today().year
    records = [clean_km(r, current_year) for r in records]
    models = {m.id: m for m in watchlist.models}
    min_price = watchlist.settings.min_price
    active = [
        r for r in records
        if r.get("active") and r.get("model_id") in models and r.get("price") and r["price"] >= min_price
    ]

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in active:
        if not (set(r.get("flags", [])) & UNRELIABLE_FLAGS):
            groups[(r["model_id"], _tier(r))].append(r)

    trends = observed_trend({r["id"]: r.get("model_id") for r in records}, history)

    price_models: dict[tuple[str, str], PriceModel] = {}
    for key, comps in groups.items():
        if len(comps) >= MIN_REGRESSION:
            try:
                price_models[key] = PriceModel(comps)
            except ZeroDivisionError:
                pass

    out = []
    for r in active:
        model = models[r["model_id"]]
        comps = [c for c in groups[(model.id, _tier(r))] if c["id"] != r["id"]]
        n = len(comps)
        pm = price_models.get((model.id, _tier(r)))
        if pm is not None:
            fair = round(pm.predict(r), -1)
        elif n >= MIN_COMPS:
            fair = statistics.median(c["price"] for c in comps)
            kms = [c["km"] for c in comps if c.get("km")]
            if r.get("km") and len(kms) >= MIN_COMPS:
                ref = statistics.median(kms)
                adj = KM_EFFECT_PER_10K * (ref - r["km"]) / 10_000
                fair *= 1 + max(-KM_EFFECT_CAP, min(KM_EFFECT_CAP, adj))
            fair = round(fair, -1)
        else:
            fair = r["price"]  # te weinig vergelijkingsmateriaal: geen koopje/te duur-signaal

        flags = list(r.get("flags", []))
        suspicious = fair > SUSPICIOUS_DEAL * r["price"]
        if suspicious:
            fair = round(SUSPICIOUS_DEAL * r["price"], -1)
            flags.append("Prijs verdacht laag")

        conf = 1.0
        conf -= 0 if n >= 8 else 0.15 if n >= MIN_COMPS else 0.35
        if not r.get("km"):
            conf -= 0.15
        if not r.get("year"):
            conf -= 0.1
        if r.get("price_type") == "MIN_BID":
            conf -= 0.1
        conf -= 0.2 * len(set(r.get("flags", [])) & UNRELIABLE_FLAGS)
        if suspicious:
            conf -= 0.3
        conf = round(max(0.1, min(1.0, conf)), 2)

        trend, _w = blended_trend(model, trends.get(model.id))
        variant_bonus = min(sum(b for _, b in r.get("variants", [])), 6.0)
        out.append({
            **r,
            "flags": flags,
            "fair": fair,
            "comps": n,
            "tier": _tier(r),
            "conf": conf,
            "rate": {
                "trend": trend,
                "variant": round(variant_bonus, 2),
                "km": km_adjustment(r.get("km")),
                "gearbox": gearbox_adjustment(model, r.get("gearbox")),
                "fuel": -1.0 if r.get("fuel") == "diesel" else 0.0,
                "condition": condition_adjustment(r.get("flags", [])),
            },
        })

    stats = {}
    for m in watchlist.models:
        mine = [r for r in active if r["model_id"] == m.id]
        prices = [r["price"] for r in mine]
        trend, weight = blended_trend(m, trends.get(m.id))
        stats[m.id] = {
            **m.to_public(),
            "active": len(mine),
            "median": statistics.median(prices) if prices else None,
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "observed": trends.get(m.id),
            "trendUsed": trend,
            "observedWeight": weight,
            "removedTotal": sum(1 for r in records if r.get("model_id") == m.id and not r.get("active")),
        }
    return out, stats
