"""Command line:

    python -m legendcars update            # alle sites doorzoeken + dashboard bouwen
    python -m legendcars scrape [--model vw-corrado] [--source autoscout24]
    python -m legendcars build             # enkel dashboard opnieuw bouwen uit data/
    python -m legendcars models            # overzicht van de watchlist
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date

from . import config
from .export import DEFAULT_OUTPUT, build_data, render
from .http import Fetcher
from .matching import match, reject_reason
from .sources import adevinta, autoscout24, coches, kleinanzeigen, willhaben
from .store import Store

log = logging.getLogger("legendcars")


def scrape(wl: config.Watchlist, store: Store, model_ids: list[str] | None, sources: list[str] | None, verbose: bool):
    today = date.today().isoformat()
    fetcher = Fetcher(delay=wl.settings.request_delay)
    wanted_sources = [s for s in wl.settings.sources if not sources or s in sources]
    models = [m for m in wl.models if not model_ids or m.id in model_ids]
    totals = Counter()
    for model in models:
        for src in wanted_sources:
            if src == "autoscout24":
                if not model.as24:
                    continue
                result = autoscout24.search(model, wl.settings, fetcher)
            elif src == "kleinanzeigen":
                if not model.query:
                    continue
                result = kleinanzeigen.search(model, wl.settings, fetcher)
            elif src == "willhaben":
                if not model.query:
                    continue
                result = willhaben.search(model, wl.settings, fetcher)
            elif src == "coches":
                result = coches.search(model, wl.settings, fetcher)
            elif src in adevinta.SITES:
                if not model.query:
                    continue
                result = adevinta.search(model, wl.settings, fetcher, src)
            else:
                print(f"Onbekende bron in watchlist: {src}", file=sys.stderr)
                continue
            seen, new, rejected = set(), 0, Counter()
            for listing in result.listings:
                m = match(listing, model, wl.settings)
                if m is None:
                    rejected[reject_reason(listing, model, wl.settings)] += 1
                    continue
                seen.add(listing.id)
                new += store.upsert(listing, m, today)
            gone = store.mark_missing(src, model.id, seen, today) if result.complete else 0
            totals["matched"] += len(seen)
            totals["new"] += new
            totals["gone"] += gone
            totals["errors"] += len(result.errors)
            print(
                f"{model.id:26s} {src:12s} gevonden {len(result.listings):4d}  match {len(seen):4d}  "
                f"nieuw {new:3d}  weg {gone:3d}{'' if result.complete else '  (onvolledig)'}"
                f"{'  FOUTEN ' + str(len(result.errors)) if result.errors else ''}",
                flush=True,
            )
            if verbose and src != "coches":
                for reason, n in rejected.most_common(5):
                    print(f"    afgewezen {n:3d}x  {reason}")
        store.save()  # tussentijds bewaren: een afgebroken run verliest niets
    print(f"\nTotaal: {totals['matched']} matches, {totals['new']} nieuw, {totals['gone']} verdwenen, "
          f"{totals['errors']} fouten, {fetcher.requests} requests")
    return totals


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="legendcars", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--watchlist", default=str(config.DEFAULT_WATCHLIST))
    p.add_argument("--data", default=str(config.ROOT / "data"))
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("scrape", "update"):
        sp = sub.add_parser(name)
        sp.add_argument("--model", action="append", help="enkel dit model-id (herhaalbaar)")
        sp.add_argument("--source", action="append", help="autoscout24, 2dehands, marktplaats, kleinanzeigen, willhaben of coches (herhaalbaar)")
    bp = sub.add_parser("build")
    for sp in (bp, sub.choices["update"]):
        sp.add_argument("--output", default=str(DEFAULT_OUTPUT))
    sub.add_parser("models")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    wl = config.load(args.watchlist)

    if args.cmd == "models":
        for m in wl.models:
            print(f"{m.id:26s} {m.label:45s} {m.years[0]}-{m.years[1]}  trend {m.trend:+.1f}%/jaar")
        for mid in wl.skipped:
            print(f"{mid:26s} overgeslagen: begint na max_year {wl.settings.max_year}")
        return 0

    store = Store(args.data)
    if args.cmd in ("scrape", "update"):
        totals = scrape(wl, store, args.model, args.source, args.verbose)
        if totals["matched"] == 0 and totals["errors"] > 0:
            print("Geen enkele advertentie opgehaald — sites onbereikbaar of geblokkeerd?", file=sys.stderr)
            return 2
    if args.cmd in ("build", "update"):
        data = build_data(wl, store)
        out = render(data, args.output)
        print(f"Dashboard: {out}  ({len(data['listings'])} advertenties)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
