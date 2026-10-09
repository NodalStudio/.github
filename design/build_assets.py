"""Build the static visual assets of the organisation profile (profile/assets/).

Text is set in the brand typefaces (Cabinet Grotesk, General Sans) and converted to
vector paths, so the SVGs render identically everywhere without shipping font files.
The fonts are the self-hosted woff2 files of the NodalWebsite repository:

    pip install fonttools brotli uharfbuzz pillow
    python design/build_assets.py --fonts ../NodalWebsite/public/fonts \
                                  --work  ../NodalWebsite/public/work

Re-run it whenever the copy below or the portfolio screenshots change.
"""

import argparse
import html
import io
import math
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "profile" / "assets"

W = 1200  # every SVG shares the README content width ratio

THEMES = {
    "light": dict(bg="#FFFDEC", ink="#050607", muted="#6B6A60", line="#05060724",
                  soft="#0506070F", badge_bg="#231F20", badge_fg="#FFFDEC", page="#FFFFFF"),
    "dark": dict(bg="#050607", ink="#FFFDEC", muted="#A6A493", line="#FFFDEC29",
                 soft="#FFFDEC0F", badge_bg="#FFFDEC", badge_fg="#050607", page="#0D1117"),
}

# Monogram, normalised to a 114.17 × 114.16 box (from the website favicon / nav badge).
BADGE_BG = ("M27.01 0h60.16c14.85 0 27 12.15 27 27v60.16c0 14.85-12.15 27-27 27H27.01"
            "c-14.85 0-27-12.15-27-27V27.01C0 12.15 12.15 0 27.01 0z")
BADGE_I = "M22.03 15.58v83.01"
BADGE_S = ("M23.2 18.7l41.52 65.79.11.07c2.96 5.04 9.16 8.48 16.01 8.48 9.8 0 17.74-7.04 "
           "17.74-15.72 0-4.46-1.26-7.61-3.4-10.21l-28.57-22.31c-2.14-2.6-3.05-5.52-3.05-8.97 "
           "0-8.68 7.94-15.72 17.74-15.72 6.85 0 12.79 3.44 15.75 8.48")

REDUCED_MOTION = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def num(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


class Face:
    """A woff2 face, shaped with HarfBuzz (kerning, ligatures) and drawn as SVG paths."""

    def __init__(self, path):
        tt = TTFont(path)
        tt.flavor = None
        buf = io.BytesIO()
        tt.save(buf)
        self.data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(self.data))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upm = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(self.data))

    def _shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        return zip(buf.glyph_infos, buf.glyph_positions)

    def width(self, text, size, tracking=0):
        s = size / self.upm
        run = list(self._shape(text))
        return sum(p.x_advance for _, p in run) * s + tracking * max(len(run) - 1, 0)

    def path(self, text, x, y, size, tracking=0, anchor="start"):
        if anchor != "start":
            w = self.width(text, size, tracking)
            x -= w if anchor == "end" else w / 2
        s = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=num)
        cx = 0.0
        for info, pos in self._shape(text):
            name = self.order[info.codepoint]
            ox = x + cx + pos.x_offset * s
            self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, ox, y - pos.y_offset * s)))
            cx += pos.x_advance * s + tracking
        return pen.getCommands()

    def wrap(self, text, size, max_width):
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and self.width(trial, size) > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line]


def svg(h, body, style, label):
    label = html.escape(label)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" '
            f'height="{h}" role="img" aria-label="{label}"><title>{label}</title>'
            f"<style>{style}{REDUCED_MOTION}</style>{body}</svg>\n")


def badge(x, y, size, t, cls="badge"):
    k = size / 114.17
    return (f'<g class="{cls}" transform="translate({num(x)} {num(y)}) scale({num(k)})">'
            f'<path d="{BADGE_BG}" fill="{t["badge_bg"]}"/>'
            f'<g fill="none" stroke="{t["badge_fg"]}" stroke-width="12" stroke-miterlimit="10">'
            f'<path class="trace" pathLength="1" d="{BADGE_I}"/>'
            f'<path class="trace t2" pathLength="1" stroke-linejoin="bevel" d="{BADGE_S}"/></g></g>')


# ---------------------------------------------------------------------------- banner

NODES = [  # (x, y, label, label dx, label dy, label anchor)
    (728, 160, "FINANCE", -16, 4, "end"), (844, 124, "COMPLIANCE", 0, -18, "middle"),
    (1022, 134, "AUTOMATION", 16, 4, "start"), (1102, 240, "AI", 16, 4, "start"),
    (1042, 346, "SECURITY", 16, 4, "start"), (914, 364, "ERP", 0, 28, "middle"),
    (776, 340, "WEB", -16, 4, "end"), (698, 252, "SAAS", -16, 4, "end"),
]
HUB = (916, 248)
RING = [(i, (i + 1) % len(NODES)) for i in range(len(NODES))]
CHORDS = [(0, 2), (1, 3), (5, 7), (4, 6)]


def banner(f, t):
    h = 480
    disp, disp_m, body = f["display"], f["display_medium"], f["body"]
    o = []
    o.append(f'<defs><pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
             f'<circle cx="11" cy="11" r="1.1" fill="{t["ink"]}"/></pattern>'
             f'<radialGradient id="fade" cx="{HUB[0]}" cy="{HUB[1]}" r="300" gradientUnits="userSpaceOnUse">'
             f'<stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
             f'</radialGradient><mask id="m"><rect width="{W}" height="{h}" fill="url(#fade)"/></mask></defs>')
    o.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="22" fill="{t["bg"]}" stroke="{t["line"]}"/>')
    o.append(f'<rect width="{W}" height="{h}" fill="url(#dots)" opacity=".13" mask="url(#m)"/>')

    # editorial frame
    o.append(f'<g fill="{t["muted"]}">'
             f'<path d="{disp_m.path("§00 — INDEPENDENT SOFTWARE STUDIO", 64, 60, 13, 2.2)}"/>'
             f'<path d="{disp_m.path("BARCELONA · PARIS", W - 64, 60, 13, 2.2, "end")}"/>'
             f'<path d="{disp_m.path("REGULATED FINANCE · BUSINESS SOFTWARE · WEB & PERFORMANCE", 64, 438, 12, 2)}"/>'
             f'<path d="{disp_m.path("NODALSTUDIO.IO", W - 64, 438, 12, 2, "end")}"/></g>')
    o.append(f'<g stroke="{t["line"]}"><path d="M64 80H{W - 64}"/><path d="M64 410H{W - 64}"/></g>')

    # network: the studio as the node between disciplines
    edges = [(HUB, NODES[i][:2]) for i in range(len(NODES))]
    edges += [(NODES[a][:2], NODES[b][:2]) for a, b in RING + CHORDS]
    o.append(f'<g fill="none" stroke="{t["ink"]}" stroke-width="1" opacity=".22">')
    o += [f'<path d="M{a[0]} {a[1]}L{b[0]} {b[1]}"/>' for a, b in edges]
    o.append("</g>")
    o.append(f'<g fill="none" stroke="{t["ink"]}" stroke-width="2" stroke-linecap="round">')
    for i, (a, b) in enumerate(edges):
        a, b = (b, a) if i % 3 == 1 else (a, b)
        o.append(f'<path class="flow" pathLength="100" style="animation-delay:-{(i * 0.83) % 6:.2f}s" '
                 f'd="M{a[0]} {a[1]}L{b[0]} {b[1]}"/>')
    o.append("</g>")
    for i, (x, y, label, dx, dy, anchor) in enumerate(NODES):
        o.append(f'<circle class="ring" style="animation-delay:-{i * 0.7:.1f}s" cx="{x}" cy="{y}" r="11" '
                 f'fill="none" stroke="{t["ink"]}" stroke-width="1"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{t["ink"]}"/>')
        o.append(f'<path fill="{t["muted"]}" d="{disp_m.path(label, x + dx, y + dy, 11, 1.6, anchor)}"/>')
    o.append(f'<circle cx="{HUB[0]}" cy="{HUB[1]}" r="74" fill="{t["bg"]}"/>')
    o.append(f'<circle class="halo" cx="{HUB[0]}" cy="{HUB[1]}" r="74" fill="none" stroke="{t["ink"]}"/>')
    o.append(badge(HUB[0] - 52, HUB[1] - 52, 104, t))

    # wordmark + tagline
    o.append(f'<path class="rise" fill="{t["ink"]}" d="{disp.path("Nodal", 58, 214, 148, -2)}"/>')
    o.append(f'<path class="rise r2" fill="{t["ink"]}" d="{disp.path("Studio", 58, 336, 148, -2)}"/>')
    o.append(f'<path class="rise r3" fill="{t["ink"]}" d="{body.path("We design, build and integrate your software.", 64, 382, 25)}"/>')

    style = (
        ".rise{animation:rise 1s cubic-bezier(.2,.7,.2,1) both}.r2{animation-delay:.12s}.r3{animation-delay:.3s}"
        "@keyframes rise{from{opacity:0;transform:translateY(18px)}}"
        ".trace{stroke-dasharray:1;animation:draw 1.6s cubic-bezier(.65,0,.35,1) .35s both}.t2{animation-delay:.75s}"
        "@keyframes draw{from{stroke-dashoffset:1}}"
        ".flow{stroke-dasharray:5 95;stroke-dashoffset:100;animation:flow 6s linear infinite}"
        "@keyframes flow{to{stroke-dashoffset:0}}"
        ".ring{transform-box:fill-box;transform-origin:center;animation:ping 5.6s ease-out infinite}"
        "@keyframes ping{0%{opacity:.55;transform:scale(.5)}60%,100%{opacity:0;transform:scale(1.8)}}"
        ".halo{opacity:.25;transform-box:fill-box;transform-origin:center;animation:halo 4s ease-in-out infinite}"
        "@keyframes halo{50%{opacity:.08;transform:scale(1.07)}}"
        "@media (prefers-reduced-motion: reduce){.flow{display:none}}"
    )
    return svg(h, "".join(o), style, "Nodal Studio — We design, build and integrate your software.")


# ---------------------------------------------------------------------------- section headers

SECTIONS = [
    ("01", "OFFERS", "What we do."),
    ("02", "WORK", "Selected work."),
    ("03", "OPEN SOURCE", "Built in the open."),
    ("04", "JOURNAL", "From the blog."),
]


def section(f, t, n, kicker, title):
    h = 112
    o = [f'<path fill="{t["muted"]}" d="{f["display_medium"].path(f"§{n} — {kicker}", 0, 26, 14, 2.4)}"/>',
         f'<path class="rise" fill="{t["ink"]}" d="{f["display"].path(title, -2, 84, 52, -0.5)}"/>',
         f'<path stroke="{t["line"]}" d="M0 108.5H{W}"/>',
         f'<path class="grow" stroke="{t["ink"]}" stroke-width="2" d="M0 108H120"/>']
    style = (".rise{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}"
             "@keyframes rise{from{opacity:0;transform:translateY(12px)}}"
             ".grow{animation:grow 1.2s cubic-bezier(.65,0,.35,1) .2s both}"
             "@keyframes grow{from{transform:scaleX(0)}}")
    return svg(h, "".join(o), style, f"§{n} — {title}")


# ---------------------------------------------------------------------------- offers

OFFERS = [
    ("01", "Products & Platforms",
     "Tastefully designed, high-performance websites — reliable, smooth and precise.",
     ["SaaS", "Design", "Landing pages"]),
    ("02", "Missions & Integration",
     "ERP migrations, AI implementation, automation: we wire systems together.",
     ["ERP", "AI", "Automation"]),
    ("03", "Cybersecurity",
     "Safe systems, compliant business: we find the cracks before attackers do.",
     ["Compliance", "Data protection", "AI security"]),
]


def offers(f, t):
    h, gap = 330, 24
    cw = (W - 2 * gap) / 3
    disp, disp_m, body = f["display"], f["display_medium"], f["body"]
    o = []
    for i, (n, title, text, pills) in enumerate(OFFERS):
        x = i * (cw + gap)
        o.append(f'<g class="card" style="animation-delay:{i * 0.12:.2f}s">')
        o.append(f'<rect x="{num(x + .5)}" y=".5" width="{num(cw - 1)}" height="{h - 1}" rx="20" '
                 f'fill="{t["bg"]}" stroke="{t["line"]}"/>')
        o.append(f'<path fill="{t["ink"]}" d="{disp.path(n, x + 32, 70, 40, -1)}"/>')
        o.append(f'<path fill="{t["muted"]}" d="{disp_m.path("OFFER", x + cw - 32, 66, 12, 2, "end")}"/>')
        o.append(f'<path d="M{num(x + 32)} 98H{num(x + cw - 32)}" stroke="{t["line"]}"/>')
        o.append(f'<path fill="{t["ink"]}" d="{disp.path(title, x + 32, 146, 29, -0.3)}"/>')
        for j, line in enumerate(body.wrap(text, 17, cw - 64)):
            o.append(f'<path fill="{t["muted"]}" d="{body.path(line, x + 32, 186 + j * 26, 17)}"/>')
        px = x + 32
        for p in pills:
            pw = body.width(p, 13) + 24
            o.append(f'<rect x="{num(px)}" y="{h - 66}" width="{num(pw)}" height="34" rx="17" '
                     f'fill="none" stroke="{t["line"]}"/>')
            o.append(f'<path fill="{t["ink"]}" d="{body.path(p, px + 12, h - 44.5, 13)}"/>')
            px += pw + 6
        o.append("</g>")
    style = (".card{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}"
             "@keyframes rise{from{opacity:0;transform:translateY(14px)}}")
    label = " · ".join(f"{n} {title}: {text}" for n, title, text, _ in OFFERS)
    return svg(h, "".join(o), style, label)


# ---------------------------------------------------------------------------- call to action

def cta(f, t):
    h = 300
    inv = {**t, "bg": t["ink"], "ink": t["bg"], "badge_bg": t["badge_fg"], "badge_fg": t["badge_bg"],
           "muted": THEMES["dark" if t is THEMES["light"] else "light"]["muted"]}
    disp, disp_m, body = f["display"], f["display_medium"], f["body"]
    o = [f'<rect width="{W}" height="{h}" rx="22" fill="{inv["bg"]}"/>',
         f'<path fill="{inv["muted"]}" d="{disp_m.path("§05 — CONTACT", 64, 70, 13, 2.2)}"/>',
         f'<path class="rise" fill="{inv["ink"]}" d="{disp.path("Got a project?", 58, 168, 92, -1.5)}"/>',
         f'<path fill="{inv["ink"]}" d="{body.path("hello@nodalstudio.io", 64, 238, 27)}"/>',
         f'<path class="nudge" fill="none" stroke="{inv["ink"]}" stroke-width="2.4" stroke-linecap="round" '
         f'stroke-linejoin="round" d="M{num(64 + body.width("hello@nodalstudio.io", 27) + 20)} 229h30m-10-10 10 10-10 10"/>',
         f'<path fill="{inv["muted"]}" d="{disp_m.path("BARCELONA · PARIS · EN / FR / ES", W - 64, 238, 12, 2, "end")}"/>',
         badge(W - 64 - 124, 58, 124, inv)]
    style = (".rise{animation:rise 1s cubic-bezier(.2,.7,.2,1) both}"
             "@keyframes rise{from{opacity:0;transform:translateY(14px)}}"
             ".nudge{animation:nudge 2.4s ease-in-out infinite}@keyframes nudge{50%{transform:translateX(8px)}}"
             ".trace{stroke-dasharray:1;animation:draw 1.6s cubic-bezier(.65,0,.35,1) .3s both}.t2{animation-delay:.7s}"
             "@keyframes draw{from{stroke-dashoffset:1}}")
    return svg(h, "".join(o), style, "Got a project? Write to hello@nodalstudio.io")


# ---------------------------------------------------------------------------- portfolio frames

WORK = {  # screenshot → address shown in the window chrome
    "compliom": "compliom.com", "ubique": "github.com/NodalStudio/Ubique",
    "accounting-rag": "nodalstudio.io/fr/recherche/rag-droit-comptable",
    "here": "wemethere.events", "impulse": "communaute-impulse.com",
    "accca": "sorolls.org", "grumps": "grumps.app",
}


def frame(src, address, font_path, out):
    """Wrap a portfolio screenshot in a quiet browser window with rounded corners."""
    k = 2  # supersample, then downscale for smooth corners
    width, bar, radius = 1000, 44, 16
    shot = Image.open(src).convert("RGB")
    shot = shot.resize((width * k, round(shot.height * width / shot.width) * k), Image.LANCZOS)
    h = bar * k + shot.height
    canvas = Image.new("RGBA", (width * k, h), (0, 0, 0, 0))
    window = Image.new("RGBA", canvas.size, "#16171A")
    window.paste(shot, (0, bar * k))
    d = ImageDraw.Draw(window)
    for i, c in enumerate(("#3A3B3F", "#3A3B3F", "#3A3B3F")):
        cx, cy = (24 + i * 18) * k, bar * k // 2
        d.ellipse((cx - 5 * k, cy - 5 * k, cx + 5 * k, cy + 5 * k), fill=c)
    font = ImageFont.truetype(font_path, 13 * k)
    tw = d.textlength(address, font=font)
    pill_w = tw + 40 * k
    px = (width * k - pill_w) / 2
    d.rounded_rectangle((px, 10 * k, px + pill_w, (bar - 10) * k), radius=12 * k, fill="#232428")
    d.text((width * k / 2, bar * k / 2), address, font=font, fill="#B9B8AE", anchor="mm")
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, canvas.width - 1, canvas.height - 1), radius=radius * k, fill=255)
    canvas.paste(window, (0, 0), mask)
    canvas = canvas.resize((width, h // k), Image.LANCZOS)
    canvas.save(out, "WEBP", quality=88, method=6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True, type=Path)
    ap.add_argument("--work", type=Path)
    a = ap.parse_args()
    f = {"display": Face(a.fonts / "display.woff2"),
         "display_medium": Face(a.fonts / "display-medium.woff2"),
         "body": Face(a.fonts / "body.woff2"),
         "body_medium": Face(a.fonts / "body-medium.woff2")}
    for name, t in THEMES.items():
        (OUT / f"banner-{name}.svg").write_text(banner(f, t))
        (OUT / f"offers-{name}.svg").write_text(offers(f, t))
        (OUT / f"contact-{name}.svg").write_text(cta(f, t))
        for n, kicker, title in SECTIONS:
            (OUT / f"section-{n}-{name}.svg").write_text(section(f, t, n, kicker, title))
    if a.work:
        ttf = OUT / ".body-medium.ttf"  # Pillow needs a TrueType file; removed right after
        ttf.write_bytes(f["body_medium"].data)
        try:
            (OUT / "work").mkdir(exist_ok=True)
            for slug, address in WORK.items():
                frame(a.work / f"{slug}.webp", address, str(ttf), OUT / "work" / f"{slug}.webp")
        finally:
            ttf.unlink()
    print("assets written to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
