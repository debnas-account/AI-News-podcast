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
.player{margin:14px 0 6px}
.player audio{display:none}
.seek{-webkit-appearance:none;appearance:none;display:block;width:100%;height:28px;margin:0;background:transparent;cursor:pointer;--p:0%}
.seek::-webkit-slider-runnable-track{height:6px;border-radius:3px;background:linear-gradient(to right,var(--text) var(--p),rgba(245,248,255,.25) var(--p))}
.seek::-moz-range-track{height:6px;border-radius:3px;background:linear-gradient(to right,var(--text) var(--p),rgba(245,248,255,.25) var(--p))}
.seek::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:18px;height:18px;margin-top:-6px;border-radius:50%;background:var(--text);border:0}
.seek::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:var(--text);border:0}
.times{display:flex;justify-content:space-between;color:var(--blue);font-size:14px;font-variant-numeric:tabular-nums}
.controls{display:flex;align-items:center;justify-content:center;gap:26px;margin-top:6px}
.controls button{display:flex;align-items:center;justify-content:center;padding:0;border:0;border-radius:50%;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
.skip{width:64px;height:64px;background:transparent;color:var(--text)}
.skip svg{width:52px;height:52px}
.play{width:96px;height:96px;background:var(--text);color:var(--bg)}
.play svg{width:44px;height:44px}
.play .i-pause,.playing .play .i-play{display:none}
.playing .play .i-pause{display:block}
.controls button:active{transform:scale(.94)}
.controls button:focus-visible{outline:3px solid var(--amber);outline-offset:3px}
.older .play{width:72px;height:72px}
.older .play svg{width:32px;height:32px}
.older .skip{width:52px;height:52px}
.older .skip svg{width:42px;height:42px}
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
.feed button{background:var(--rasp);color:var(--text);border:0;border-radius:10px;padding:10px 16px;font:inherit;font-weight:600;cursor:pointer}
ol{padding-left:20px;margin:8px 0 0}
footer{color:var(--blue);font-size:14px;margin-top:28px}
"""


_SKIP_ARC = (
    '<path d="M24 8A17 17 0 1 1 8 19.2"/><path d="M24 2.5 17.5 8 24 13.5"/>'
)
_SKIP_TEXT = (
    '<text x="24" y="30.5" text-anchor="middle" font-size="14" font-weight="700" '
    'font-family="Arial,Helvetica,sans-serif" fill="currentColor" stroke="none">10</text>'
)
_SVG = 'viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"'
ICON_BACK = f"<svg {_SVG}>{_SKIP_ARC}{_SKIP_TEXT}</svg>"
ICON_FWD = f'<svg {_SVG}><g transform="translate(48 0) scale(-1 1)">{_SKIP_ARC}</g>{_SKIP_TEXT}</svg>'
ICON_PLAY = (
    '<svg class="i-play" viewBox="0 0 48 48" fill="currentColor" aria-hidden="true"><path d="M17 9.5v29a2 2 0 0 0 3 1.7l23-14.5a2 2 0 0 0 0-3.4L20 7.8a2 2 0 0 0-3 1.7z"/></svg>'
    '<svg class="i-pause" viewBox="0 0 48 48" fill="currentColor" aria-hidden="true"><rect x="11" y="8" width="9" height="32" rx="2.5"/><rect x="28" y="8" width="9" height="32" rx="2.5"/></svg>'
)

# Eigen speler: grote afspeelknop, tien seconden terug en vooruit, en dezelfde
# knoppen op het vergrendelscherm (Media Session).
PLAYER_JS = """
(function(){
var SKIP=10,players=document.querySelectorAll('.player');
function fmt(s){s=Math.max(0,Math.round(s));return Math.floor(s/60)+':'+('0'+s%60).slice(-2)}
players.forEach(function(p){
var a=p.querySelector('audio'),play=p.querySelector('.play'),bar=p.querySelector('.seek'),
cur=p.querySelector('.cur'),rem=p.querySelector('.rem'),known=parseFloat(p.dataset.duration)||0,drag=false;
function dur(){return isFinite(a.duration)&&a.duration>0?a.duration:known}
function show(t){var d=dur();bar.style.setProperty('--p',(d?t/d*100:0)+'%');cur.textContent=fmt(t);rem.textContent='-'+fmt(d-t)}
function draw(){if(drag)return;var d=dur(),t=a.currentTime||0;bar.value=d?t/d*1000:0;show(t)}
function seek(t){var d=dur();t=Math.min(Math.max(0,t),d?Math.max(0,d-0.3):t);
if(a.readyState<1){a.preload='metadata';a.addEventListener('loadedmetadata',function(){a.currentTime=t},{once:true});a.load();show(t);bar.value=d?t/d*1000:0}
else{a.currentTime=t;draw()}}
function toggle(){if(a.paused){players.forEach(function(o){var x=o.querySelector('audio');if(x!==a)x.pause()});a.play()}else{a.pause()}}
play.addEventListener('click',toggle);
p.querySelector('.back').addEventListener('click',function(){seek((a.currentTime||0)-SKIP)});
p.querySelector('.fwd').addEventListener('click',function(){seek((a.currentTime||0)+SKIP)});
bar.addEventListener('input',function(){drag=true;show(bar.value/1000*dur())});
bar.addEventListener('change',function(){drag=false;seek(bar.value/1000*dur())});
['timeupdate','loadedmetadata','durationchange','seeked'].forEach(function(e){a.addEventListener(e,draw)});
a.addEventListener('play',function(){p.classList.add('playing');play.setAttribute('aria-label','Pause');
if('mediaSession' in navigator){try{
navigator.mediaSession.metadata=new MediaMetadata({title:p.dataset.title,artist:p.dataset.show,artwork:[{src:'cover.png',sizes:'1400x1400',type:'image/png'}]});
navigator.mediaSession.setActionHandler('play',function(){a.play()});
navigator.mediaSession.setActionHandler('pause',function(){a.pause()});
navigator.mediaSession.setActionHandler('seekbackward',function(){seek(a.currentTime-SKIP)});
navigator.mediaSession.setActionHandler('seekforward',function(){seek(a.currentTime+SKIP)});
navigator.mediaSession.setActionHandler('seekto',function(d){if(d&&d.seekTime!=null)seek(d.seekTime)});
}catch(e){}}});
function stopped(){p.classList.remove('playing');play.setAttribute('aria-label','Play')}
a.addEventListener('pause',stopped);a.addEventListener('ended',stopped);
draw();
});
})();
"""


def _player(ep: dict, latest: bool, show: str) -> str:
    preload = "metadata" if latest else "none"
    return f"""<div class="player" data-duration="{ep['duur']}" data-title="{escape(ep['titel'], quote=True)}" data-show="{escape(show, quote=True)}">
<audio preload="{preload}" src="{escape(ep['bestand'], quote=True)}"></audio>
<input class="seek" type="range" min="0" max="1000" step="1" value="0" aria-label="Position in episode">
<div class="times"><span class="cur">0:00</span><span class="rem">-{_duur(ep['duur'])}</span></div>
<div class="controls">
<button type="button" class="skip back" aria-label="Back 10 seconds">{ICON_BACK}</button>
<button type="button" class="play" aria-label="Play">{ICON_PLAY}</button>
<button type="button" class="skip fwd" aria-label="Forward 10 seconds">{ICON_FWD}</button>
</div>
</div>"""


def _episode_card(ep: dict, latest: bool, show: str = "") -> str:
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
    return f"""<section class="card{' latest' if latest else ''}">
{label}<h2>{escape(ep['titel'])}</h2>
<p class="meta">{escape(datum_voluit(d))} · {_duur(ep['duur'])} min</p>
{_player(ep, latest, show)}
<p style="margin-top:14px">{escape(ep['samenvatting'])}</p>
{sources}
</section>"""


def build_index(episodes: list[dict], config: dict) -> str:
    base = config["base_url"].rstrip("/")
    feed_url = f"{base}/feed.xml"
    if episodes:
        latest = _episode_card(episodes[0], True, config["title"])
        older = "".join(_episode_card(e, False, config["title"]) for e in episodes[1:])
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
<script>{PLAYER_JS}</script>
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
