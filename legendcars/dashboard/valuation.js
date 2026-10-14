/* LegendCars waardeprojectie. Werkt in de browser (window.Valuation) en in Node (module.exports). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Valuation = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Standaardgewichten van de investeringsscore (dashboard én dagelijkse melding)
  var DEFAULT_WEIGHTS = { ret: 45, deal: 15, rarity: 10, demand: 10, conf: 5, cond: 15 };
  var OLDTIMER_AGE = 30; // standaard; instelbaar via params.oldtimer_age (watchlist.toml [dashboard])
  var MIN_RATE = -5;
  var MAX_RATE = 15;

  function clamp(x, lo, hi) {
    return Math.max(lo, Math.min(hi, x));
  }

  function oldtimerAge(params) {
    return (params && params.oldtimer_age) || OLDTIMER_AGE;
  }

  /* Extra groei rond de oldtimergrens: wagens die tijdens je stockage oldtimer worden,
     krijgen goedkopere verzekering/taks en meer kopers. */
  function ageAdjustment(year, currentYear, horizon, limit) {
    if (!year) return 0;
    var lim = limit || OLDTIMER_AGE;
    var age = currentYear - year;
    if (age < lim && age + horizon >= lim) return 1.0;
    if (age >= lim && age < lim + 10) return 0.3;
    return 0;
  }

  /* Jaarlijkse waardegroei in %, opgebouwd uit onderdelen (voor de uitleg in het dashboard). */
  function rateParts(listing, params, currentYear) {
    var r = listing.rate || {};
    return [
      { key: "trend", label: "Markttrend model", value: r.trend || 0 },
      { key: "variant", label: "Uitvoering", value: r.variant || 0 },
      { key: "km", label: "Kilometerstand", value: r.km || 0 },
      { key: "gearbox", label: "Versnellingsbak", value: r.gearbox || 0 },
      { key: "fuel", label: "Brandstof", value: r.fuel || 0 },
      { key: "condition", label: "Staat (uit advertentie)", value: r.condition || 0 },
      { key: "age", label: "Oldtimergrens (" + oldtimerAge(params) + " jaar)", value: ageAdjustment(listing.year, currentYear, params.horizon, oldtimerAge(params)) },
    ];
  }

  function annualRate(listing, params, currentYear) {
    var sum = rateParts(listing, params, currentYear).reduce(function (a, p) { return a + p.value; }, 0);
    return clamp(sum, MIN_RATE, MAX_RATE);
  }

  function yearlyCosts(p) {
    return p.storage_per_month * 12 + p.insurance_per_year + p.tax_per_year + p.maintenance_per_year;
  }

  /* Waarde waarmee je start: een koopje telt maar gedeeltelijk mee (deal_credit %),
     te veel betalen verlies je meteen volledig. */
  function startValue(listing, p) {
    var fair = listing.fair || listing.price;
    if (fair > listing.price) return listing.price + (fair - listing.price) * (p.deal_credit / 100);
    return fair;
  }

  function project(listing, p, currentYear) {
    var h = Math.max(1, p.horizon);
    var ratePct = annualRate(listing, p, currentYear);
    var start = startValue(listing, p);
    var value = start * Math.pow(1 + ratePct / 100, h);
    var sellNet = value * (1 - p.sell_pct / 100);
    var costs = yearlyCosts(p);
    var invested = listing.price + p.buy_costs + costs * h;
    var net = sellNet - invested;
    var annual = Math.pow(Math.max(sellNet, 1) / invested, 1 / h) - 1;
    return {
      ratePct: ratePct,
      start: start,
      value: value,
      sellNet: sellNet,
      yearlyCosts: costs,
      invested: invested,
      net: net,
      roi: net / invested,
      annual: annual,
    };
  }

  /* Waarde en totale investering per jaar, voor de grafiek in het detailpaneel. */
  function series(listing, p, currentYear) {
    var proj = project(listing, p, currentYear);
    var out = [];
    for (var t = 0; t <= p.horizon; t++) {
      out.push({
        t: t,
        value: proj.start * Math.pow(1 + proj.ratePct / 100, t),
        invested: listing.price + p.buy_costs + proj.yearlyCosts * t,
      });
    }
    return out;
  }

  function floor50(x) {
    return Math.max(0, Math.floor(x / 50) * 50);
  }

  /* Biedadvies: openingsbod + maximumprijs waarbij het minimumrendement nog gehaald wordt.
     - openingsbod: laagste van vraagprijs en marktwaarde, min een korting die groeit met de tijd
       online en het aantal minpunten, en kleiner wordt als de verkoper al zakte;
     - maximum: hoogste aankoopprijs met een rendement per jaar >= target_return (standaard 5%). */
  function bidAdvice(listing, params, currentYear) {
    var fair = listing.fair || listing.price;
    var base = Math.min(listing.price, fair);
    var days = listing.days || 0;
    var disc = days >= 90 ? 0.12 : days >= 45 ? 0.08 : 0.05;
    if (listing.drop > 0) disc -= 0.02;
    var neg = ((listing.cond && listing.cond.neg) || []).length;
    disc += Math.min(0.09, 0.03 * neg);
    disc = clamp(disc, 0.02, 0.2);

    var target = (params.target_return != null ? params.target_return : 5) / 100;
    function ok(p) {
      var l2 = {};
      for (var k in listing) l2[k] = listing[k];
      l2.price = p;
      return project(l2, params, currentYear).annual >= target;
    }
    var lo = 0, hi = Math.max(listing.price, fair) * 2;
    if (!ok(100)) {
      hi = 0;
    } else {
      for (var i = 0; i < 40; i++) {
        var mid = (lo + hi) / 2;
        if (ok(mid)) lo = mid; else hi = mid;
      }
      hi = lo;
    }
    var max = floor50(hi);
    var bid = floor50(base * (1 - disc));
    return {
      bid: Math.min(bid, max),
      max: max,
      discount: disc,
      target: target,
      worth: max >= bid, // vergeleken met het onafgekapte openingsbod
      atAsking: max >= listing.price,
    };
  }

  /* Score 0-100. Gewichten komen uit de schuifregelaars in het dashboard. */
  function score(listing, model, proj, w) {
    var parts = {
      ret: clamp((proj.annual + 0.05) / 0.15, 0, 1),
      deal: clamp(((listing.fair || listing.price) / listing.price - 0.8) / 0.4, 0, 1),
      rarity: (((model && model.rarity) || 3) - 1) / 4,
      demand: (((model && model.demand) || 3) - 1) / 4,
      conf: listing.conf == null ? 0.5 : listing.conf,
      cond: listing.cond && listing.cond.score != null ? clamp((listing.cond.score + 4) / 8, 0, 1) : 0.5,
    };
    var total = 0;
    var weight = 0;
    Object.keys(parts).forEach(function (k) {
      var wk = w[k] || 0;
      total += parts[k] * wk;
      weight += wk;
    });
    return { value: weight ? (100 * total) / weight : 0, parts: parts };
  }

  return {
    OLDTIMER_AGE: OLDTIMER_AGE,
    DEFAULT_WEIGHTS: DEFAULT_WEIGHTS,
    bidAdvice: bidAdvice,
    oldtimerAge: oldtimerAge,
    ageAdjustment: ageAdjustment,
    rateParts: rateParts,
    annualRate: annualRate,
    yearlyCosts: yearlyCosts,
    startValue: startValue,
    project: project,
    series: series,
    score: score,
  };
});
