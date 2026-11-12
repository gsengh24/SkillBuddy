"""Build self-contained mockup files from src/.

    python3 docs/design/onboarding/src/build.py

Each src/screens/NN-name.html becomes ../NN-name.html with base.css and harness.js inlined.
Directives inside screen and partial files:
    <!--#include name k=v ...-->   insert src/partials/name.html; {{k}} -> v,
                                   {{k=v}} -> aria-current="page" when it matches, else nothing
    <!--#icon name-->              insert src/icons/name.svg (aria-hidden line icon)
"""

from __future__ import annotations

import html
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@700;800'
    '&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">'
)
INC = re.compile(r"<!--#include ([\w-]+?)((?: \w+=[\w.]*(?:-[\w.]+)*)*)\s*-->")
ICON = re.compile(r"<!--#icon ([\w-]+)-->")
META = re.compile(r"\A<!--meta\n(.*?)\n-->\n", re.S)


def icon(m: re.Match[str]) -> str:
    return (SRC / "icons" / f"{m.group(1)}.svg").read_text().strip()


def expand(text: str, depth: int = 0) -> str:
    if depth > 5:
        raise RuntimeError("include loop")

    def inc(m: re.Match[str]) -> str:
        body = (SRC / "partials" / f"{m.group(1)}.html").read_text()
        params = dict(p.split("=", 1) for p in m.group(2).split())
        for k, v in params.items():
            body = body.replace("{{" + k + "}}", v)
        body = re.sub(
            r"\{\{(\w+)=(\w+)\}\}",
            lambda q: 'aria-current="page"' if params.get(q.group(1)) == q.group(2) else "",
            body,
        )
        return expand(body, depth + 1)

    text = INC.sub(inc, text)
    return ICON.sub(icon, text)


def main() -> None:
    css = (SRC / "base.css").read_text()
    js = (SRC / "harness.js").read_text()
    screens = sorted((SRC / "screens").glob("*.html"))
    index = []
    for i, path in enumerate(screens):
        raw = path.read_text()
        m = META.match(raw)
        if not m:
            raise SystemExit(f"{path.name}: missing meta block")
        meta = dict(line.split(": ", 1) for line in m.group(1).splitlines())
        body = expand(raw[m.end():])
        prev = screens[i - 1].name if i else None
        nxt = screens[i + 1].name if i + 1 < len(screens) else None
        nav = ['<a class="mono" href="index.html">All screens</a>']
        if prev:
            nav.append(f'<a class="mono" href="{prev}">Previous</a>')
        if nxt:
            nav.append(f'<a class="mono" href="{nxt}">Next</a>')
        title, t2 = meta["title"], meta.get("title2", "")
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cynergi · {html.escape(meta["short"])}</title>
{FONTS}
<style>
{css}{meta.get("css", "")}
</style>
</head>
<body>
<header class="mk-head">
  <div>
    <p class="mono mk-kicker">{html.escape(meta["kicker"])}</p>
    <h1>{html.escape(title)} <span>{html.escape(t2)}</span></h1>
    <p>{html.escape(meta["desc"])}</p>
  </div>
  <nav class="mk-nav" aria-label="Mockups">{"".join(nav)}</nav>
</header>
<main>
{body}
</main>
<script>
{js}
</script>
</body>
</html>
"""
        (OUT / path.name).write_text(page)
        index.append((path.name, meta))
        print("built", path.name)

    items = "\n".join(
        f'<li><a href="{n}"><span class="mono">{html.escape(m["kicker"])}</span>'
        f'<b>{html.escape(m["short"])}</b><small>{html.escape(m["desc"])}</small></a></li>'
        for n, m in index
    )
    (OUT / "index.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cynergi onboarding mockups</title>
{FONTS}
<style>
{css}
.ix {{ max-width: 1160px; margin: 0 auto; padding: 0 32px 72px; }}
.ix ol {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }}
.ix a {{ display: grid; gap: 6px; height: 100%; padding: 20px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); text-decoration: none; transition: transform .2s var(--ease), border-color .2s; }}
.ix a:hover {{ border-color: var(--green-line); transform: translateY(-2px); }}
.ix .mono {{ color: var(--green); }}
.ix b {{ font: 600 16px/1.3 var(--f-b); }}
.ix small {{ color: var(--muted); font-size: 13px; }}
@media (max-width: 640px) {{ .ix {{ padding: 0 16px 48px; }} .ix ol {{ grid-template-columns: minmax(0, 1fr); }} }}
</style>
</head>
<body>
<header class="mk-head">
  <div>
    <p class="mono mk-kicker">Cynergi · onboarding redesign</p>
    <h1>Onboarding mockups. <span>Twelve screens, phone and desktop.</span></h1>
    <p>Built from ONBOARDING-DESIGN-BRIEF.md. Every screen file is self-contained and shows the
    390px and 1280px layouts. Copy marked “Draft copy” is privacy, consent or email wording for the owner to review.</p>
  </div>
</header>
<div class="ix"><ol>
{items}
</ol></div>
</body>
</html>
""")
    print("built index.html")


if __name__ == "__main__":
    main()
