"""Refresh the "From the blog" section of profile/README.md from nodalstudio.io.

Reads the public RSS feed, then each article page for its poster (og:image), tags
(article:tag) and category (JSON-LD articleSection). Writes rounded thumbnails of the
latest articles to profile/assets/blog/ and rewrites the blocks between the
BLOG / TAGS markers of the README. Run by .github/workflows/update-blog.yml.

    pip install pillow
    python scripts/update_blog.py
"""

import hashlib
import html
import io
import json
import re
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from PIL import Image, ImageDraw

SITE = "https://nodalstudio.io"
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "profile" / "README.md"
THUMBS = ROOT / "profile" / "assets" / "blog"
RAW = "https://raw.githubusercontent.com/NodalStudio/.github/main/profile/assets/blog"
LATEST = 6
COLUMNS = 2
NBSP = "&nbsp;"
NB_HYPHEN = "&#8209;"  # keeps "#ai-agents" from wrapping at its hyphen
UA = {"User-Agent": "NodalStudio-profile-bot (+https://github.com/NodalStudio/.github)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def meta(page, prop):
    return [html.unescape(m) for m in
            re.findall(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', page)]


def article(item):
    page = get(item["link"]).decode()
    data = {}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        doc = json.loads(block)
        if doc.get("@type") in ("Article", "BlogPosting"):
            data = doc
    images = meta(page, "og:image")
    if not images:
        raise SystemExit(f"no og:image on {item['link']}")
    return {**item, "image": images[0], "tags": meta(page, "article:tag"),
            "category": data.get("articleSection", "")}


def feed():
    root = ET.fromstring(get(f"{SITE}/rss.xml"))
    items = [{
        "title": i.findtext("title").strip(),
        "link": i.findtext("link").strip(),
        "date": parsedate_to_datetime(i.findtext("pubDate")),
    } for i in root.iter("item")]
    items.sort(key=lambda i: i["date"], reverse=True)
    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(article, items))


def slug(link):
    return link.rstrip("/").rsplit("/", 1)[-1]


def thumbnail(post):
    """800×420 poster with rounded corners; the content hash in the name busts caches."""
    src = Image.open(io.BytesIO(get(post["image"]))).convert("RGB")
    k, (w, h), radius = 2, (800, 420), 14
    ratio = max(w * k / src.width, h * k / src.height)
    src = src.resize((round(src.width * ratio), round(src.height * ratio)), Image.LANCZOS)
    left, top = (src.width - w * k) // 2, (src.height - h * k) // 2
    src = src.crop((left, top, left + w * k, top + h * k))
    mask = Image.new("L", src.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=radius * k, fill=255)
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    out.paste(src, (0, 0), mask)
    buf = io.BytesIO()
    out.resize((w, h), Image.LANCZOS).save(buf, "WEBP", quality=84, method=6)
    data = buf.getvalue()
    name = f"{slug(post['link'])}-{hashlib.sha256(data).hexdigest()[:8]}.webp"
    (THUMBS / name).write_bytes(data)
    return name


def tag_url(tag):
    return f"{SITE}/blog/tag/{urllib.parse.quote(tag)}/"


def shield(text):
    return urllib.parse.quote(text.replace("-", "--").replace("_", "__").replace(" ", "_"))


def esc(text):
    return html.escape(text, quote=True)


def render_posts(posts):
    THUMBS.mkdir(parents=True, exist_ok=True)
    keep = set()
    cells = []
    for post in posts[:LATEST]:
        name = thumbnail(post)
        keep.add(name)
        when = post["date"].strftime("%b %-d, %Y").upper()
        # phrases never break internally; lines only wrap between them
        kicker = f"{NBSP}· ".join(esc(x).replace(" ", NBSP) for x in filter(None, [when, post["category"].upper()]))
        tags = " ".join(f'<a href="{tag_url(t)}">#{esc(t).replace("-", NB_HYPHEN)}</a>' for t in post["tags"])
        cells.append(
            f'<td width="{100 // COLUMNS}%" valign="top">\n'
            f'<a href="{post["link"]}"><img src="{RAW}/{name}" width="100%" alt="{esc(post["title"])}"></a>\n'
            f"<p><sub>{kicker}</sub></p>\n"
            f'<p><a href="{post["link"]}"><b>{esc(post["title"])}</b></a></p>\n'
            f"<p><sub>{tags}</sub></p>\n</td>")
    for stale in THUMBS.glob("*.webp"):
        if stale.name not in keep:
            stale.unlink()
    # one table per row: GitHub stripes every second row of a table
    rows = ["<table>\n<tr>\n" + "\n".join(cells[i:i + COLUMNS]) + "\n</tr>\n</table>"
            for i in range(0, len(cells), COLUMNS)]
    return "\n\n".join(rows)


def render_stats(posts):
    dates = sorted(p["date"] for p in posts)
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    topics = {t for p in posts for t in p["tags"]}
    parts = [f"**{len(posts)} articles** since {dates[0]:%B %Y}"]
    if gaps:
        parts.append(f"a new one every **~{round(statistics.mean(gaps))} days**")
    parts += [f"**{len(topics)} topics**", f"latest on {dates[-1]:%B %-d, %Y}"]
    return " &nbsp;·&nbsp; ".join(parts)


def render_tags(posts):
    counts = {}
    for p in posts:
        for t in p["tags"]:
            counts[t] = counts.get(t, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "\n".join(
        f'<a href="{tag_url(t)}"><img alt="#{esc(t)} · {n}" '
        f'src="https://img.shields.io/badge/{shield("#" + t)}-{n}-FFFDEC?style=flat-square&labelColor=050607"></a>'
        for t, n in ordered)


def replace(text, marker, content):
    pattern = re.compile(rf"(<!-- {marker}:START -->).*?(<!-- {marker}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"marker {marker} missing from {README}")
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(2)}", text)


def main():
    posts = feed()
    if not posts:
        raise SystemExit("the feed is empty — refusing to blank the README section")
    text = README.read_text()
    text = replace(text, "BLOG-STATS", render_stats(posts))
    text = replace(text, "BLOG", render_posts(posts))
    text = replace(text, "TAGS", render_tags(posts))
    README.write_text(text)
    print(f"{len(posts)} articles, latest: {posts[0]['title']} ({datetime.now(timezone.utc):%F})")


if __name__ == "__main__":
    main()
