"""Собирает static/ для GitHub Pages (корень репо + docs/)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
API_URL = "https://flt-eg0r6.amvera.io"
OUT_DIRS = [ROOT, ROOT / "docs"]


def build_html() -> str:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/style.css"', 'href="style.css"')
    html = html.replace('src="/static/app.js"', 'src="app.js"')
    if 'name="api-url"' not in html:
        html = html.replace(
            "<head>",
            f'<head>\n  <meta name="api-url" content="{API_URL}">',
            1,
        )
    return html


def main() -> None:
    html = build_html()
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    for out in OUT_DIRS:
        out.mkdir(exist_ok=True)
        (out / ".nojekyll").touch()
        (out / "index.html").write_text(html, encoding="utf-8")
        (out / "style.css").write_text(css, encoding="utf-8")
        (out / "app.js").write_text(js, encoding="utf-8")

    print(f"OK: GitHub Pages готов. API_URL={API_URL}")


if __name__ == "__main__":
    main()
