#!/usr/bin/env bash
# Startpunt voor alle podcasttaken. Maakt zo nodig een virtuele omgeving aan.
#
#   ./podcast.sh kandidaten              nieuwskandidaten van de afgelopen 26 uur ophalen
#   ./podcast.sh controleer <aflevering> script controleren (opbouw, lengte) zonder audio te maken
#   ./podcast.sh publiceer <aflevering>  audio maken, feed bijwerken en alles pushen
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt
fi

exec .venv/bin/python -m scripts.cli "$@"
