# AI News in Ten Minutes

Een dagelijkse, volledig geautomatiseerde Engelstalige podcast van ongeveer tien minuten met
het AI-nieuws van de afgelopen 24 uur: eerst de wereld, aan het einde Nederland.

## Hoe het werkt

1. **Elke ochtend rond 04:07 uur** (Europe/Amsterdam) start een geplande Claude-sessie in de
   cloud. Er hoeft geen computer aan te staan.
2. De sessie volgt [`PRODUCTIE.md`](PRODUCTIE.md): nieuwskandidaten ophalen uit ruim dertig
   RSS-feeds, aanvullen met zoeken op het web, selecteren, controleren bij de bron en een script
   schrijven in `episodes/JJJJ-MM-DD.md`.
3. `./podcast.sh publiceer` zet het script om in spraak, bouwt de podcastfeed en de afspeelpagina
   en zet alles op de branch `gh-pages`, die via GitHub Pages publiek bereikbaar is.
4. Apple Podcasts op de iPhone haalt de nieuwe aflevering op uit de feed.

| Wat | Waar |
|---|---|
| Podcastfeed | `https://debnas-account.github.io/AI-News-podcast/feed.xml` |
| Afspeelpagina | `https://debnas-account.github.io/AI-News-podcast/` |
| Altijd de nieuwste aflevering | `https://debnas-account.github.io/AI-News-podcast/latest.mp3` |

## Eenmalig instellen

1. **GitHub Pages aanzetten**: Settings, Pages, bij 'Source' kiezen voor 'Deploy from a branch',
   branch `gh-pages`, map `/ (root)`. Bij een privérepository vraagt GitHub hiervoor een betaald
   abonnement; een openbare repository kan het gratis. De site zelf is in beide gevallen
   openbaar voor wie het adres kent.
2. **Abonneren op de iPhone**: open de afspeelpagina, kopieer het feedadres, ga in Podcasts naar
   Bibliotheek, tik op de drie puntjes en kies de optie om een programma via URL te volgen.
   Zet daarna bij het programma automatisch downloaden aan.
3. **Reserve**: zet de afspeelpagina op het beginscherm (deelknop, 'Zet op beginscherm'). Daar
   staat altijd de nieuwste aflevering, ook als Podcasts de feed nog niet heeft ververst.

## Aanpassen

Alles staat in [`config.json`](config.json):

- `tts.voice`: de stem. Beschikbaar zijn onder meer `en-US-AndrewMultilingualNeural`,
  `en-US-BrianMultilingualNeural`, `en-US-AvaMultilingualNeural`,
  `en-US-EmmaMultilingualNeural`, `en-GB-RyanNeural` en `en-GB-SoniaNeural`.
- `tts.rate`: het spreektempo, bijvoorbeeld `+8%` voor iets vlotter.
- `target_words`: de richtlijn voor de lengte. De stem spreekt ongeveer 147 woorden per minuut.
- `pronunciation`: woorden die de stem anders moet uitspreken.
- `feeds`: de nieuwsbronnen. `"filter": true` laat alleen berichten door die over AI gaan.
- `keep_episodes`: hoeveel afleveringen in de feed blijven staan.

De redactionele lijn (selectie, toon, opbouw, regels voor juistheid) staat in `PRODUCTIE.md`.
Het tijdstip pas je aan bij de geplande taak in Claude.

## Handmatig gebruiken

```bash
./podcast.sh kandidaten
```

```bash
./podcast.sh controleer episodes/2026-11-15.md
```

```bash
./podcast.sh publiceer episodes/2026-11-15.md
```

Met `--lokaal` bouwt `publiceer` alleen een proefversie in `build/site`, zonder iets te pushen.

## Kosten en kanttekeningen

- **Spraak**: de stemmen komen via het opensourcepakket `edge-tts` van de voorleesdienst van
  Microsoft Edge. Dat kost niets en klinkt goed, maar het is geen officiële API: het kan
  onaangekondigd stoppen met werken en de gebruiksvoorwaarden voor dit soort gebruik zijn niet
  duidelijk. Officiële alternatieven met een gratis tegoed dat voor dit volume (ongeveer
  300.000 tekens per maand) volstaat, zijn Azure AI Speech (dezelfde stemmen) en Google Cloud
  Text-to-Speech (Chirp 3 HD). Controleer de actuele voorwaarden voordat je overstapt.
- **Claude**: de dagelijkse sessie telt mee in het gebruik van het Claude-abonnement.
- **Juistheid**: het script wordt door AI geschreven op basis van bronnen die het zelf opent.
  De regels in `PRODUCTIE.md` zijn streng, maar fouten blijven mogelijk. De bronnen staan bij
  elke aflevering in de shownotes.
- **Opslag**: `gh-pages` bestaat steeds uit één commit met de laatste veertien afleveringen,
  zodat de repository niet volloopt met oude audio.
