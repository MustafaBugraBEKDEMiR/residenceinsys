"""Read, join and clean City of Melbourne CLUE exports.

Two open datasets (CC BY 4.0) are combined:

* Building information  – one row per building per census year
  (location, construction year, floors, predominant space use ...)
* Residential dwellings – dwelling counts per building per census year

The Opendatasoft portal exports CSVs with ';' as delimiter and either field
identifiers (``construction_year``) or labels (``Construction year``) as
headers, so the reader sniffs the delimiter and normalises header names.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import risk

PROCESSED_FIELDS = [
    "census_year", "block_id", "property_id", "base_property_id",
    "building_name", "street_address", "small_area", "construction_year",
    "refurbished_year", "floors_above_ground", "space_use", "accessibility",
    "dwellings", "dwelling_type", "est_residents", "risk_class",
    "latitude", "longitude",
]

# normalised header -> canonical name
ALIASES = {
    "clue_small_area": "small_area",
    "small_area": "small_area",
    "number_of_floors_above_ground": "floors_above_ground",
    "floors_above_ground": "floors_above_ground",
    "predominant_space_use": "space_use",
    "accessibility_type": "accessibility",
    "dwelling_number": "dwelling_number",
    "number_of_dwellings": "dwelling_number",
    "building_address": "street_address",
    "street_address": "street_address",
    "base_property_id": "base_property_id",
    "property_id": "property_id",
    "block_id": "block_id",
}

# Rough bounding box of the City of Melbourne LGA; drops bad coordinates.
BBOX = (144.85, -37.88, 145.02, -37.74)  # minx, miny, maxx, maxy


def _norm(name: str) -> str:
    name = name.strip().lstrip("﻿").lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return ALIASES.get(name, name)


def read_table(path: Path | str) -> list[dict]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(fh, dialect)
        header = [_norm(h) for h in next(reader)]
        return [dict(zip(header, row)) for row in reader if any(row)]


def _int(value) -> int | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() in {"nan", "none", "null"}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _year(value) -> int | None:
    y = _int(value)
    # CLUE uses 0/blank for unknown; reject obviously wrong values.
    if y is None or y < 1800 or y > 2100:
        return None
    return y


def _coords(row: dict) -> tuple[float, float] | None:
    lat, lon = row.get("latitude"), row.get("longitude")
    if not lat or not lon:
        loc = row.get("location") or row.get("geo_point_2d") or ""
        parts = [p.strip() for p in loc.split(",")]
        if len(parts) == 2:
            lat, lon = parts
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    minx, miny, maxx, maxy = BBOX
    if not (minx <= lon_f <= maxx and miny <= lat_f <= maxy):
        return None
    return lat_f, lon_f


@dataclass
class PrepareReport:
    census_year: int
    building_rows: int = 0
    kept: int = 0
    dropped_no_coords: int = 0
    duplicates: int = 0
    dwelling_rows: int = 0
    dwelling_properties: int = 0
    dwelling_properties_matched: int = 0
    dwellings_total: int = 0
    dwellings_matched: int = 0
    risk_counts: Counter = field(default_factory=Counter)

    def lines(self) -> list[str]:
        match = (
            100 * self.dwellings_matched / self.dwellings_total
            if self.dwellings_total else 0
        )
        return [
            f"Census year:              {self.census_year}",
            f"Building rows (year):     {self.building_rows}",
            f"Kept buildings:           {self.kept}",
            f"  dropped (no coords):    {self.dropped_no_coords}",
            f"  dropped (duplicates):   {self.duplicates}",
            f"Dwelling rows (year):     {self.dwelling_rows}",
            f"Residential properties:   {self.dwelling_properties} "
            f"({self.dwelling_properties_matched} matched to a building)",
            f"Dwellings matched:        {self.dwellings_matched}/{self.dwellings_total} "
            f"({match:.1f}%)",
            "Risk classes:             "
            + ", ".join(f"{k}={self.risk_counts.get(k, 0)}" for k in risk.ORDER),
        ]


def available_years(rows: list[dict]) -> list[int]:
    return sorted({y for y in (_int(r.get("census_year")) for r in rows) if y})


def prepare(
    building_rows: list[dict],
    dwelling_rows: list[dict],
    household_size: float,
    census_year: int | None = None,
) -> tuple[list[dict], PrepareReport]:
    """Join both tables for one census year and derive resident estimates."""
    years = available_years(building_rows)
    if not years:
        raise ValueError("No census_year values found in building data")
    if census_year is None:
        # newest year that also has dwelling data
        dyears = set(available_years(dwelling_rows))
        common = [y for y in years if y in dyears]
        census_year = (common or years)[-1]
    report = PrepareReport(census_year=census_year)

    # aggregate dwellings per property
    dw_count: dict[int, int] = defaultdict(int)
    dw_types: dict[int, Counter] = defaultdict(Counter)
    for r in dwelling_rows:
        if _int(r.get("census_year")) != census_year:
            continue
        report.dwelling_rows += 1
        pid = _int(r.get("property_id"))
        n = _int(r.get("dwelling_number")) or 0
        if pid is None or n <= 0:
            continue
        dw_count[pid] += n
        dw_types[pid][(r.get("dwelling_type") or "").strip()] += n
    report.dwelling_properties = len(dw_count)
    report.dwellings_total = sum(dw_count.values())

    out: list[dict] = []
    seen: set[int] = set()
    for r in building_rows:
        if _int(r.get("census_year")) != census_year:
            continue
        report.building_rows += 1
        pid = _int(r.get("property_id"))
        if pid is None or pid in seen:
            report.duplicates += 1
            continue
        coords = _coords(r)
        if coords is None:
            report.dropped_no_coords += 1
            continue
        seen.add(pid)
        cyear = _year(r.get("construction_year"))
        dwellings = dw_count.get(pid, 0)
        if dwellings:
            report.dwelling_properties_matched += 1
            report.dwellings_matched += dwellings
        rclass = risk.classify(cyear)
        report.risk_counts[rclass] += 1
        out.append({
            "census_year": census_year,
            "block_id": _int(r.get("block_id")),
            "property_id": pid,
            "base_property_id": _int(r.get("base_property_id")),
            "building_name": (r.get("building_name") or "").strip(),
            "street_address": (r.get("street_address") or "").strip(),
            "small_area": (r.get("small_area") or "").strip() or "Unknown",
            "construction_year": cyear,
            "refurbished_year": _year(r.get("refurbished_year")),
            "floors_above_ground": _int(r.get("floors_above_ground")),
            "space_use": (r.get("space_use") or "").strip(),
            "accessibility": (r.get("accessibility") or "").strip(),
            "dwellings": dwellings,
            "dwelling_type": dw_types[pid].most_common(1)[0][0] if dwellings else "",
            "est_residents": round(dwellings * household_size, 1),
            "risk_class": rclass,
            "latitude": round(coords[0], 6),
            "longitude": round(coords[1], 6),
        })
    report.kept = len(out)
    return out, report


def write_processed(rows: list[dict], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PROCESSED_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in PROCESSED_FIELDS})


def read_processed(path: Path | str) -> list[dict]:
    rows = []
    for r in read_table(path):
        rows.append({
            "census_year": _int(r["census_year"]),
            "block_id": _int(r.get("block_id")),
            "property_id": _int(r["property_id"]),
            "base_property_id": _int(r.get("base_property_id")),
            "building_name": r.get("building_name", ""),
            "street_address": r.get("street_address", ""),
            "small_area": r.get("small_area", "") or "Unknown",
            "construction_year": _year(r.get("construction_year")),
            "refurbished_year": _year(r.get("refurbished_year")),
            "floors_above_ground": _int(r.get("floors_above_ground")),
            "space_use": r.get("space_use", ""),
            "accessibility": r.get("accessibility", ""),
            "dwellings": _int(r.get("dwellings")) or 0,
            "dwelling_type": r.get("dwelling_type", ""),
            "est_residents": float(r.get("est_residents") or 0),
            "risk_class": r.get("risk_class") or risk.classify(_year(r.get("construction_year"))),
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
        })
    return rows
