"""Leest watchlist.toml in en compileert de regex'en."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WATCHLIST = ROOT / "watchlist.toml"


# Uitvoering die enkel uiterlijk is ("M3-look", "AMG pakket", "allestimento M3", "M3 velgen") telt niet mee.
LOOKALIKE = re.compile(
    r"\b(look|optiek|optik|styling|pakket|paket|package|allestimento|replica|bodykit|kit|velgen|felgen|"
    r"bumper|stoelen|sitze|seats|interieur|interior|stuur|spiegels|uitlaat|line)\b"
)
LOOKALIKE_WINDOW = 22  # tekens voor/na de match


def _compile(patterns) -> list[re.Pattern]:
    return [re.compile(p) for p in (patterns or [])]


@dataclass
class Variant:
    label: str
    bonus: float
    match: re.Pattern | None = None
    years: tuple[int, int] | None = None

    def applies(self, text: str, year: int | None) -> bool:
        if self.years:
            if year is None or not (self.years[0] <= year <= self.years[1]):
                return False
        if self.match is None:
            return True
        for m in self.match.finditer(text):
            context = text[max(0, m.start() - LOOKALIKE_WINDOW): m.end() + LOOKALIKE_WINDOW]
            if not LOOKALIKE.search(context):
                return True
        return False


@dataclass
class As24Search:
    make: int
    model: int | None = None
    line: int | None = None
    body: list[int] = field(default_factory=list)

    @property
    def mmmv(self) -> str:
        return f"{self.make}|{self.model or ''}|{self.line or ''}|"


@dataclass
class Model:
    id: str
    make: str
    name: str
    years: tuple[int, int]
    trend: float
    rarity: int
    demand: int
    manual_premium: bool
    keywords: list[re.Pattern]
    text_keywords: list[re.Pattern]
    exclude: list[re.Pattern]
    body: list[str]
    variants: list[Variant]
    as24: list[As24Search]
    query: list[str]

    @property
    def label(self) -> str:
        return f"{self.make} {self.name}"

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "make": self.make,
            "name": self.name,
            "years": list(self.years),
            "trend": self.trend,
            "rarity": self.rarity,
            "demand": self.demand,
            "manualPremium": self.manual_premium,
        }


@dataclass
class Settings:
    as24_countries: list[str]
    as24_max_pages: int
    adevinta_sites: list[str]
    adevinta_max_pages: int
    request_delay: float
    min_price: int
    title_exclude: list[re.Pattern]
    risk_flags: list[tuple[re.Pattern, str]]


@dataclass
class Watchlist:
    settings: Settings
    dashboard: dict
    models: list[Model]

    def model(self, model_id: str) -> Model:
        for m in self.models:
            if m.id == model_id:
                return m
        raise KeyError(model_id)


def load(path: Path | str = DEFAULT_WATCHLIST) -> Watchlist:
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    s = raw.get("settings", {})
    settings = Settings(
        as24_countries=s.get("as24_countries", ["B", "NL", "D"]),
        as24_max_pages=int(s.get("as24_max_pages", 20)),
        adevinta_sites=s.get("adevinta_sites", ["2dehands", "marktplaats"]),
        adevinta_max_pages=int(s.get("adevinta_max_pages", 3)),
        request_delay=float(s.get("request_delay", 1.0)),
        min_price=int(s.get("min_price", 1000)),
        title_exclude=_compile(s.get("title_exclude")),
        risk_flags=[(re.compile(f["match"]), f["label"]) for f in s.get("risk_flags", [])],
    )

    models = []
    seen = set()
    for m in raw.get("model", []):
        if m["id"] in seen:
            raise ValueError(f"Dubbel model-id in watchlist: {m['id']}")
        seen.add(m["id"])
        models.append(
            Model(
                id=m["id"],
                make=m["make"],
                name=m["name"],
                years=tuple(m["years"]),
                trend=float(m["trend"]),
                rarity=int(m.get("rarity", 3)),
                demand=int(m.get("demand", 3)),
                manual_premium=bool(m.get("manual_premium", False)),
                keywords=_compile(m.get("keywords")),
                text_keywords=_compile(m.get("text_keywords")),
                exclude=_compile(m.get("exclude")),
                body=m.get("body", []),
                variants=[
                    Variant(
                        label=v["label"],
                        bonus=float(v.get("bonus", 0)),
                        match=re.compile(v["match"]) if v.get("match") else None,
                        years=tuple(v["years"]) if v.get("years") else None,
                    )
                    for v in m.get("variants", [])
                ],
                as24=[As24Search(**a) for a in m.get("as24", [])],
                query=m.get("query", []),
            )
        )
    return Watchlist(settings=settings, dashboard=raw.get("dashboard", {}), models=models)
