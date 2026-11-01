from django.contrib.gis.db import models

from . import risk


class Building(models.Model):
    """One building from the City of Melbourne CLUE census.

    Building attributes come from the CLUE "Building information" dataset;
    ``dwellings`` is joined from the CLUE "Residential dwellings" dataset on
    (census_year, property_id). ``est_residents`` is derived as
    dwellings x persons per dwelling (see settings.PERSONS_PER_DWELLING).
    """

    census_year = models.PositiveSmallIntegerField(db_index=True)
    block_id = models.IntegerField(null=True, blank=True)
    property_id = models.IntegerField(db_index=True)
    base_property_id = models.IntegerField(null=True, blank=True)

    building_name = models.CharField(max_length=200, blank=True)
    street_address = models.CharField(max_length=200, blank=True)
    small_area = models.CharField("CLUE small area", max_length=100, db_index=True)

    construction_year = models.PositiveSmallIntegerField(null=True, blank=True)
    refurbished_year = models.PositiveSmallIntegerField(null=True, blank=True)
    floors_above_ground = models.PositiveSmallIntegerField(null=True, blank=True)
    space_use = models.CharField("predominant space use", max_length=100, blank=True)
    accessibility = models.CharField(max_length=200, blank=True)

    dwellings = models.PositiveIntegerField(default=0)
    dwelling_type = models.CharField(max_length=100, blank=True)
    est_residents = models.FloatField(default=0)

    risk_class = models.CharField(
        max_length=10, choices=risk.CHOICES, default=risk.UNKNOWN, db_index=True
    )
    location = models.PointField(srid=4326, geography=False)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["construction_year"])]

    def __str__(self) -> str:
        return self.building_name or self.street_address or f"Property {self.property_id}"

    @property
    def is_residential(self) -> bool:
        return self.dwellings > 0
