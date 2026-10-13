"""Bronnen: elke bron levert per watchlist-model een SearchResult."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..listing import Listing


@dataclass
class SearchResult:
    source: str
    model_id: str
    listings: list[Listing] = field(default_factory=list)
    # complete=True betekent: alle resultaten van de zoekopdracht zijn opgehaald,
    # dus advertenties die we niet meer zien zijn waarschijnlijk verkocht/verwijderd.
    complete: bool = True
    errors: list[str] = field(default_factory=list)
