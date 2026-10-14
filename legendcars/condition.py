"""Staat van de auto inschatten uit de advertentietekst (NL/FR/DE/EN) en gestructureerde velden.

Resultaat: een score van -4 tot +4 en de redenen (pluspunten/minpunten) die in het dashboard verschijnen.
Een ontkenning vlak voor een minpunt ("geen roest", "kein Rost", "sans rouille") telt niet als minpunt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import normalize

MAX_SCORE = 4.0

POSITIVE = [
    (r"car ?pass|\bnap\b|nationale autopas", "Car-Pass/NAP", 1.0),
    (r"onderhoudsboek|onderhoudshistoriek|onderhoudshistorie|alle facturen|facturen aanwezig|scheckheft|serviceheft|checkheft"
     r"|lueckenlos|luckenlos|service ?history|carnet d ?entretien|factures|entretien suivi|full service|volledige historiek",
     "Onderhoudshistoriek", 1.0),
    (r"\b1e eigenaar|eerste eigenaar|\b1 eigenaar|erste hand|\b1 hand|erstbesitz|premiere main|1er proprietaire"
     r"|\b1 proprietaire|one owner|\b1 owner|\b1 vorbesitzer|ein vorbesitzer|einem vorbesitzer", "1e eigenaar", 1.0),
    (r"\b2e eigenaar|\b2 eigenaars|zweite hand|\b2 hand|\b2 vorbesitzer|deuxieme main", "2e eigenaar", 0.5),
    (r"garagewagen|garage ?gestald|altijd binnen|droog gestald|garagenwagen|garagenfahrzeug|garagengepflegt"
     r"|toujours au garage|stocke au sec|garage kept|always garaged", "Garagewagen", 1.0),
    (r"h kennzeichen|h zulassung|\bh kz\b|oldtimer ?(kenteken|plaat|inschrijving|zulassung)|\bo plaat|historisch kenteken"
     r"|carte grise collection", "Oldtimerplaat", 0.5),
    (r"tuv neu|neu tuv|hu neu|neue hu|tuv bis 20[23]\d|hu bis 20[23]\d|keuring ok|gekeurd voor verkoop|nieuwe apk|apk tot"
     r"|controle technique ok|ct ok|pickerl bis|pickerl neu|\bmot\b", "Keuring OK", 0.5),
    (r"roestvrij|geen roest|zonder roest|rostfrei|kein rost|keinen rost|sans rouille|no rust|rust ?free", "Roestvrij", 1.0),
    (r"originele staat|original ?zustand|unverbastelt|nicht verbastelt|etat d ?origine|matching numbers|onverbouwd|niet verbouwd"
     r"|alles origineel|komplett original", "Origineel", 0.5),
    (r"gerestaureerd|restauriert|restaure\b|restored", "Gerestaureerd", 0.5),
    (r"unfallfrei|schadevrij|ongevalvrij|sans accident|accident free|unbeschadigtes fahrzeug|nooit ongeval", "Schadevrij", 0.5),
    (r"distributie ?riem (vervangen|nieuw)|nieuwe distributie|zahnriemen (neu|gewechselt)|courroie de distribution (neuve|changee)"
     r"|timing belt (new|replaced)", "Distributie vervangen", 0.3),
]

NEGATION = r"(geen|zonder|kein|keinen|keine|nicht|ohne|sans|pas de|no|not|niet)\b(\s+\w+){0,2}\s*$"

NEGATIVE = [
    (r"\broest(?!vrij)|\brost\b|\brostig|rostet|rouille|\brust\b(?! ?free)|\brusty|doorgeroest|durchgerostet", "Roest", 1.5),
    (r"\bongeval(?!vrij)|\bunfall\b|\bunfallschaden|\bsinistre|\baccident\b(?! ?free)|schadeauto|reparierter? (unfall|schaden)",
     "Ongeval", 1.0),
    (r"getuned|chiptuning|umgebaut|verbouwd|tiefergelegt|verlaagd (onderstel|chassis)|verlaagde (vering|veren)|ringtool|track ?(car|day)|rennstrecke|circuit|tuning", "Getuned", 0.5),
    (r"motorschade|motor ?defe[ck]t|motorschaden|olieverbruik|olverbrauch|lekt olie|olverlust|zylinderkopfdichtung|koppakking"
     r"|getriebeschaden|lagerschaden|pleuellager|moteur hs|joint de culasse|head gasket", "Motorproblemen", 1.5),
    (r"zonder keuring|ohne tuv|ohne hu|tuv abgelaufen|hu abgelaufen|sans controle|zonder apk|abgemeldet seit", "Geen keuring", 1.0),
    (r"tauschmotor|austauschmotor|andere motor|motor vervangen|moteur (echange|remplace)", "Vervangen motor", 0.5),
    (r"lakschade|deuken|lackschaden|beulen|dellen|carrosserieschade", "Lak/deuken", 0.5),
]

_POS = [(re.compile(p), label, w) for p, label, w in POSITIVE]
_NEG = [(re.compile(p), label, w) for p, label, w in NEGATIVE]
_NEGATION = re.compile(NEGATION)


@dataclass
class Condition:
    score: float = 0.0
    pos: list[str] = field(default_factory=list)
    neg: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"score": round(self.score, 1), "pos": self.pos, "neg": self.neg}


def _negated(text: str, start: int) -> bool:
    return bool(_NEGATION.search(text[max(0, start - 25):start]))


def assess(text: str, owners: int | None = None, accident_free: bool | None = None) -> Condition:
    t = normalize(text)
    c = Condition()
    for rx, label, w in _POS:
        if rx.search(t):
            c.pos.append(label)
            c.score += w
    if "1e eigenaar" in c.pos and "2e eigenaar" in c.pos:
        c.pos.remove("2e eigenaar")
        c.score -= 0.5
    for rx, label, w in _NEG:
        if not any(not _negated(t, m.start()) for m in rx.finditer(t)):
            continue
        c.neg.append(label)
        c.score -= w
    if "Ongeval" in c.neg and "Schadevrij" in c.pos:
        # "unbeschädigt" in een formulierveld + "reparierter Unfallschaden" in de tekst: de tekst wint
        c.pos.remove("Schadevrij")
        c.score -= 0.5
    if owners is not None:
        if owners == 1 and "1e eigenaar" not in c.pos:
            c.pos.append("1e eigenaar")
            c.score += 1.0
        elif owners >= 5:
            c.neg.append(f"{owners} eigenaars")
            c.score -= 0.5
    if accident_free is True and "Schadevrij" not in c.pos and "Ongeval" not in c.neg:
        c.pos.append("Schadevrij")
        c.score += 0.5
    elif accident_free is False and "Ongeval" not in c.neg:
        c.neg.append("Ongeval")
        c.score -= 1.0
    c.score = max(-MAX_SCORE, min(MAX_SCORE, c.score))
    return c
