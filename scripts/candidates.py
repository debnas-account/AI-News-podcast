"""Haal nieuwskandidaten van de afgelopen uren op uit de RSS-feeds in config.json.

Het resultaat is een startlijst voor de redactie, geen eindselectie: titels en
samenvattingen uit feeds zijn onbevestigd en moeten bij de bron worden gecontroleerd.
"""
from __future__ import annotations

import calendar
import concurrent.futures as cf
import html
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import feedparser

from .common import BUILD, load_config, log, tz

USER_AGENT = "Mozilla/5.0 (compatible; podcast-feedreader/1.0)"

# "AI" alleen in hoofdletters, anders matcht het op allerlei gewone woorden.
AI_HOOFDLETTERS = re.compile(r"(?<![\w-])(AI|A\.I\.|AGI|LLM|GPU|GPT)(?![a-z])")
AI_TERMEN = re.compile(
    r"kunstmatige intelligentie|artifici[eë]le intelligentie|artificial intelligence|"
    r"openai|anthropic|chatgpt|claude|gemini|deepmind|mistral|nvidia|copilot|grok|xai\b|"
    r"deepseek|llama|hugging face|perplexity|midjourney|sora\b|"
    r"taalmodel|language model|machine learning|deep learning|neural net|neuraal netwerk|"
    r"chatbot|generatieve|generative|superintelligen|humanoid|humanoïde|deepfake|"
    r"datacenter|data center|algoritm|ai-verordening|ai act|ai-act|"
    r"\bagents?\b|\bagentic\b|\brobots?\b",
    re.IGNORECASE,
)


NL_WOORDEN = re.compile(
    r"\b(de|het|een|van|voor|met|op|en|is|bij|naar|om|niet|ook|aan|door|over|uit|wordt|zijn|dat|die)\b",
    re.IGNORECASE,
)


def is_dutch(text: str) -> bool:
    """Ruwe taalcheck: minstens twee gangbare Nederlandse woorden in de kop."""
    return len(NL_WOORDEN.findall(text)) >= 2


def real_url(link: str) -> str:
    """Bing Nieuws verpakt het echte adres in een doorverwijzing; pak het uit."""
    if "bing.com/news/apiclick" in link:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
        if query.get("url"):
            return query["url"][0]
    return link


def domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def is_ai(text: str) -> bool:
    return bool(AI_HOOFDLETTERS.search(text) or AI_TERMEN.search(text))


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_feed(feed: dict, cutoff: float, blocked: list[str]) -> tuple[dict, list[dict], str | None]:
    """Geef (feed, items, foutmelding). Probeert het bij een fout nog één keer."""
    last_error = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(feed["url"], headers={"User-Agent": USER_AGENT})
            data = urllib.request.urlopen(req, timeout=25).read()
            parsed = feedparser.parse(data)
            items = []
            for entry in parsed.entries:
                stamp = entry.get("published_parsed") or entry.get("updated_parsed")
                if not stamp:
                    continue
                ts = calendar.timegm(stamp)
                if ts < cutoff or ts > time.time() + 3600:
                    continue
                title = strip_html(entry.get("title", ""))
                summary = strip_html(entry.get("summary", ""))
                source = feed["name"]
                url = real_url(entry.get("link", ""))
                note = ""
                src = entry.get("source", {})
                src_title = src.get("title") if isinstance(src, dict) else None
                if "news.google.com" in feed["url"]:
                    # Google News geeft alleen een doorverwijzing, geen artikeladres.
                    if src_title:
                        source = src_title
                        title = re.sub(r"\s+-\s+" + re.escape(src_title) + r"$", "", title)
                    summary = ""
                    note = "alleen kop via Google News: zoek het artikel zelf op, dit adres is geen bron"
                elif "bing.com/news" in feed["url"]:
                    source = src_title or domain(url) or source
                haystack = f"{source} {url}".lower()
                if any(b in haystack for b in blocked):
                    continue
                if feed.get("lang") == "nl" and not is_dutch(title):
                    continue
                if feed.get("filter") and not is_ai(f"{title} {summary}"):
                    continue
                items.append({
                    "ts": ts,
                    "title": title,
                    "summary": summary[:280],
                    "url": url,
                    "note": note,
                    "source": source,
                    "region": feed["region"],
                })
            items.sort(key=lambda i: -i["ts"])
            return feed, items[: feed.get("max", 25)], None
        except Exception as exc:  # netwerkfouten mogen de run nooit stoppen
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(2)
    return feed, [], last_error


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def collect(hours: float | None = None) -> str:
    config = load_config()
    hours = hours or config.get("candidate_hours", 26)
    cutoff = time.time() - hours * 3600
    zone = tz(config)

    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        blocked = [b.lower() for b in config.get("blocked_sources", [])]
        results = list(pool.map(lambda f: fetch_feed(f, cutoff, blocked), config["feeds"]))

    seen: set[str] = set()
    by_region: dict[str, list[dict]] = {"wereld": [], "nederland": []}
    failed = []
    for feed, items, error in results:
        if error:
            failed.append(f"{feed['name']}: {error}")
        for item in items:
            key = norm_title(item["title"])
            if not key or key in seen:
                continue
            seen.add(key)
            by_region.setdefault(item["region"], []).append(item)

    now = datetime.now(zone)
    lines = [
        f"# Nieuwskandidaten, opgehaald {now:%d-%m-%Y %H:%M} ({config['timezone']})",
        "",
        f"Venster: de afgelopen {hours:g} uur. Dit zijn onbevestigde koppen uit RSS-feeds: "
        "controleer elk item bij de oorspronkelijke bron voordat het in het script komt. "
        "De tijd tussen haken is het moment van publicatie volgens de feed.",
        "",
    ]
    for region, kop in (("wereld", "Wereld"), ("nederland", "Nederland")):
        items = sorted(by_region.get(region, []), key=lambda i: -i["ts"])
        lines.append(f"## {kop} ({len(items)} items)")
        lines.append("")
        for item in items:
            when = datetime.fromtimestamp(item["ts"], timezone.utc).astimezone(zone)
            lines.append(f"- [{when:%d-%m %H:%M}] {item['source']}: {item['title']}")
            if item["summary"]:
                lines.append(f"  {item['summary']}")
            if item["note"]:
                lines.append(f"  ({item['note']})")
            else:
                lines.append(f"  {item['url']}")
        lines.append("")
    if failed:
        lines.append("## Feeds die niet bereikbaar waren")
        lines.append("")
        lines.extend(f"- {f}" for f in failed)
        lines.append("")

    BUILD.mkdir(exist_ok=True)
    out = BUILD / "kandidaten.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log(
        f"{len(by_region.get('wereld', []))} wereld- en {len(by_region.get('nederland', []))} "
        f"Nederlandse kandidaten; {len(failed)} van de {len(config['feeds'])} feeds onbereikbaar."
    )
    return str(out)
