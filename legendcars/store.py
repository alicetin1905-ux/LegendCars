"""Opslag als tekstbestanden zodat git de geschiedenis efficiënt bijhoudt.

data/listings.jsonl       één regel per advertentie die ooit gematcht werd (actief of niet)
data/price_history.csv    id,datum,prijs — een regel bij eerste waarneming en bij elke prijswijziging
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import ROOT
from .listing import Listing
from .matching import Match

DATA_DIR = ROOT / "data"


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.dir = Path(data_dir)
        self.listings_path = self.dir / "listings.jsonl"
        self.history_path = self.dir / "price_history.csv"
        self.records: dict[str, dict] = {}
        self._new_history: list[tuple[str, str, int]] = []
        self._last_price: dict[str, int] = {}
        self.load()

    def load(self):
        if self.listings_path.exists():
            with open(self.listings_path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        rec = json.loads(line)
                        self.records[rec["id"]] = rec
        for lid, _date, price in self.history():
            self._last_price[lid] = price

    def history(self):
        if not self.history_path.exists():
            return
        with open(self.history_path, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                yield row["id"], row["date"], int(row["price"])

    def upsert(self, listing: Listing, match: Match, today: str) -> bool:
        """Slaat de advertentie op; geeft True terug als ze nieuw is."""
        rec = listing.to_dict()
        rec["variants"] = [[label, bonus] for label, bonus in match.variants]
        rec["flags"] = match.flags
        old = self.records.get(listing.id)
        is_new = old is None
        rec["first_seen"] = today if is_new else old.get("first_seen", today)
        rec["first_price"] = listing.price if is_new else old.get("first_price", listing.price)
        rec["last_seen"] = today
        rec["active"] = True
        rec.pop("removed", None)
        self.records[listing.id] = rec
        if listing.price and self._last_price.get(listing.id) != listing.price:
            self._new_history.append((listing.id, today, listing.price))
            self._last_price[listing.id] = listing.price
        return is_new

    def mark_missing(self, source: str, model_id: str, seen_ids: set[str], today: str) -> int:
        """Advertenties die bij een volledige zoekopdracht niet meer opdoken -> inactief (verkocht/verwijderd)."""
        n = 0
        for rec in self.records.values():
            if (
                rec.get("active")
                and rec["source"] == source
                and rec.get("model_id") == model_id
                and rec["id"] not in seen_ids
            ):
                rec["active"] = False
                rec["removed"] = today
                n += 1
        return n

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.listings_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for lid in sorted(self.records):
                fh.write(json.dumps(self.records[lid], ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(self.listings_path)
        if self._new_history:
            new_file = not self.history_path.exists()
            with open(self.history_path, "a", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                if new_file:
                    w.writerow(["id", "date", "price"])
                w.writerows(self._new_history)
            self._new_history = []
