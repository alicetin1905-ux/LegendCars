# LegendCars: Oldtimer collection

Een dashboard dat elke dag zoekt naar de auto's uit je collectielijst op:

| Website | Land | Wat |
|---|---|---|
| **AutoScout24** | BE, NL, DE, LU, FR, AT, IT, ES | vooral handelaars |
| **2dehands.be** | BE | particulieren en handelaars |
| **Marktplaats.nl** | NL | particulieren en handelaars |
| **Kleinanzeigen.de** | DE | vooral particulieren, veel youngtimers onder €10.000 |
| **Willhaben.at** | AT | particulieren en handelaars |
| **Coches.net** | ES | roestvrije klassiekers uit Spanje |

Niet opgenomen: **AutoTrack.nl** (zelfde advertenties als AutoScout24), **Autovlan.be** (doorverwezen naar Gocar), **Gocar.be** (Cloudflare-botbeveiliging), **Mobile.de**, **Leboncoin.fr**, **La Centrale**, **Subito.it**, **Gaspedaal.nl**, **Autoweek**, **Catawiki**, **Car & Classic** en **Classic Driver** (blokkeren automatische opvragingen). 2ememain.be is dezelfde database als 2dehands. De auto's worden gerangschikt op hoeveel waarde ze kunnen opbrengen als je ze een aantal jaar stockeert.

Open `docs/index.html` in je browser. Of zet GitHub Pages aan (zie hieronder), dan staat het dashboard online en wordt het elke ochtend automatisch bijgewerkt.

## Wat het dashboard doet

- **Schuifregelaar "Stockeren voor X jaar"** (1 tot 15 jaar): alle berekeningen passen zich live aan.
- **Welk model brengt het meest op?** Mediaan netto rendement per jaar per model, na alle kosten. Klik op een model om te filteren.
- **Beste kansen**: elke advertentie met vraagprijs, marktwaarde, staat, verwachte waarde na X jaar, netto winst, rendement per jaar en een investeringsscore (0-100). Klik op een rij voor de volledige rekensom en een grafiek.
- **Filters**: merk, model, prijs van/tot (standaard €2.500-9.999), max. km (standaard 250.000), land, website, enkel manueel, projecten/schade verbergen, enkel winstgevend.
- **Kosten en scoregewichten**: stalling, verzekering, taks, onderhoud, aankoop- en verkoopkosten. Je kiest ook zelf hoe zwaar rendement, koopjes, zeldzaamheid, vraag en betrouwbaarheid meetellen. Je instellingen worden in je browser onthouden.

## Filters

| Filter | Waarde | Waar |
|---|---|---|
| Bouwjaar | t/m 1999 | bij het zoeken (`max_year` in `watchlist.toml`) |
| Prijs | €2.500 – €9.999 | standaardfilter in het dashboard (`price_min`/`price_max`) |
| Kilometerstand | max. 250.000 km | standaardfilter in het dashboard (`max_km`) |
| Afstand | max. 250 km hemelsbreed van Balen | standaardfilter in het dashboard (`home_*`, `max_distance_km`) |

De afstand wordt berekend met de exacte coördinaten (2dehands, Marktplaats, Willhaben) of anders met de postcode/gemeente (postcodetabel van [GeoNames](https://www.geonames.org/), CC-BY 4.0). Het vertrekpunt staat bewust afgerond op ~1 km, want deze pagina is openbaar.

Op prijs en km wordt bewust breder gezocht. Zo is de marktwaarde gebaseerd op álle vergelijkbare auto's en niet alleen op de goedkope.

## Dagelijkse melding van nieuwe kansen

Na elke update kijkt `legendcars/alerts.mjs` naar auto's die **vandaag nieuw online** kwamen of **vandaag in prijs zakten**, binnen je standaardfilters (prijs, km, afstand, geen risico's) en met een investeringsscore van minstens `alert_min_score` (standaard 75). Zijn er zulke auto's, dan maakt de update een **GitHub-issue "🚗 N nieuwe kansen"** met links naar de advertenties; de melding van gisteren wordt gesloten.

- **Melding op je gsm:** installeer de GitHub-app en zet meldingen aan (je krijgt ze ook per e-mail). Je bent automatisch "watcher" van je eigen repo.
- **Liever Telegram?** Maak met @BotFather een bot, stuur hem een bericht en voeg in GitHub twee secrets toe (Settings → Secrets and variables → Actions): `TELEGRAM_BOT_TOKEN` en `TELEGRAM_CHAT_ID`. Dan komt dezelfde lijst ook via Telegram.

## Staat, prijsdalingen en favorieten

- **Staat:** voor de auto's binnen je filters wordt de volledige advertentie gelezen (`python -m legendcars details`, zit in de dagelijkse update). Pluspunten (Car-Pass/NAP, onderhoudshistoriek, 1e eigenaar, garagewagen, oldtimerplaat, keuring, roestvrij, origineel) en minpunten (roest, ongeval, motorproblemen, tuning, geen keuring, vervangen motor, lak/deuken) geven een staat-score van −4 tot +4. Die telt mee in de groei (max. ±1%/jaar) en in de score. De beschrijving zelf wordt niet bewaard; telefoonnummers en e-mailadressen worden uit opgeslagen teksten verwijderd.
- **Prijsdalingen en tijd online:** badges "Prijs −€X" en "57 d online", filter "Enkel prijsdalingen", sorteren op "Grootste prijsdaling". Vanaf 45 dagen online krijg je een onderhandelingstip.
- **Favorieten:** klik "☆ Bewaar" bij een auto, voeg notities toe in het detailpaneel en vergelijk je favorieten naast elkaar bovenaan. Favorieten en notities worden in je browser bewaard (per toestel).

## Hoe de waarde wordt ingeschat

| Stap | Wat |
|---|---|
| Marktwaarde | Mediaan van vergelijkbare advertenties (zelfde model en prijsklasse-uitvoering, bv. VR6 apart van G60), gecorrigeerd voor kilometerstand. Bij minder dan 4 vergelijkbare advertenties: geen koopje-signaal. |
| Groei per jaar | Markttrend van het model (`trend` in `watchlist.toml`) + uitvoering (bv. M3, VR6, Type R) + kilometerstand + manuele bak + brandstof + staat + extra groei als de auto tijdens het stockeren een oldtimer wordt (30 jaar, `oldtimer_age`). |
| Eigen data | Elke dag wordt de prijshistoriek bewaard (`data/price_history.csv`). Na 6 maanden begint de **gemeten** trend mee te tellen (tot 60% na 3 jaar). |
| Netto | Waarde na X jaar − aankoopprijs − aankoopkosten (standaard €500). Stalling, verzekering, taks, onderhoud en verkoopkosten staan standaard op €0 en zijn in te vullen in het dashboard. |

> De startwaarden voor `trend`, `rarity` en `demand` zijn inschattingen op basis van algemene markttrends in de klassiekerwereld. Pas ze gerust aan in `watchlist.toml`. Het blijven schattingen op basis van vraagprijzen, geen financieel advies. Controleer elke auto zelf (Car-Pass, onderhoudshistoriek, roest).

## Modellen aanpassen

Alles staat in **`watchlist.toml`**. Elk `[[model]]`-blok is één filter: bouwjaren, verplichte woorden (bv. `gsi`, `vr6`), uitgesloten woorden, carrosserie, uitvoeringen met hun bonus, en de zoekopdrachten per site. Bovenaan staan de standaardkosten van het dashboard.

AutoScout24-id's voor merken en modellen vind je in de URL van een zoekopdracht op autoscout24.be (`mmmv=merk|model|reeks|`).

## Lokaal draaien

Python 3.11+ is nodig, verder niets te installeren.

```bash
python -m legendcars update                      # alles doorzoeken + dashboard bouwen (± 45 min)
python -m legendcars scrape --model vw-corrado   # één model
python -m legendcars -v scrape --source 2dehands # één site, met redenen waarom advertenties afvielen
python -m legendcars build                       # enkel dashboard opnieuw bouwen
python -m legendcars models                      # overzicht van de watchlist
```

Tests: `python -m unittest discover -s tests -t .` en `node --test tests/valuation.test.mjs`.

## Automatisch elke dag (GitHub)

1. **Settings → Actions → General → Workflow permissions**: kies *Read and write permissions*.
2. **Settings → Pages**: *Deploy from a branch*, branch `main`, map `/docs` of `/ (root)`. Bij root stuurt `index.html` door naar het dashboard in `docs/`.
3. De workflow **Dagelijkse update** draait elke ochtend en bewaart nieuwe advertenties en prijzen in `data/`. Je kunt hem ook manueel starten via **Actions → Dagelijkse update → Run workflow**.

## Bestanden

```
watchlist.toml              jouw filters, trends en standaardkosten
legendcars/sources/         één bestand per website
legendcars/matching.py      controleert of een advertentie echt bij het model hoort
legendcars/market.py        marktwaarde, groei-onderdelen, gemeten trend
legendcars/dashboard/       HTML/CSS/JS van het dashboard (valuation.js = projectie)
data/listings.jsonl         alle gevonden advertenties (ook verdwenen = waarschijnlijk verkocht)
data/price_history.csv      prijs per advertentie per wijziging
docs/index.html             het gebouwde dashboard
```

## Opmerkingen

- De scraper vraagt ongeveer één pagina per seconde op en bewaart geen namen of telefoonnummers van verkopers. Gebruik het enkel voor persoonlijk zoekwerk; de gebruiksvoorwaarden van de sites gelden.
- Coches.net blokkeert de servers van GitHub. De dagelijkse update slaat Coches dan over; advertenties die 14 dagen niet meer gezien zijn, verdwijnen uit het dashboard.
- Een advertentie die bij een volledige zoekopdracht niet meer opduikt, wordt als *verdwenen* gemarkeerd. Dat is waarschijnlijk verkocht, en het is nuttige data voor de werkelijke vraag per model.
