#!/usr/bin/env python3
"""Generate the terminal-style SVG cards used by the profile README.

Standard library only. Reads live numbers from the GitHub GraphQL API and
writes assets/banner.svg, assets/neofetch.svg and assets/langs.svg.

Token lookup order: GH_TOKEN, GITHUB_TOKEN, then `gh auth token`.
"""
import datetime
import json
import os
import random
import subprocess
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

# ----------------------------------------------------------------- settings
LOGIN = os.environ.get("PROFILE_LOGIN", "ChiuKuanHsun")
HANDLE = "kuanhsun"                      # shown in the prompt: kuanhsun@github
DISPLAY_NAME = "KUAN HSUN"               # big text in the banner
TAGLINES = [                             # cycled in the banner
    "building things that scratch my own itch",
    "Chrome extensions / Android / automation",
    "reading manga, shipping side projects",
]
LOCATION = "Taiwan (UTC+8)"
HOST = "National Tsing Hua University"
SHELL = "TypeScript, Python, Kotlin, C++"
HOBBIES = "manga, anime, automating everything"
TOP_LANGS = 6
EXCLUDE_LANGS = set()                    # e.g. {"HTML", "CSS"} to hide them

# ------------------------------------------------------------------- theme
BG, BAR, BORDER = "#0d1117", "#161b22", "#30363d"
FG, DIM = "#c9d1d9", "#8b949e"
GREEN, BLUE, CYAN = "#39d353", "#58a6ff", "#56d4dd"
PALETTE = ["#f85149", "#d29922", "#39d353", "#56d4dd", "#58a6ff", "#bc8cff", "#c9d1d9", "#8b949e"]
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
W = 840
FS, CW, LH = 14, 8.4, 22                 # font size, char width, line height

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

QUERY = """
query($login:String!){ user(login:$login){
  createdAt
  contributionsCollection{ contributionCalendar{ totalContributions } }
  repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){
    totalCount
    nodes{
      stargazerCount
      languages(first:10, orderBy:{field:SIZE, direction:DESC}){
        edges{ size node{ name color } }
      }
    }
  }
}}"""


# -------------------------------------------------------------------- data
def token():
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token()}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        payload = json.load(res)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    user = payload["data"]["user"]

    sizes, colors = {}, {}
    stars = 0
    for repo in user["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in EXCLUDE_LANGS:
                continue
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or DIM
    total = sum(sizes.values()) or 1
    langs = sorted(sizes.items(), key=lambda kv: -kv[1])[:TOP_LANGS]

    created = datetime.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    months = (now.year - created.year) * 12 + now.month - created.month - (now.day < created.day)
    return {
        "repos": user["repositories"]["totalCount"],
        "stars": stars,
        "contributions": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "uptime": f"{months // 12} years, {months % 12} months",
        "langs": [(n, colors[n], s / total * 100) for n, s in langs],
    }


# ----------------------------------------------------------------- helpers
def text(x, y, s, fill=FG, extra=""):
    """Monospace text pinned to an exact width so every font lines up."""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" textLength="{len(s) * CW:.1f}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve"{extra}>{escape(s)}</text>'
    )


def fade(begin, dur=0.15):
    return f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="{dur}s" fill="freeze"/>'


def prompt(x, y):
    """`kuanhsun@github:~$ ` — returns (svg, x after the prompt)."""
    parts = [(f"{HANDLE}@github", GREEN), (":", FG), ("~", BLUE), ("$", FG)]
    out = []
    for s, color in parts:
        out.append(text(x, y, s, color))
        x += len(s) * CW
    return "".join(out), x + CW


def typed(x, y, cmd, uid, begin, dur):
    """A command revealed one character at a time, with a cursor that leaves."""
    widths = ";".join(f"{i * CW:.1f}" for i in range(len(cmd) + 1))
    xs = ";".join(f"{x + i * CW:.1f}" for i in range(len(cmd) + 1))
    return (
        f'<clipPath id="{uid}"><rect x="{x:.1f}" y="{y - FS:.1f}" width="0" height="{LH}">'
        f'<animate attributeName="width" values="{widths}" calcMode="discrete" '
        f'begin="{begin}s" dur="{dur}s" fill="freeze"/></rect></clipPath>'
        f'<g clip-path="url(#{uid})">{text(x, y, cmd)}</g>'
        f'<rect x="{x:.1f}" y="{y - FS + 2:.1f}" width="{CW}" height="{FS + 2}" fill="{FG}">'
        f'<animate attributeName="x" values="{xs}" calcMode="discrete" begin="{begin}s" dur="{dur}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0" begin="{begin + dur + 0.2:.2f}s"/></rect>'
    )


def cursor(x, y):
    return (
        f'<rect x="{x:.1f}" y="{y - FS + 2:.1f}" width="{CW}" height="{FS + 2}" fill="{FG}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></rect>'
    )


def window(height, title, body, defs=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img" aria-label="{escape(title)}">
<defs><clipPath id="frame"><rect width="{W}" height="{height}" rx="10"/></clipPath>{defs}</defs>
<g clip-path="url(#frame)" font-family="{FONT}" font-size="{FS}">
<rect width="{W}" height="{height}" fill="{BG}"/>
<rect width="{W}" height="36" fill="{BAR}"/>
<circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>
<text x="{W / 2}" y="23" fill="{DIM}" text-anchor="middle" font-size="13">{escape(title)}</text>
{body}
</g>
<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="10" fill="none" stroke="{BORDER}"/>
</svg>
"""


# ------------------------------------------------------------------- cards
ART = [  # "KH" as a pixel grid, drawn with rects so no font can break it
    "X...X.X...X",
    "X..X..X...X",
    "X.X...X...X",
    "XX....XXXXX",
    "X.X...X...X",
    "X..X..X...X",
    "X...X.X...X",
]
CELL = 16


def neofetch(d):
    info = [
        ("OS", LOCATION),
        ("Host", HOST),
        ("Uptime", f"{d['uptime']} on GitHub"),
        ("Shell", SHELL),
        ("Packages", f"{d['repos']} public repos"),
        ("Stars", f"{d['stars']} earned"),
        ("Commits", f"{d['contributions']} contributions in the last year"),
        ("Hobbies", HOBBIES),
    ]
    x0, y = 28, 36 + 30
    p, px = prompt(x0, y)
    body = [p, typed(px, y, "neofetch", "cmd", 0.6, 0.9)]

    top = y + LH + 10
    info_x = x0 + len(ART[0]) * CELL + 36
    t = 1.9

    art_top = top + (LH * (len(info) + 3) - len(ART) * CELL) / 2 - FS
    for r, line in enumerate(ART):
        cells = "".join(
            f'<rect x="{x0 + c * CELL}" y="{art_top + r * CELL:.1f}" width="{CELL - 3}" height="{CELL - 3}" rx="2" fill="{GREEN}"/>'
            for c, ch in enumerate(line)
            if ch == "X"
        )
        body.append(f'<g opacity="0">{fade(t + r * 0.07)}{cells}</g>')

    head = f"{HANDLE}@github"
    rows = [text(info_x, top, head, GREEN, ' font-weight="bold"'), text(info_x, top + LH, "-" * len(head), DIM)]
    key_w = max(len(k) for k, _ in info) + 2
    for i, (k, v) in enumerate(info):
        yy = top + LH * (i + 2)
        rows.append(text(info_x, yy, k, CYAN, ' font-weight="bold"') + text(info_x + key_w * CW, yy, v))
    yy = top + LH * (len(info) + 2) + 6
    swatches = "".join(
        f'<rect x="{info_x + i * 28:.1f}" y="{yy - 13:.1f}" width="28" height="16" fill="{c}"/>'
        for i, c in enumerate(PALETTE)
    )
    rows.append(swatches)
    for i, row in enumerate(rows):
        body.append(f'<g opacity="0">{fade(t + i * 0.09)}{row}</g>')

    end_y = yy + LH + 14
    p2, px2 = prompt(x0, end_y)
    body.append(f'<g opacity="0">{fade(t + len(rows) * 0.09 + 0.3)}{p2}{cursor(px2, end_y)}</g>')
    return window(end_y + 24, f"{HANDLE}@github: ~", "\n".join(body))


def langs(d):
    x0, y = 28, 36 + 30
    p, px = prompt(x0, y)
    cmd = f"langs --top {len(d['langs'])} --by bytes"
    body = [p, typed(px, y, cmd, "cmd", 0.6, 1.4)]

    name_w = max(len(n) for n, _, _ in d["langs"])
    bar_x = x0 + (name_w + 2) * CW
    bar_w = W - bar_x - 28 - 8 * CW
    peak = max(p for _, _, p in d["langs"])
    t = 2.4
    yy = y
    for i, (name, color, pct) in enumerate(d["langs"]):
        yy = y + LH + 12 + i * (LH + 6)
        w = max(bar_w * pct / peak, 2)
        begin = t + i * 0.12
        body.append(
            f'<g opacity="0">{fade(begin)}'
            f"{text(x0, yy, name)}"
            f'<rect x="{bar_x:.1f}" y="{yy - 11:.1f}" width="{bar_w:.1f}" height="12" rx="2" fill="{BAR}"/>'
            f'<rect x="{bar_x:.1f}" y="{yy - 11:.1f}" width="0" height="12" rx="2" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{begin:.2f}s" dur="0.8s" fill="freeze" '
            f'calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></rect>'
            f"{text(bar_x + bar_w + 2 * CW, yy, f'{pct:5.1f}%', DIM)}</g>"
        )
    end_y = yy + LH + 18
    p2, px2 = prompt(x0, end_y)
    body.append(f'<g opacity="0">{fade(t + len(d["langs"]) * 0.12 + 0.6)}{p2}{cursor(px2, end_y)}</g>')
    return window(end_y + 24, f"{HANDLE}@github: ~/languages", "\n".join(body))


def banner():
    h = 200
    rng = random.Random(7)                # fixed seed: identical output every run
    rain = []
    for i in range(48):
        x = 10 + i * 17.3
        chars = "".join(rng.choice("01アイウエオカキクケコ<>/{}=+*") for _ in range(16))
        spans = "".join(f'<tspan x="{x:.1f}" dy="15">{escape(c)}</tspan>' for c in chars)
        dur, delay = rng.uniform(5, 11), rng.uniform(0, 8)
        rain.append(
            f'<text y="0" fill="{GREEN}" opacity="{rng.uniform(0.08, 0.26):.2f}" font-size="12">{spans}'
            f'<animateTransform attributeName="transform" type="translate" from="0 -260" to="0 {h + 20}" '
            f'dur="{dur:.1f}s" begin="-{delay:.1f}s" repeatCount="indefinite"/></text>'
        )

    # Tagline: each phrase is wiped in, held, wiped out, in turn.
    n, slot = len(TAGLINES), 4.5
    total = n * slot
    tx = 0
    lines = []
    for i, phrase in enumerate(TAGLINES):
        full = len(phrase) * CW * 16 / FS
        a, b, c, e = i * slot / total, (i * slot + 1.1) / total, (i * slot + 3.6) / total, (i * slot + 4.2) / total
        kt = f"0;{a:.4f};{b:.4f};{c:.4f};{e:.4f};1"
        vals = f"0;0;{full:.1f};{full:.1f};0;0"
        if i == 0:
            kt, vals = f"0;{b:.4f};{c:.4f};{e:.4f};1", f"0;{full:.1f};{full:.1f};0;0"
        lines.append(
            f'<clipPath id="tag{i}"><rect x="{tx}" y="-18" width="0" height="26">'
            f'<animate attributeName="width" values="{vals}" keyTimes="{kt}" dur="{total}s" repeatCount="indefinite"/>'
            f"</rect></clipPath>"
            f'<text x="{tx}" y="0" fill="{FG}" font-size="16" clip-path="url(#tag{i})" '
            f'textLength="{full:.1f}" lengthAdjust="spacingAndGlyphs">{escape(phrase)}</text>'
        )
    longest = max(len(p) for p in TAGLINES) * CW * 16 / FS
    tag_x = (W - longest) / 2

    title = (
        f'<text x="{W / 2}" y="96" text-anchor="middle" font-size="58" font-weight="bold" '
        f'letter-spacing="10"'
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(DISPLAY_NAME)}">
<defs>
<clipPath id="frame"><rect width="{W}" height="{h}" rx="10"/></clipPath>
<linearGradient id="glow" x1="0" x2="2" y1="0" y2="0" spreadMethod="repeat">
<stop offset="0" stop-color="{GREEN}"/><stop offset="0.25" stop-color="{CYAN}"/><stop offset="0.5" stop-color="{GREEN}"/>
<animate attributeName="x1" values="0;-1" dur="6s" repeatCount="indefinite"/>
<animate attributeName="x2" values="2;1" dur="6s" repeatCount="indefinite"/>
</linearGradient>
<radialGradient id="vignette" cx="0.5" cy="0.5" r="0.75">
<stop offset="0.35" stop-color="{BG}" stop-opacity="0.92"/><stop offset="1" stop-color="{BG}" stop-opacity="0.25"/>
</radialGradient>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity="0.28"/></pattern>
</defs>
<g clip-path="url(#frame)" font-family="{FONT}">
<rect width="{W}" height="{h}" fill="{BG}"/>
{"".join(rain)}
<rect width="{W}" height="{h}" fill="url(#vignette)"/>
{title} fill="#f85149" opacity="0">{escape(DISPLAY_NAME)}<animate attributeName="opacity" values="0;0;0.8;0;0.6;0;0" keyTimes="0;0.90;0.91;0.93;0.95;0.97;1" dur="5s" repeatCount="indefinite"/><animateTransform attributeName="transform" type="translate" values="-4 0;-4 0;-6 1;-3 0;-4 0" keyTimes="0;0.9;0.93;0.96;1" dur="5s" repeatCount="indefinite"/></text>
{title} fill="{BLUE}" opacity="0">{escape(DISPLAY_NAME)}<animate attributeName="opacity" values="0;0;0.8;0;0.6;0;0" keyTimes="0;0.90;0.92;0.94;0.95;0.98;1" dur="5s" repeatCount="indefinite"/><animateTransform attributeName="transform" type="translate" values="4 0;4 0;6 -1;3 0;4 0" keyTimes="0;0.9;0.93;0.96;1" dur="5s" repeatCount="indefinite"/></text>
{title} fill="url(#glow)">{escape(DISPLAY_NAME)}</text>
<g transform="translate({tag_x:.1f} 142)">
<text x="-{2 * CW * 16 / FS:.1f}" y="0" fill="{GREEN}" font-size="16" font-weight="bold">&gt;</text>
{"".join(lines)}
</g>
<rect width="{W}" height="{h}" fill="url(#scan)"/>
</g>
<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="10" fill="none" stroke="{BORDER}"/>
</svg>
"""


def main():
    data = fetch()
    OUT.mkdir(exist_ok=True)
    cards = {"banner.svg": banner(), "neofetch.svg": neofetch(data), "langs.svg": langs(data)}
    for name, svg in cards.items():
        (OUT / name).write_text(svg, encoding="utf-8", newline="\n")
        print(f"wrote assets/{name}")
    print(json.dumps({k: v for k, v in data.items() if k != "langs"}))


if __name__ == "__main__":
    main()
