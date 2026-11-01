from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from rest_framework.test import APIClient

from buildings import clue

FIX = Path(__file__).parent / "fixtures"

# polygon around the three CBD test buildings, excluding Carlton
CBD = {
    "type": "Polygon",
    "coordinates": [[[144.960, -37.817], [144.968, -37.817], [144.968, -37.811],
                     [144.960, -37.811], [144.960, -37.817]]],
}


@pytest.fixture
def loaded(db, tmp_path):
    rows, _ = clue.prepare(
        clue.read_table(FIX / "buildings_sample.csv"),
        clue.read_table(FIX / "dwellings_sample.csv"),
        persons_per_dwelling=1.8,
    )
    path = tmp_path / "ris_buildings.csv"
    clue.write_processed(rows, path)
    call_command("load_buildings", file=str(path))


@pytest.fixture
def client():
    return APIClient()


def test_index_page(client, loaded):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Resident Information System" in r.content


def test_meta(client, loaded):
    data = client.get("/api/meta/").json()
    assert data["buildings"] == 5
    assert data["dwellings"] == 55
    assert {a["name"] for a in data["small_areas"]} == {"Melbourne (CBD)", "Carlton"}
    assert len(data["risk_classes"]) == 5


def test_buildings_geojson_and_filters(client, loaded):
    fc = client.get("/api/buildings/").json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 5
    assert client.get("/api/buildings/?small_area=Carlton").json()["features"].__len__() == 2
    assert len(client.get("/api/buildings/?risk=high").json()["features"]) == 1
    assert len(client.get("/api/buildings/?residential=1").json()["features"]) == 3
    assert len(client.get("/api/buildings/?year_min=1960&year_max=2000").json()["features"]) == 2
    assert len(client.get("/api/buildings/?floors_min=5").json()["features"]) == 2
    assert len(client.get("/api/buildings/?q=lygon").json()["features"]) == 2


def test_bad_number_is_400(client, loaded):
    assert client.get("/api/buildings/?year_min=abc").status_code == 400


def test_area_stats_polygon(client, loaded):
    data = client.post("/api/area-stats/", {"geometry": CBD}, format="json").json()
    assert data["buildings"] == 3
    assert data["dwellings"] == 54
    assert data["est_residents"] == round(54 * settings.PERSONS_PER_DWELLING)
    assert data["area_km2"] > 0
    high = next(r for r in data["by_risk"] if r["key"] == "high")
    assert high["buildings"] == 1
    assert data["priority_buildings"][0]["dwellings"] == 50


def test_area_stats_circle_and_filters(client, loaded):
    body = {"geometry": {"type": "Circle", "center": [144.9671, -37.8001], "radius": 100},
            "filters": {"residential": True}}
    data = client.post("/api/area-stats/", body, format="json").json()
    assert data["buildings"] == 1
    assert data["dwellings"] == 1


def test_area_stats_rejects_bad_geometry(client, loaded):
    r = client.post("/api/area-stats/", {"geometry": {"type": "Point", "coordinates": [0, 0]}},
                    format="json")
    assert r.status_code == 400


def test_export_csv(client, loaded):
    r = client.post("/api/export/", {"geometry": CBD}, format="json")
    assert r.status_code == 200
    lines = r.content.decode().strip().splitlines()
    assert lines[0].startswith("property_id")
    assert len(lines) == 4
