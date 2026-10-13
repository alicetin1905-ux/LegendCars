"""Gemeenschappelijk formaat voor een advertentie, ongeacht de bron."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Listing:
    id: str  # "<bron>:<id bij bron>"
    source: str  # autoscout24 | 2dehands | marktplaats
    url: str
    title: str
    subtitle: str = ""
    description: str = ""
    year: int | None = None
    km: int | None = None
    price: int | None = None
    price_type: str = "FIXED"  # FIXED | MIN_BID (bieden vanaf) | ...
    fuel: str | None = None  # petrol | diesel | lpg | other
    gearbox: str | None = None  # manual | automatic
    body: str | None = None  # cabrio | coupe | other
    hp: int | None = None
    country: str | None = None
    city: str | None = None
    seller: str | None = None  # dealer | private
    image: str | None = None
    model_id: str | None = None  # watchlist-model waarvoor de zoekopdracht liep
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def norm_fuel(value: str | None) -> str | None:
    if not value:
        return None
    v = value.lower()
    if "diesel" in v:
        return "diesel"
    if "lpg" in v or "gas" in v:
        return "lpg"
    if "benzin" in v or "essence" in v or "petrol" in v:
        return "petrol"
    return "other"


def norm_gearbox(value: str | None) -> str | None:
    if not value:
        return None
    v = value.lower()
    if "auto" in v or "semi" in v or "half" in v:
        return "automatic"
    if "hand" in v or "manu" in v or "schalt" in v:
        return "manual"
    return None


def norm_body(value: str | None) -> str | None:
    if not value:
        return None
    v = value.lower()
    if "cabrio" in v or "roadster" in v or "convertible" in v:
        return "cabrio"
    if "coup" in v:
        return "coupe"
    return "other"
