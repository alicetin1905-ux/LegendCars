"""Controleert of een advertentie echt bij het watchlist-model hoort en verrijkt ze met uitvoering/risico's."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import Model, Settings
from .listing import Listing
from .text import normalize

TEXT_SOURCES = {"2dehands", "marktplaats", "kleinanzeigen", "willhaben", "coches"}
# Als de site geen carrosserie meegeeft, moet het in de tekst staan (anders glipt bv. een Golf 2 door als "Golf 1 Cabrio")
BODY_WORDS = {
    "cabrio": re.compile(r"cabrio|roadster|spider|spyder|convertible|descapotable|karmann|barchetta"),
    "coupe": re.compile(r"\bcoupe|\bcoupes?\b"),
}
MAX_VARIANT_BONUS = 6.0


@dataclass
class Match:
    variants: list[tuple[str, float]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def variant_bonus(self) -> float:
        return min(sum(b for _, b in self.variants), MAX_VARIANT_BONUS)

    @property
    def tier(self) -> str:
        """Prijsklasse binnen het model: de duurste uitvoering met een stevige bonus, anders 'base'."""
        strong = [(b, label) for label, b in self.variants if b >= 1.5]
        return max(strong)[1] if strong else "base"


def reject_reason(listing: Listing, model: Model, settings: Settings) -> str | None:
    """None als de advertentie matcht, anders een korte reden (handig voor debuggen)."""
    title = normalize(listing.title, listing.subtitle)
    full = normalize(listing.title, listing.subtitle, listing.description)

    for rx in settings.title_exclude:
        if rx.search(title):
            return f"titel-uitsluiting: {rx.pattern}"
    if listing.year is None:
        if listing.source in TEXT_SOURCES:
            return "geen bouwjaar"
    elif not (model.years[0] <= listing.year <= model.years[1]):
        return f"bouwjaar {listing.year} buiten {model.years}"
    for rx in model.keywords:
        if not rx.search(full):
            return f"sleutelwoord ontbreekt: {rx.pattern}"
    if listing.source in TEXT_SOURCES:
        for rx in model.text_keywords:
            if not rx.search(full):
                return f"tekst-sleutelwoord ontbreekt: {rx.pattern}"
    for rx in model.exclude:
        if rx.search(title):
            return f"uitgesloten: {rx.pattern}"
    if model.body:
        if listing.body:
            if listing.body not in model.body:
                return f"carrosserie {listing.body} niet in {model.body}"
        elif model.body_in_text and listing.source in TEXT_SOURCES and not any(BODY_WORDS[b].search(full) for b in model.body if b in BODY_WORDS):
            return f"carrosserie onbekend en niet in tekst ({'/'.join(model.body)})"
    return None


def match(listing: Listing, model: Model, settings: Settings) -> Match | None:
    if reject_reason(listing, model, settings):
        return None
    full = normalize(listing.title, listing.subtitle, listing.description)
    result = Match()
    for v in model.variants:
        if v.applies(full, listing.year):
            result.variants.append((v.label, v.bonus))
    for rx, label in settings.risk_flags:
        if rx.search(full) and label not in result.flags:
            result.flags.append(label)
    return result
