"""Indicative seismic vulnerability classes based on construction year.

This is a *screening* index meant to help responders prioritise, not an
engineering assessment. The bands follow the history of Australian
earthquake design codes:

* before 1945  – era dominated by unreinforced masonry (URM), the building
                 stock considered most vulnerable in Australia.
* 1945 – 1979  – no Australian earthquake standard existed before
                 AS 2121-1979.
* 1980 – 1994  – AS 2121-1979 era (limited to few zones; Melbourne mostly
                 outside them).
* 1995 onwards – AS 1170.4-1993, referenced by the Building Code of
                 Australia from 1 January 1995 (later AS 1170.4-2007).
"""
from __future__ import annotations

HIGH = "high"
ELEVATED = "elevated"
MODERATE = "moderate"
LOW = "low"
UNKNOWN = "unknown"

RISK_CLASSES = [
    (HIGH, "High", "Built before 1945 (likely unreinforced masonry)", "#c0392b"),
    (ELEVATED, "Elevated", "Built 1945-1979 (before first seismic code)", "#e67e22"),
    (MODERATE, "Moderate", "Built 1980-1994 (AS 2121-1979 era)", "#f1c40f"),
    (LOW, "Low", "Built 1995+ (AS 1170.4 seismic design)", "#27ae60"),
    (UNKNOWN, "Unknown", "Construction year not recorded", "#7f8c8d"),
]

CHOICES = [(key, label) for key, label, _, _ in RISK_CLASSES]
ORDER = [key for key, *_ in RISK_CLASSES]


def classify(construction_year: int | None) -> str:
    """Return the vulnerability class key for a construction year."""
    if construction_year is None or construction_year <= 0:
        return UNKNOWN
    if construction_year < 1945:
        return HIGH
    if construction_year < 1980:
        return ELEVATED
    if construction_year < 1995:
        return MODERATE
    return LOW


def legend() -> list[dict]:
    return [
        {"key": k, "label": label, "description": d, "color": c}
        for k, label, d, c in RISK_CLASSES
    ]
