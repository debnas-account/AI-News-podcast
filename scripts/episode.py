"""Inlezen en controleren van een afleveringsbestand (episodes/JJJJ-MM-DD.md)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PAUZE = "[pauze]"
PAUZES = ("[pauze]", "[pause]")


@dataclass
class Episode:
    path: Path
    datum: date
    titel: str
    samenvatting: str
    script: str
    bronnen: list[dict] = field(default_factory=list)

    @property
    def paragraphs(self) -> list[str]:
        """Alinea's van het script; '[pauze]' blijft als los element staan."""
        return [p.strip() for p in re.split(r"\n\s*\n", self.script) if p.strip()]

    @property
    def word_count(self) -> int:
        text = self.script.replace(PAUZE, " ").replace("[pause]", " ")
        return len(re.findall(r"\b[\w'’-]+\b", text))


def parse(path: str | Path) -> Episode:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\s*---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        raise ValueError("Het bestand moet beginnen met een blok tussen twee regels '---'.")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    for english, dutch in (("date", "datum"), ("title", "titel"), ("summary", "samenvatting")):
        if english in meta and dutch not in meta:
            meta[dutch] = meta[english]
    body = match.group(2)

    sections: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        heading = re.match(r"#{1,3}\s+(.+?)\s*$", line)
        if heading and heading.group(1).lower() in ("script", "bronnen", "sources"):
            current = "bronnen" if heading.group(1).lower() == "sources" else heading.group(1).lower()
            sections[current] = ""
        elif current:
            sections[current] += line + "\n"

    for key in ("datum", "titel", "samenvatting"):
        if not meta.get(key):
            raise ValueError(f"Veld '{key}' ontbreekt in de kop van het bestand.")
    if not sections.get("script", "").strip():
        raise ValueError("De sectie '# Script' ontbreekt of is leeg.")

    bronnen = []
    for line in sections.get("bronnen", "").splitlines():
        m = re.search(r"\[(.+?)\]\((https?://[^)\s]+)\)\s*(?:[–—-]\s*(.+))?", line)
        if m:
            bronnen.append({"titel": m.group(1).strip(), "url": m.group(2), "bron": (m.group(3) or "").strip()})

    return Episode(
        path=path,
        datum=date.fromisoformat(meta["datum"]),
        titel=meta["titel"],
        samenvatting=meta["samenvatting"],
        script=sections["script"].strip(),
        bronnen=bronnen,
    )


def check(ep: Episode, config: dict) -> tuple[list[str], list[str]]:
    """Geef (fouten, waarschuwingen). Fouten blokkeren publicatie."""
    errors, warnings = [], []
    lo, hi = config["target_words"]
    words = ep.word_count

    if ep.path.stem != ep.datum.isoformat():
        errors.append(f"Bestandsnaam ({ep.path.name}) en datum ({ep.datum}) komen niet overeen.")
    if words < 250:
        errors.append(f"Het script telt maar {words} woorden; dat is te kort voor een aflevering.")
    elif words < lo:
        warnings.append(f"Het script telt {words} woorden (richtlijn {lo}-{hi}). Prima op een rustige nieuwsdag, vul niet op.")
    elif words > hi:
        warnings.append(f"Het script telt {words} woorden (richtlijn {lo}-{hi}): de aflevering wordt langer dan tien minuten.")
    if re.search(r"https?://|www\.", ep.script):
        errors.append("Het script bevat een webadres. Zet links alleen onder '# Bronnen'.")
    if re.search(r"^\s*([-*+]|\d+\.)\s", ep.script, re.MULTILINE):
        errors.append("Het script bevat opsommingstekens. Schrijf lopende tekst voor het oor.")
    if re.search(r"^#+\s", ep.script, re.MULTILINE):
        errors.append("Het script bevat tussenkopjes. Gebruik '[pauze]' tussen onderdelen.")
    nl = len(re.findall(r"\b(het|een|van|voor|niet|ook|wordt|zijn|naar|maar)\b", ep.script, re.IGNORECASE))
    en = len(re.findall(r"\b(the|and|of|that|with|for|is|are|this|but)\b", ep.script, re.IGNORECASE))
    if nl > en:
        errors.append("Het script lijkt Nederlandstalig. De podcast is Engelstalig: schrijf het script in het Engels.")
    doorverwijzingen = [b["url"] for b in ep.bronnen if re.search(r"news\.google\.com|bing\.com/news", b["url"])]
    if doorverwijzingen:
        errors.append("Onder '# Bronnen' staan doorverwijzingen van Google News of Bing. Zet er het echte artikeladres neer.")
    if re.search(r"[()]", ep.script):
        warnings.append("Het script bevat haakjes; die klinken niet goed. Maak er een bijzin of een losse zin van.")
    if re.search(r"\s[–—-]\s", ep.script):
        warnings.append("Het script bevat gedachtestreepjes. Gebruik komma's of maak twee zinnen.")
    if not ep.bronnen:
        errors.append("Er staan geen bronnen onder '# Bronnen'. Elke nieuwsclaim heeft een bron nodig.")
    elif len(ep.bronnen) < 4:
        warnings.append(f"Er staan maar {len(ep.bronnen)} bronnen in de shownotes.")
    if len(ep.titel) > 110:
        warnings.append("De titel is lang; houd hem onder de 110 tekens.")
    return errors, warnings
