# LegendCars: Oldtimer collection

Een dashboard dat elke dag op **AutoScout24** (België, Nederland, Duitsland, Luxemburg, Frankrijk, Oostenrijk, Italië, Spanje), **2dehands.be** en **Marktplaats.nl** zoekt naar de auto's uit je collectielijst. De auto's worden gerangschikt op hoeveel waarde ze kunnen opbrengen als je ze een aantal jaar stockeert.

Open `docs/index.html` in je browser. Of zet GitHub Pages aan (zie hieronder), dan staat het dashboard online en wordt het elke ochtend automatisch bijgewerkt.

## Wat het dashboard doet

- **Schuifregelaar "Stockeren voor X jaar"** (1 tot 15 jaar): alle berekeningen passen zich live aan.
- **Welk model brengt het meest op?** Mediaan netto rendement per jaar per model, na alle kosten. Klik op een model om te filteren.
- **Beste kansen**: elke advertentie met vraagprijs, marktwaarde, verwachte waarde na X jaar, netto winst, rendement per jaar en een investeringsscore (0-100). Klik op een rij voor de volledige rekensom en een grafiek.
- **Filters**: merk, model, budget, land, website, enkel manueel, projecten/schade verbergen, enkel winstgevend.
- **Kosten en scoregewichten**: stalling, verzekering, taks, onderhoud, aankoop- en verkoopkosten. Je kiest ook zelf hoe zwaar rendement, koopjes, zeldzaamheid, vraag en betrouwbaarheid meetellen. Je instellingen worden in je browser onthouden.

## Hoe de waarde wordt ingeschat

| Stap | Wat |
|---|---|
| Marktwaarde | Mediaan van vergelijkbare advertenties (zelfde model en prijsklasse-uitvoering, bv. VR6 apart van G60), gecorrigeerd voor kilometerstand. Bij minder dan 4 vergelijkbare advertenties: geen koopje-signaal. |
| Groei per jaar | Markttrend van het model (`trend` in `watchlist.toml`) + uitvoering (bv. M3, VR6, Type R) + kilometerstand + manuele bak + brandstof + staat + extra groei als de auto tijdens het stockeren 25 jaar wordt (O-plaat). |
| Eigen data | Elke dag wordt de prijshistoriek bewaard (`data/price_history.csv`). Na 6 maanden begint de **gemeten** trend mee te tellen (tot 60% na 3 jaar). |
| Netto | Waarde na X jaar − verkoopkosten − aankoopprijs − aankoopkosten − jaarlijkse kosten × X. |

> De startwaarden voor `trend`, `rarity` en `demand` zijn inschattingen op basis van algemene markttrends in de klassiekerwereld. Pas ze gerust aan in `watchlist.toml`. Het blijven schattingen op basis van vraagprijzen, geen financieel advies. Controleer elke auto zelf (Car-Pass, onderhoudshistoriek, roest).

## Modellen aanpassen

Alles staat in **`watchlist.toml`**. Elk `[[model]]`-blok is één filter: bouwjaren, verplichte woorden (bv. `gsi`, `vr6`), uitgesloten woorden, carrosserie, uitvoeringen met hun bonus, en de zoekopdrachten per site. Bovenaan staan de standaardkosten van het dashboard.

AutoScout24-id's voor merken en modellen vind je in de URL van een zoekopdracht op autoscout24.be (`mmmv=merk|model|reeks|`).

## Lokaal draaien

Python 3.11+ is nodig, verder niets te installeren.

```bash
python -m legendcars update                      # alles doorzoeken + dashboard bouwen (± 30 min)
python -m legendcars scrape --model vw-corrado   # één model
python -m legendcars -v scrape --source 2dehands # één site, met redenen waarom advertenties afvielen
python -m legendcars build                       # enkel dashboard opnieuw bouwen
python -m legendcars models                      # overzicht van de watchlist
```

Tests: `python -m unittest discover -s tests -t .` en `node --test tests/valuation.test.mjs`.

## Automatisch elke dag (GitHub)

1. **Settings → Actions → General → Workflow permissions**: kies *Read and write permissions*.
2. **Settings → Pages**: *Deploy from a branch*, branch `main`, map `/docs`.
3. De workflow **Dagelijkse update** draait elke ochtend en bewaart nieuwe advertenties en prijzen in `data/`. Je kunt hem ook manueel starten via **Actions → Dagelijkse update → Run workflow**.

## Bestanden

```
watchlist.toml              jouw filters, trends en standaardkosten
legendcars/sources/         AutoScout24 en 2dehands/Marktplaats
legendcars/matching.py      controleert of een advertentie echt bij het model hoort
legendcars/market.py        marktwaarde, groei-onderdelen, gemeten trend
legendcars/dashboard/       HTML/CSS/JS van het dashboard (valuation.js = projectie)
data/listings.jsonl         alle gevonden advertenties (ook verdwenen = waarschijnlijk verkocht)
data/price_history.csv      prijs per advertentie per wijziging
docs/index.html             het gebouwde dashboard
```

## Opmerkingen

- Mobile.de blokkeert automatische opvragingen. Daarom wordt Duitsland via AutoScout24 doorzocht.
- De scraper vraagt ongeveer één pagina per seconde op en bewaart geen namen of telefoonnummers van verkopers. Gebruik het enkel voor persoonlijk zoekwerk; de gebruiksvoorwaarden van de sites gelden.
- Een advertentie die bij een volledige zoekopdracht niet meer opduikt, wordt als *verdwenen* gemarkeerd. Dat is waarschijnlijk verkocht, en het is nuttige data voor de werkelijke vraag per model.
