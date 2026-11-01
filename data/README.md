# Data

`ris_buildings.csv` is the processed dataset the application loads. It is built
from two City of Melbourne open datasets collected through the
**Census of Land Use and Employment (CLUE)**, licensed **CC BY 4.0**:

| Dataset | What we use | Portal |
| --- | --- | --- |
| Building information | location, construction year, refurbished year, floors above ground, predominant space use, accessibility | [buildings-with-name-age-size-accessibility-and-bicycle-facilities](https://data.melbourne.vic.gov.au/explore/dataset/buildings-with-name-age-size-accessibility-and-bicycle-facilities/) |
| Residential dwellings | number and type of dwellings per building | [residential-dwellings](https://data.melbourne.vic.gov.au/explore/dataset/residential-dwellings/) |

## Rebuilding the processed file

1. Download both datasets as CSV and save them in `data/raw/` as
   * `buildings-with-name-age-size-accessibility-and-bicycle-facilities.csv`
   * `residential-dwellings.csv`

   Direct export links:
   * https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/buildings-with-name-age-size-accessibility-and-bicycle-facilities/exports/csv
   * https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/residential-dwellings/exports/csv

2. Run

   ```bash
   python manage.py prepare_clue            # newest census year in both files
   python manage.py prepare_clue --year 2021  # or a specific year
   python manage.py load_buildings
   ```

## Processing steps (`buildings/clue.py`)

* Both exports are read with delimiter sniffing (`;` or `,`) and header
  normalisation, so label-style and identifier-style headers both work.
* Only one census year is kept (default: newest year present in both files).
* Buildings are deduplicated on `property_id`; rows without valid coordinates
  inside the City of Melbourne bounding box are dropped.
* Construction years of `0`, blank or outside 1800-2100 are treated as unknown.
* Dwelling counts are summed per `property_id` and joined to the building.
* `est_residents = dwellings × PERSONS_PER_DWELLING` (default 1.45 =
  149,601 usual residents / 103,029 private dwellings, ABS 2021 Census,
  Melbourne City SA3). Configurable through the `PERSONS_PER_DWELLING`
  environment variable.
* `risk_class` is derived from construction year (see `buildings/risk.py`).

Attribution: *Contains data from the City of Melbourne Open Data Portal,
licensed under CC BY 4.0.*
