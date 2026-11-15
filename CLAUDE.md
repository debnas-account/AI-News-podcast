# AI News in Ten Minutes

Deze repository produceert elke ochtend automatisch een Engelstalige podcast over AI-nieuws.

- **Dagelijkse aflevering maken**: volg `PRODUCTIE.md` stap voor stap. Dat document bevat de
  werkwijze, de redactionele regels en het format.
- **Opbouw**: `config.json` (titel, stem, feeds, lengte), `scripts/` (kandidaten ophalen, audio
  maken, site bouwen, publiceren), `episodes/` (één markdownbestand per aflevering),
  `assets/cover.png` (omslag). Alles loopt via `./podcast.sh`.
- **Branches**: de code en de scripts staan op `main`. De publieke site (feed, afspeelpagina en
  audio) staat op `gh-pages` en wordt door `./podcast.sh publiceer` volledig overschreven: die
  branch bestaat steeds uit één commit. Bewerk `gh-pages` nooit met de hand.
- **Taal**: de podcast, de feed en de afspeelpagina zijn Engelstalig. De documentatie, de
  instructies en de meldingen van de scripts in deze repository zijn in het Nederlands.
- **Privacy**: zet geen persoonlijke gegevens van de eigenaar in bestanden of afleveringen.
