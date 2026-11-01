from django.contrib.gis import admin

from .models import Building


@admin.register(Building)
class BuildingAdmin(admin.GISModelAdmin):
    list_display = (
        "property_id", "street_address", "small_area", "construction_year",
        "floors_above_ground", "dwellings", "est_residents", "risk_class",
    )
    list_filter = ("risk_class", "small_area", "census_year")
    search_fields = ("street_address", "building_name", "property_id")
