"""Build the static GitHub Pages demo into _site/.

The demo is the same Leaflet client as the Django app, with
static/ris/static-backend.js answering the API calls in the browser from a
JSON file. No database or Django runtime is needed:

    python scripts/build_site.py            # writes _site/
    python -m http.server -d _site 8001     # preview
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from buildings import clue, risk  # noqa: E402

OUT = ROOT / "_site"
PERSONS_PER_DWELLING = float(os.environ.get("PERSONS_PER_DWELLING", 1.45))
COLUMNS = [
    "id", "building_name", "street_address", "small_area", "construction_year",
    "refurbished_year", "floors_above_ground", "space_use", "accessibility",
    "dwellings", "dwelling_type", "est_residents", "risk_class", "property_id",
    "lon", "lat",
]


def build() -> None:
    rows = clue.read_processed(ROOT / "data" / "ris_buildings.csv")
    items = []
    for i, r in enumerate(rows, start=1):
        r["id"] = i
        r["est_residents"] = round(r["dwellings"] * PERSONS_PER_DWELLING, 1)
        r["lon"], r["lat"] = r["longitude"], r["latitude"]
        items.append([r[c] for c in COLUMNS])

    years = [r["construction_year"] for r in rows if r["construction_year"]]
    floors = [r["floors_above_ground"] for r in rows if r["floors_above_ground"]]
    areas = Counter(r["small_area"] for r in rows)
    meta = {
        "buildings": len(rows),
        "census_year": max(r["census_year"] for r in rows),
        "construction_year_range": [min(years), max(years)],
        "floors_max": max(floors),
        "dwellings": sum(r["dwellings"] for r in rows),
        "est_residents": round(sum(r["est_residents"] for r in rows)),
        "persons_per_dwelling": PERSONS_PER_DWELLING,
        "small_areas": [{"name": n, "buildings": c} for n, c in sorted(areas.items())],
        "risk_classes": risk.legend(),
        "source": {
            "name": "City of Melbourne - Census of Land Use and Employment (CLUE)",
            "license": "CC BY 4.0",
            "url": "https://data.melbourne.vic.gov.au/",
        },
    }

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    shutil.copytree(ROOT / "static", OUT / "static")
    with (OUT / "data" / "ris.json").open("w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "columns": COLUMNS, "rows": items}, fh,
                  ensure_ascii=False, separators=(",", ":"))

    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    html = html.replace("{% load static %}", "")
    # cache-busting: GitHub Pages caches assets for 10 minutes
    version = hashlib.sha1(b"".join(
        f.read_bytes()
        for f in [*sorted((ROOT / "static" / "ris").glob("*")), ROOT / "data" / "ris_buildings.csv"]
    )).hexdigest()[:8]
    html = re.sub(r"\{% static '([^']+)' %\}", rf"static/\1?v={version}", html)
    html = html.replace(
        f'<script src="static/ris/app.js?v={version}"></script>',
        f'<script>window.RIS_DATA_URL = "data/ris.json?v={version}";</script>\n'
        f'<script src="static/ris/static-backend.js?v={version}"></script>\n'
        f'<script src="static/ris/app.js?v={version}"></script>',
    )
    html = html.replace(
        '<p class="summary" id="dataset-summary">',
        '<p class="demo-note">Static demo on GitHub Pages: all filtering and '
        'area statistics run in your browser.</p>\n      '
        '<p class="summary" id="dataset-summary">',
    )
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    size = (OUT / "data" / "ris.json").stat().st_size / 1e6
    print(f"Built {OUT} - {len(rows)} buildings, ris.json {size:.1f} MB")


if __name__ == "__main__":
    build()
