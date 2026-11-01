from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from buildings import clue
from buildings.models import Building


class Command(BaseCommand):
    help = "Load the processed CLUE CSV (data/ris_buildings.csv) into the database."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(settings.CLUE_DATA_DIR / "ris_buildings.csv"))
        parser.add_argument("--if-empty", action="store_true",
                            help="Skip loading when the table already has rows")

    def handle(self, *args, **opts):
        if opts["if_empty"] and Building.objects.exists():
            self.stdout.write("Buildings table already populated - skipping.")
            return
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"Processed file not found: {path}. Run prepare_clue first.")
        rows = clue.read_processed(path)
        hh = settings.HOUSEHOLD_SIZE
        objs = []
        for r in rows:
            lat, lon = r.pop("latitude"), r.pop("longitude")
            r["est_residents"] = round(r["dwellings"] * hh, 1)
            objs.append(Building(location=Point(lon, lat, srid=4326), **r))
        with transaction.atomic():
            Building.objects.all().delete()
            Building.objects.bulk_create(objs, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(objs)} buildings (household size {hh})."
        ))
