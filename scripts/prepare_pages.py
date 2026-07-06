"""Собирает static/ в docs/ для GitHub Pages."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
DOCS = ROOT / "docs"
API_URL = "https://YOUR-PROJECT.amvera.app"  # URL бэкенда на Amvera (GitHub → Settings → Variables → API_URL)
WEBAPP_URL = "https://eg0r112.github.io/FLT"


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").touch()

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/style.css"', 'href="style.css"')
    html = html.replace('src="/static/app.js"', 'src="app.js"')
    if 'name="api-url"' not in html:
        html = html.replace(
            "<head>",
            f'<head>\n  <meta name="api-url" content="{API_URL}">',
            1,
        )

    (DOCS / "index.html").write_text(html, encoding="utf-8")
    (DOCS / "style.css").write_text(
        (STATIC / "style.css").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (DOCS / "app.js").write_text(
        (STATIC / "app.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"OK: docs/ готов. API_URL={API_URL}")


if __name__ == "__main__":
    main()
