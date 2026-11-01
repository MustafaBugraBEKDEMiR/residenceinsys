from pathlib import Path

from buildings import clue, risk

FIX = Path(__file__).parent / "fixtures"


def _prepare(year=None):
    b = clue.read_table(FIX / "buildings_sample.csv")
    d = clue.read_table(FIX / "dwellings_sample.csv")
    return clue.prepare(b, d, persons_per_dwelling=1.8, census_year=year)


def test_headers_are_normalised_from_labels():
    rows = clue.read_table(FIX / "buildings_sample.csv")
    assert {"census_year", "property_id", "small_area", "floors_above_ground",
            "space_use", "construction_year"} <= set(rows[0])


def test_prepare_picks_latest_year_and_joins_dwellings():
    rows, report = _prepare()
    assert report.census_year == 2023
    by_pid = {r["property_id"]: r for r in rows}
    assert set(by_pid) == {100, 101, 102, 103, 104}
    assert by_pid[101]["dwellings"] == 50
    assert by_pid[101]["dwelling_type"] == "Residential Apartment"
    assert by_pid[101]["est_residents"] == 90.0
    assert by_pid[102]["dwellings"] == 0


def test_cleaning_drops_duplicates_bad_coords_and_unknown_years():
    rows, report = _prepare()
    assert report.duplicates == 1
    assert report.dropped_no_coords == 1
    by_pid = {r["property_id"]: r for r in rows}
    assert by_pid[104]["construction_year"] is None
    assert by_pid[104]["risk_class"] == risk.UNKNOWN
    # coordinates parsed from the "location" column when lat/lon are blank
    assert by_pid[103]["latitude"] == -37.8


def test_unmatched_dwellings_are_reported():
    _, report = _prepare()
    assert report.dwellings_total == 57
    assert report.dwellings_matched == 55


def test_explicit_year():
    rows, _ = _prepare(2022)
    assert len(rows) == 1 and rows[0]["dwellings"] == 3


def test_processed_roundtrip(tmp_path):
    rows, _ = _prepare()
    out = tmp_path / "p.csv"
    clue.write_processed(rows, out)
    back = clue.read_processed(out)
    assert len(back) == len(rows)
    assert back[0]["property_id"] == rows[0]["property_id"]


def test_risk_bands():
    assert risk.classify(None) == risk.UNKNOWN
    assert risk.classify(1890) == risk.HIGH
    assert risk.classify(1944) == risk.HIGH
    assert risk.classify(1945) == risk.ELEVATED
    assert risk.classify(1979) == risk.ELEVATED
    assert risk.classify(1980) == risk.MODERATE
    assert risk.classify(1994) == risk.MODERATE
    assert risk.classify(1995) == risk.LOW
