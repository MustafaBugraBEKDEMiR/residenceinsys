from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from buildings import clue

DEFAULT_BUILDINGS = "buildings-with-name-age-size-accessibility-and-bicycle-facilities.csv"
DEFAULT_DWELLINGS = "residential-dwellings.csv"


class Command(BaseCommand):
    help = (
        "Join the raw CLUE 'Building information' and 'Residential dwellings' "
        "CSV exports into one processed CSV (data/ris_buildings.csv)."
    )

    def add_arguments(self, parser):
        d = settings.CLUE_DATA_DIR
        parser.add_argument("--buildings", default=str(d / "raw" / DEFAULT_BUILDINGS))
        parser.add_argument("--dwellings", default=str(d / "raw" / DEFAULT_DWELLINGS))
        parser.add_argument("--year", type=int, default=None,
                            help="Census year to use (default: newest in both files)")
        parser.add_argument("--out", default=str(d / "ris_buildings.csv"))

    def handle(self, *args, **opts):
        for key in ("buildings", "dwellings"):
            if not Path(opts[key]).exists():
                raise CommandError(f"{key} file not found: {opts[key]}")
        b_rows = clue.read_table(opts["buildings"])
        d_rows = clue.read_table(opts["dwellings"])
        self.stdout.write(f"Building census years: {clue.available_years(b_rows)}")
        self.stdout.write(f"Dwelling census years: {clue.available_years(d_rows)}")
        rows, report = clue.prepare(b_rows, d_rows, settings.PERSONS_PER_DWELLING, opts["year"])
        clue.write_processed(rows, opts["out"])
        for line in report.lines():
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} buildings -> {opts['out']}"))
