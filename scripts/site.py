"""Bouw de publieke site: podcastfeed (feed.xml), afspeelpagina (index.html) en latest.mp3."""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from email.utils import format_datetime
from html import escape
from pathlib import Path

from .common import ROOT, datum_voluit

INDEX = "episodes.json"


def load_index(site: Path) -> list[dict]:
    path = site / INDEX
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def guid(datum: str) -> str:
    return f"ai-news-{datum}"


def upsert(episodes: list[dict], entry: dict, keep: int) -> tuple[list[dict], list[dict]]:
    """Voeg de aflevering toe (of vervang die van dezelfde dag). Geeft (bewaard, verwijderd)."""
    episodes = [e for e in episodes if e["datum"] != entry["datum"]] + [entry]
    episodes.sort(key=lambda e: e["datum"], reverse=True)
    return episodes[:keep], episodes[keep:]


def _duur(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _shownotes_html(ep: dict) -> str:
    parts = [f"<p>{escape(ep['samenvatting'])}</p>"]
    if ep.get("bronnen"):
        parts.append("<p>Sources:</p><ul>")
        for b in ep["bronnen"]:
            suffix = f" ({escape(b['bron'])})" if b.get("bron") else ""
            parts.append(f'<li><a href="{escape(b["url"], quote=True)}">{escape(b["titel"])}</a>{suffix}</li>')
        parts.append("</ul>")
    parts.append("<p>This episode was compiled and voiced automatically by AI. Check important facts against the sources.</p>")
    return "".join(parts)


def build_feed(episodes: list[dict], config: dict) -> str:
    base = config["base_url"].rstrip("/")
    items = []
    for ep in episodes:
        published = datetime.fromisoformat(ep["gepubliceerd"])
        d = date.fromisoformat(ep["datum"])
        title = f"{d.day} {datum_voluit(d).split()[2]}: {ep['titel']}"
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(ep['samenvatting'])}</description>
      <content:encoded><![CDATA[{_shownotes_html(ep)}]]></content:encoded>
      <itunes:summary>{escape(ep['samenvatting'])}</itunes:summary>
      <enclosure url="{base}/{ep['bestand']}" length="{ep['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{guid(ep['datum'])}</guid>
      <pubDate>{format_datetime(published)}</pubDate>
      <itunes:duration>{int(round(ep['duur']))}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
      <link>{base}/</link>
    </item>""")
    last = format_datetime(datetime.fromisoformat(episodes[0]["gepubliceerd"])) if episodes else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(config['title'])}</title>
    <link>{base}/</link>
    <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml"/>
    <language>{config['language']}</language>
    <description>{escape(config['description'])}</description>
    <itunes:summary>{escape(config['description'])}</itunes:summary>
    <itunes:author>{escape(config['author'])}</itunes:author>
    <itunes:image href="{base}/cover.png"/>
    <image><url>{base}/cover.png</url><title>{escape(config['title'])}</title><link>{base}/</link></image>
    <itunes:category text="News"><itunes:category text="Tech News"/></itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:block>yes</itunes:block>
    <lastBuildDate>{last}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""


CSS = """
:root{--bg:#0E1B30;--card:#1A2C46;--text:#F5F8FF;--blue:#8FD3F0;--grey:#E7E6E6;--rasp:#E94B6B;--amber:#F2B84B;--coral:#FF8A7A}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:"Avenir Next","Avenir Next LT Pro",Avenir,"Segoe UI",system-ui,sans-serif;font-size:17px;line-height:1.55}
main{max-width:680px;margin:0 auto;padding:28px 16px 56px}
h1,h2,.label{font-family:"Arial Black",Arial,sans-serif;font-weight:900;text-transform:uppercase;letter-spacing:.02em}
h1{font-size:clamp(26px,7vw,38px);line-height:1.08;margin:0 0 8px}
h1 span{color:var(--rasp)}
.lead{color:var(--blue);margin:0 0 28px}
.label{font-size:12px;color:var(--amber);letter-spacing:.12em;margin:0 0 6px}
.card{background:var(--card);border-radius:16px;padding:20px;margin:0 0 16px}
.card.latest{border-top:4px solid var(--rasp)}
h2{font-size:20px;line-height:1.2;margin:0 0 10px}
.meta{color:var(--blue);font-size:15px;margin:0 0 12px}
audio{width:100%;margin:8px 0 4px}
p{margin:0 0 12px}
a{color:var(--blue)}
details{margin-top:10px}
summary{cursor:pointer;color:var(--amber);font-weight:600}
ul{padding-left:20px;margin:10px 0 0}
li{margin:0 0 6px;font-size:15px}
.older h2{font-size:16px;margin:0 0 4px}
.older .card{padding:16px}
.feed{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.feed code{flex:1 1 240px;background:var(--bg);border-radius:10px;padding:10px 12px;font-size:13px;overflow-wrap:anywhere;color:var(--grey)}
button{background:var(--rasp);color:var(--text);border:0;border-radius:10px;padding:10px 16px;font:inherit;font-weight:600;cursor:pointer}
ol{padding-left:20px;margin:8px 0 0}
footer{color:var(--blue);font-size:14px;margin-top:28px}
"""


def _episode_card(ep: dict, latest: bool) -> str:
    d = date.fromisoformat(ep["datum"])
    sources = ""
    if ep.get("bronnen"):
        lis = "".join(
            f'<li><a href="{escape(b["url"], quote=True)}" rel="noopener">{escape(b["titel"])}</a>'
            + (f" ({escape(b['bron'])})" if b.get("bron") else "") + "</li>"
            for b in ep["bronnen"]
        )
        sources = f"<details><summary>Sources ({len(ep['bronnen'])})</summary><ul>{lis}</ul></details>"
    label = '<p class="label">Latest episode</p>' if latest else ""
    preload = "metadata" if latest else "none"
    return f"""<section class="card{' latest' if latest else ''}">
{label}<h2>{escape(ep['titel'])}</h2>
<p class="meta">{escape(datum_voluit(d))} · {_duur(ep['duur'])} min</p>
<p>{escape(ep['samenvatting'])}</p>
<audio controls preload="{preload}" src="{escape(ep['bestand'], quote=True)}"></audio>
{sources}
</section>"""


def build_index(episodes: list[dict], config: dict) -> str:
    base = config["base_url"].rstrip("/")
    feed_url = f"{base}/feed.xml"
    if episodes:
        latest = _episode_card(episodes[0], True)
        older = "".join(_episode_card(e, False) for e in episodes[1:])
        older = f'<p class="label" style="margin-top:28px">Earlier episodes</p><div class="older">{older}</div>' if older else ""
    else:
        latest, older = '<section class="card"><p>No episode has been published yet.</p></section>', ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#0E1B30">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="AI News">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="cover.png">
<link rel="icon" href="cover.png">
<link rel="alternate" type="application/rss+xml" title="{escape(config['title'])}" href="feed.xml">
<title>{escape(config['title'])}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>AI News in <span>Ten Minutes</span></h1>
<p class="lead">Every morning, the past 24 hours in AI: the world first, then the Netherlands.</p>
{latest}
{older}
<section class="card" style="margin-top:28px">
<p class="label">Subscribe in Apple Podcasts</p>
<div class="feed"><code id="feed">{feed_url}</code><button type="button" onclick="navigator.clipboard.writeText(document.getElementById('feed').textContent).then(()=>{{this.textContent='Copied'}})">Copy</button></div>
<ol>
<li>Copy the address above.</li>
<li>Open Podcasts, go to Library and tap the three dots in the top right corner.</li>
<li>Choose the option to follow a show by URL and paste the address.</li>
</ol>
</section>
<footer>Compiled and voiced automatically by AI. Check important facts against the sources.</footer>
</main>
</body>
</html>
"""


def write_site(site: Path, episodes: list[dict], removed: list[dict], config: dict) -> None:
    """Schrijf alle sitebestanden naar `site` en ruim verlopen audio op."""
    for ep in removed:
        (site / ep["bestand"]).unlink(missing_ok=True)
    keep = {Path(ep["bestand"]).name for ep in episodes}
    for audio in (site / "audio").glob("*.mp3"):
        if audio.name not in keep:  # bijvoorbeeld een vervangen aflevering met een andere naam
            audio.unlink()
    (site / INDEX).write_text(json.dumps(episodes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (site / "feed.xml").write_text(build_feed(episodes, config), encoding="utf-8")
    (site / "index.html").write_text(build_index(episodes, config), encoding="utf-8")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    cover = ROOT / "assets" / "cover.png"
    if cover.exists():
        shutil.copyfile(cover, site / "cover.png")
    if episodes:
        shutil.copyfile(site / episodes[0]["bestand"], site / "latest.mp3")
