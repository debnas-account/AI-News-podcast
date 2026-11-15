"""Zet een script om in een mp3 met de Nederlandse neurale stemmen van Microsoft (via edge-tts).

Elke alinea wordt apart ingesproken (met herhaalpogingen), daarna worden de fragmenten
met korte pauzes aan elkaar gezet, op podcastvolume gebracht en als mp3 opgeslagen.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path

import edge_tts
import edge_tts.communicate as _edge_communicate

from .common import log, run
from .episode import PAUZES

# In een cloudsessie loopt verkeer via een proxy met een eigen certificaat. edge-tts
# gebruikt een vaste certificaatbundel, dus voegen we de bundel van de omgeving toe.
_ca = os.environ.get("SSL_CERT_FILE")
if _ca and os.path.exists(_ca) and hasattr(_edge_communicate, "_SSL_CTX"):
    try:
        _edge_communicate._SSL_CTX.load_verify_locations(cafile=_ca)
    except Exception as exc:  # pragma: no cover - alleen relevant achter een proxy
        log(f"Let op: extra certificaatbundel kon niet worden geladen ({exc}).")


def speakable(text: str, pronunciation: dict[str, str]) -> str:
    """Maak tekst geschikt om voor te lezen: opmaak weg, afkortingen uitgeschreven."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)      # markdownlinks
    text = re.sub(r"[*_`#>]+", "", text)                        # opmaaktekens
    text = text.replace("–", ",").replace("—", ",")             # gedachtestreepjes
    text = re.sub(r"\s+,", ",", text)
    for key in sorted(pronunciation, key=len, reverse=True):
        if re.fullmatch(r"\W+", key):
            text = text.replace(key, f" {pronunciation[key]} ")
        else:
            text = re.sub(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", pronunciation[key], text)
    return re.sub(r"\s+", " ", text).strip()


async def _speak(text: str, voice: str, rate: str, out: Path, attempts: int = 4) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(out))
            if out.exists() and out.stat().st_size > 1000:
                return
            raise RuntimeError("leeg audiobestand ontvangen")
        except Exception as exc:
            last_error = exc
            log(f"  spraakfragment mislukt (poging {attempt}/{attempts}): {type(exc).__name__}: {exc}")
            await asyncio.sleep(3 * attempt)
    raise RuntimeError(f"Spraaksynthese mislukt na {attempts} pogingen: {last_error}")


async def _speak_all(chunks: list[tuple[int, str]], voice: str, rate: str, workdir: Path) -> None:
    limiter = asyncio.Semaphore(3)

    async def one(index: int, text: str) -> None:
        async with limiter:
            await _speak(text, voice, rate, workdir / f"{index:03d}.mp3")

    await asyncio.gather(*(one(i, t) for i, t in chunks))


def duration_seconds(path: Path) -> float:
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ]).stdout.strip()
    return float(out)


def synthesize(paragraphs: list[str], out: Path, config: dict, tags: dict[str, str]) -> float:
    """Maak `out` (mp3) van de alinea's. Geeft de duur in seconden terug."""
    tts = config["tts"]
    workdir = out.parent / (out.stem + "-delen")
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)

    # Bepaal per alinea de tekst en de pauze erna.
    parts: list[tuple[int, str, float]] = []
    for para in paragraphs:
        if para.strip().lower() in PAUZES:
            if parts:
                i, t, _ = parts[-1]
                parts[-1] = (i, t, tts["section_pause"])
            continue
        text = speakable(para, config.get("pronunciation", {}))
        if text:
            parts.append((len(parts), text, tts["paragraph_pause"]))
    if not parts:
        raise ValueError("Er is geen tekst om in te spreken.")

    log(f"Inspreken: {len(parts)} alinea's met stem {tts['voice']} ...")
    asyncio.run(_speak_all([(i, t) for i, t, _ in parts], tts["voice"], tts["rate"], workdir))

    # Elk fragment naar wav met stilte erachter, daarna samenvoegen.
    listing = workdir / "lijst.txt"
    lines = []
    for index, _, pause in parts:
        wav = workdir / f"{index:03d}.wav"
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(workdir / f"{index:03d}.mp3"),
            "-af", f"apad=pad_dur={pause}", "-ar", "44100", "-ac", "1", str(wav),
        ])
        lines.append(f"file '{wav.name}'")
    listing.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-af", "loudnorm=I=-17:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "1",
        "-codec:a", "libmp3lame", "-b:a", "64k",
    ]
    for key, value in tags.items():
        cmd += ["-metadata", f"{key}={value}"]
    cmd.append(str(out))
    run(cmd)
    shutil.rmtree(workdir, ignore_errors=True)
    return duration_seconds(out)
