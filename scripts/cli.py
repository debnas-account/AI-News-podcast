"""Commandoregel voor de podcast: kandidaten, controleer, publiceer."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import episode as episode_mod
from .common import BUILD, ROOT, datum_voluit, load_config, log, run, tz


# --------------------------------------------------------------------------- git

def git(*args: str, check: bool = True, env: dict | None = None):
    full_env = None
    if env:
        full_env = {**os.environ, **env}
    import subprocess
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, env=full_env)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} mislukt:\n{result.stdout}\n{result.stderr}")
    return result


def with_retries(action, what: str, attempts: int = 4):
    """Voer `action` uit tot het lukt; wacht 2, 4, 8 seconden tussen pogingen."""
    last = None
    for attempt in range(1, attempts + 1):
        result = action()
        if result.returncode == 0:
            return result
        last = result
        log(f"  {what} mislukt (poging {attempt}/{attempts}): {result.stderr.strip()[:300]}")
        if attempt < attempts:
            time.sleep(2 ** attempt)
    return last


def identity_env() -> dict:
    """Zorg dat commits altijd een auteur hebben, ook in een kale omgeving."""
    env = {}
    if not git("config", "user.name", check=False).stdout.strip():
        env.update(GIT_AUTHOR_NAME="AI-nieuws podcast", GIT_COMMITTER_NAME="AI-nieuws podcast")
    if not git("config", "user.email", check=False).stdout.strip():
        env.update(GIT_AUTHOR_EMAIL="noreply@anthropic.com", GIT_COMMITTER_EMAIL="noreply@anthropic.com")
    return env


# ---------------------------------------------------------------------- commando's

def cmd_kandidaten(args) -> int:
    from . import candidates
    path = candidates.collect(args.uren)
    print(path)
    return 0


def report_check(ep, config) -> bool:
    errors, warnings = episode_mod.check(ep, config)
    minutes = ep.word_count / 147
    log(f"Aflevering {ep.datum}: '{ep.titel}'")
    log(f"  {ep.word_count} woorden (ongeveer {minutes:.1f} minuten), {len(ep.bronnen)} bronnen")
    for w in warnings:
        log(f"  WAARSCHUWING: {w}")
    for e in errors:
        log(f"  FOUT: {e}")
    return not errors


def cmd_controleer(args) -> int:
    config = load_config()
    ep = episode_mod.parse(args.aflevering)
    return 0 if report_check(ep, config) else 1


def fetch_site(config: dict, site: Path) -> str | None:
    """Zet de huidige inhoud van de sitebranch in `site`. Geeft de commit terug, of None als de branch nog niet bestaat."""
    branch = config["site_branch"]
    shutil.rmtree(site, ignore_errors=True)
    site.mkdir(parents=True)
    listing = with_retries(lambda: git("ls-remote", "--heads", "origin", branch, check=False), "ls-remote")
    if listing.returncode != 0:
        raise RuntimeError("GitHub is niet bereikbaar; de site kan niet veilig worden bijgewerkt.")
    if not listing.stdout.strip():
        log(f"Branch {branch} bestaat nog niet; die wordt nu aangemaakt.")
        return None
    fetched = with_retries(lambda: git("fetch", "--depth", "1", "origin", branch, check=False), "fetch")
    if fetched.returncode != 0:
        raise RuntimeError(f"Ophalen van {branch} is mislukt.")
    parent = git("rev-parse", "FETCH_HEAD").stdout.strip()
    archive = BUILD / "site.tar"
    git("archive", "--format=tar", "-o", str(archive), parent)
    run(["tar", "-xf", str(archive), "-C", str(site)])
    archive.unlink()
    return parent


def push_site(config: dict, site: Path, parent: str | None, message: str) -> None:
    """Commit de map `site` als nieuwe inhoud van de sitebranch en push die.

    De branch bestaat steeds uit één commit, zodat oude audio geen ruimte blijft innemen.
    Lukt dat overschrijven niet, dan volgt een gewone commit bovenop de vorige.
    """
    branch = config["site_branch"]
    index = BUILD / "site.index"
    index.unlink(missing_ok=True)
    env = {"GIT_INDEX_FILE": str(index), "GIT_WORK_TREE": str(site), **identity_env()}
    git("add", "-A", ".", env=env)
    tree = git("write-tree", env=env).stdout.strip()
    index.unlink(missing_ok=True)

    orphan = git("commit-tree", tree, "-m", message, env=env).stdout.strip()
    lease = f"--force-with-lease=refs/heads/{branch}:{parent}" if parent else "--force-with-lease=refs/heads/" + branch + ":"
    result = with_retries(
        lambda: git("push", lease, "origin", f"{orphan}:refs/heads/{branch}", check=False),
        f"push naar {branch}", attempts=3,
    )
    if result.returncode == 0:
        return
    if parent:
        log("Overschrijven lukte niet; ik probeer een gewone commit bovenop de vorige.")
        stacked = git("commit-tree", tree, "-p", parent, "-m", message, env=env).stdout.strip()
        result = with_retries(
            lambda: git("push", "origin", f"{stacked}:refs/heads/{branch}", check=False),
            f"push naar {branch}",
        )
        if result.returncode == 0:
            return
    raise RuntimeError(f"Pushen naar {branch} is mislukt:\n{result.stderr}")


def push_source(config: dict, path: Path, message: str) -> None:
    """Commit het afleveringsbestand en push het naar de bronbranch."""
    branch = config["source_branch"]
    env = identity_env()
    git("add", "--", str(path.relative_to(ROOT)))
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        log("Het afleveringsbestand was al vastgelegd.")
    else:
        git("commit", "-m", message, env=env)
    for attempt in range(1, 5):
        result = git("push", "origin", f"HEAD:refs/heads/{branch}", check=False)
        if result.returncode == 0:
            return
        log(f"  push naar {branch} mislukt (poging {attempt}/4): {result.stderr.strip()[:300]}")
        git("pull", "--rebase", "origin", branch, check=False, env=env)
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Pushen naar {branch} is mislukt.")


def wait_until_live(config: dict, entry: dict, minutes: float) -> bool:
    """Wacht tot de nieuwe aflevering publiek in de feed staat en de audio bereikbaar is."""
    from .site import guid
    base = config["base_url"].rstrip("/")
    deadline = time.time() + minutes * 60
    needle = guid(entry["datum"])
    audio_ok = feed_ok = False
    while time.time() < deadline:
        try:
            bust = f"?t={int(time.time())}"
            req = urllib.request.Request(base + "/feed.xml" + bust, headers={"User-Agent": "podcast-check/1.0"})
            body = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
            feed_ok = needle in body and f'length="{entry["bytes"]}"' in body
            head = urllib.request.Request(base + "/" + entry["bestand"] + bust, method="HEAD", headers={"User-Agent": "podcast-check/1.0"})
            resp = urllib.request.urlopen(head, timeout=20)
            audio_ok = resp.status == 200 and int(resp.headers.get("Content-Length", "0")) == entry["bytes"]
            if feed_ok and audio_ok:
                return True
        except Exception:
            pass
        time.sleep(15)
    log(f"  feed bijgewerkt: {'ja' if feed_ok else 'nee'}; audio bereikbaar: {'ja' if audio_ok else 'nee'}")
    return False


def cmd_publiceer(args) -> int:
    from . import site as site_mod
    from . import tts

    config = load_config()
    zone = tz(config)
    ep = episode_mod.parse(args.aflevering)
    if not report_check(ep, config):
        log("Publicatie gestopt: los eerst de fouten op.")
        return 1

    BUILD.mkdir(exist_ok=True)
    filename = f"ai-news-{ep.datum.isoformat()}.mp3"
    mp3 = BUILD / filename
    seconds = tts.synthesize(
        ep.paragraphs, mp3, config,
        tags={
            "title": f"{ep.datum.isoformat()} {ep.titel}",
            "artist": config["author"],
            "album": config["title"],
            "date": str(ep.datum.year),
            "genre": "Podcast",
        },
    )
    log(f"Audio klaar: {mp3} ({seconds / 60:.1f} minuten, {mp3.stat().st_size / 1e6:.1f} MB)")

    site = BUILD / "site"
    parent = fetch_site(config, site) if not args.lokaal else None
    if args.lokaal:
        shutil.rmtree(site, ignore_errors=True)
        site.mkdir(parents=True)
    (site / "audio").mkdir(exist_ok=True)
    shutil.copyfile(mp3, site / "audio" / filename)

    entry = {
        "datum": ep.datum.isoformat(),
        "titel": ep.titel,
        "samenvatting": ep.samenvatting,
        "bestand": f"audio/{filename}",
        "bytes": mp3.stat().st_size,
        "duur": round(seconds, 1),
        "gepubliceerd": datetime.now(zone).replace(microsecond=0).isoformat(),
        "bronnen": ep.bronnen,
    }
    episodes, removed = site_mod.upsert(site_mod.load_index(site), entry, config["keep_episodes"])
    site_mod.write_site(site, episodes, removed, config)

    if args.lokaal:
        log(f"Lokale proefversie staat in {site} (er is niets gepusht).")
        return 0

    message = f"Aflevering {ep.datum.isoformat()}: {ep.titel}"
    push_site(config, site, parent, message)
    log(f"Site gepusht naar {config['site_branch']}.")
    push_source(config, ep.path.resolve(), message)
    log(f"Script vastgelegd op {config['source_branch']}.")

    if wait_until_live(config, entry, args.wacht):
        print(f"LIVE: {config['base_url']}/ ({datum_voluit(ep.datum)}, {seconds / 60:.1f} min)")
        return 0
    print(
        "GEPUSHT, MAAR NIET BEVESTIGD: de aflevering staat op GitHub, maar was binnen "
        f"{args.wacht:g} minuten nog niet zichtbaar op {config['base_url']}/feed.xml. "
        "Controleer of GitHub Pages aanstaat voor de sitebranch."
    )
    return 2


def cmd_site(args) -> int:
    """Bouw feed en afspeelpagina opnieuw uit de bestaande afleveringen, zonder nieuwe audio."""
    from . import site as site_mod

    config = load_config()
    BUILD.mkdir(exist_ok=True)
    site = BUILD / "site"
    parent = fetch_site(config, site)
    episodes = site_mod.load_index(site)
    if parent is None or not episodes:
        log("Er staat nog geen site met afleveringen; gebruik eerst 'publiceer'.")
        return 1
    site_mod.write_site(site, episodes, [], config)
    if args.lokaal:
        log(f"Lokale proefversie staat in {site} (er is niets gepusht).")
        return 0
    push_site(config, site, parent, "Site opnieuw gebouwd")
    log(f"Site gepusht naar {config['site_branch']} ({len(episodes)} afleveringen).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="podcast.sh", description="Dagelijkse AI-nieuwspodcast")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("kandidaten", help="nieuwskandidaten ophalen uit de RSS-feeds")
    p.add_argument("--uren", type=float, default=None, help="tijdvenster in uren (standaard uit config.json)")
    p.set_defaults(func=cmd_kandidaten)

    p = sub.add_parser("controleer", help="afleveringsbestand controleren zonder audio te maken")
    p.add_argument("aflevering")
    p.set_defaults(func=cmd_controleer)

    p = sub.add_parser("publiceer", help="audio maken, site bijwerken en pushen")
    p.add_argument("aflevering")
    p.add_argument("--lokaal", action="store_true", help="alleen lokaal bouwen in build/site, niets pushen")
    p.add_argument("--wacht", type=float, default=6, help="minuten wachten tot de aflevering live staat")
    p.set_defaults(func=cmd_publiceer)

    p = sub.add_parser("site", help="feed en afspeelpagina opnieuw bouwen zonder nieuwe aflevering")
    p.add_argument("--lokaal", action="store_true", help="alleen lokaal bouwen in build/site, niets pushen")
    p.set_defaults(func=cmd_site)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        log(f"FOUT: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
