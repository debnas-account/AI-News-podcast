"""Gedeelde hulpfuncties: configuratie, paden en subprocessen."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
EPISODES = ROOT / "episodes"

# De podcast en de site zijn Engelstalig; datums dus ook.
MAANDEN = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]
DAGEN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def tz(config: dict) -> ZoneInfo:
    return ZoneInfo(config["timezone"])


def datum_voluit(d) -> str:
    """'Sunday 15 November 2026'"""
    return f"{DAGEN[d.weekday()]} {d.day} {MAANDEN[d.month - 1]} {d.year}"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Voer een commando uit en geef stdout/stderr terug als tekst."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Commando mislukt ({result.returncode}): {' '.join(cmd)}\n{result.stdout}\n{result.stderr}"
        )
    return result


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
