import csv
import json
import math

from django.conf import settings
from django.contrib.gis.geos import GEOSException, GEOSGeometry, Point
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import risk
from .models import Building

MAX_CIRCLE_RADIUS_M = 20_000


def index(request):
    return render(request, "index.html")


# --- helpers --------------------------------------------------------------

def _split(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _num(params, key, cast=int):
    raw = params.get(key)
    if raw in (None, ""):
        return None
    try:
        return cast(raw)
    except (TypeError, ValueError):
        raise ValidationError({key: f"'{raw}' is not a valid number"})


def apply_filters(qs, params):
    """Attribute filters shared by all endpoints (query string or JSON body)."""
    areas = _split(params.get("small_area"))
    if areas:
        qs = qs.filter(small_area__in=areas)
    classes = [c for c in _split(params.get("risk")) if c in risk.ORDER]
    if classes:
        qs = qs.filter(risk_class__in=classes)
    year_min, year_max = _num(params, "year_min"), _num(params, "year_max")
    if year_min is not None:
        qs = qs.filter(construction_year__gte=year_min)
    if year_max is not None:
        qs = qs.filter(construction_year__lte=year_max)
    floors_min = _num(params, "floors_min")
    if floors_min is not None:
        qs = qs.filter(floors_above_ground__gte=floors_min)
    if str(params.get("residential", "")).lower() in {"1", "true", "yes"}:
        qs = qs.filter(dwellings__gt=0)
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(street_address__icontains=q) | Q(building_name__icontains=q))
    return qs


def parse_area(geometry):
    """Return (lookup_kwargs, area_m2) for a GeoJSON geometry or circle."""
    if not geometry:
        return None, None
    if isinstance(geometry, str):
        try:
            geometry = json.loads(geometry)
        except json.JSONDecodeError:
            raise ValidationError({"geometry": "Invalid JSON"})
    if not isinstance(geometry, dict):
        raise ValidationError({"geometry": "Expected a GeoJSON object"})
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry") or {}
    if geometry.get("type") == "Circle":
        try:
            lon, lat = (float(v) for v in geometry["center"])
            radius = float(geometry["radius"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError({"geometry": "Circle needs center [lon, lat] and radius (m)"})
        if not 0 < radius <= MAX_CIRCLE_RADIUS_M:
            raise ValidationError({"geometry": f"radius must be in (0, {MAX_CIRCLE_RADIUS_M}] m"})
        # buffer in metres in GDA2020 / MGA zone 55, then back to WGS84
        circle = Point(lon, lat, srid=4326).transform(7855, clone=True).buffer(radius, quadsegs=32)
        circle.transform(4326)
        return {"location__within": circle}, math.pi * radius ** 2
    if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValidationError({"geometry": "Only Polygon, MultiPolygon or Circle are supported"})
    try:
        geom = GEOSGeometry(json.dumps(geometry), srid=4326)
    except (GEOSException, ValueError, TypeError):
        raise ValidationError({"geometry": "Could not parse geometry"})
    if not geom.valid:
        geom = geom.buffer(0)
    # area in m2 using GDA2020 / MGA zone 55 (covers Melbourne)
    area = geom.transform(7855, clone=True).area
    return {"location__within": geom}, area


# --- API ------------------------------------------------------------------

class MetaView(APIView):
    """Dataset metadata, filter options and the risk legend."""

    def get(self, request):
        qs = Building.objects.all()
        agg = qs.aggregate(
            n=Count("id"), year_min=Min("construction_year"), year_max=Max("construction_year"),
            floors_max=Max("floors_above_ground"), census_year=Max("census_year"),
            dwellings=Sum("dwellings"), residents=Sum("est_residents"),
        )
        areas = list(
            qs.values("small_area").annotate(n=Count("id")).order_by("small_area")
        )
        return Response({
            "buildings": agg["n"],
            "census_year": agg["census_year"],
            "construction_year_range": [agg["year_min"], agg["year_max"]],
            "floors_max": agg["floors_max"],
            "dwellings": agg["dwellings"] or 0,
            "est_residents": round(agg["residents"] or 0),
            "persons_per_dwelling": settings.PERSONS_PER_DWELLING,
            "small_areas": [{"name": a["small_area"], "buildings": a["n"]} for a in areas],
            "risk_classes": risk.legend(),
            "source": {
                "name": "City of Melbourne - Census of Land Use and Employment (CLUE)",
                "license": "CC BY 4.0",
                "url": "https://data.melbourne.vic.gov.au/",
            },
        })


FEATURE_FIELDS = (
    "id", "building_name", "street_address", "small_area", "construction_year",
    "refurbished_year", "floors_above_ground", "space_use", "accessibility",
    "dwellings", "dwelling_type", "est_residents", "risk_class", "property_id", "location",
)


class BuildingListView(APIView):
    """GeoJSON FeatureCollection of buildings matching the filters."""

    def get(self, request):
        qs = apply_filters(Building.objects.all(), request.query_params)
        bbox = _split(request.query_params.get("bbox"))
        if bbox:
            try:
                minx, miny, maxx, maxy = (float(v) for v in bbox)
            except ValueError:
                raise ValidationError({"bbox": "Expected minx,miny,maxx,maxy"})
            from django.contrib.gis.geos import Polygon
            qs = qs.filter(location__within=Polygon.from_bbox((minx, miny, maxx, maxy)))
        features = []
        for row in qs.values(*FEATURE_FIELDS):
            loc = row.pop("location")
            features.append({
                "type": "Feature",
                "id": row["id"],
                "geometry": {"type": "Point", "coordinates": [round(loc.x, 6), round(loc.y, 6)]},
                "properties": row,
            })
        return Response({"type": "FeatureCollection", "features": features})


def _area_queryset(data):
    lookup, area_m2 = parse_area(data.get("geometry"))
    qs = apply_filters(Building.objects.all(), data.get("filters") or {})
    if lookup:
        qs = qs.filter(**lookup)
    return qs, area_m2


class AreaStatsView(APIView):
    """Summary of buildings and estimated residents inside a drawn area.

    POST {"geometry": <GeoJSON Polygon | {"type":"Circle","center":[lon,lat],"radius":m}>,
          "filters": {...same keys as the list endpoint...}}
    """

    def post(self, request):
        qs, area_m2 = _area_queryset(request.data)
        totals = qs.aggregate(
            buildings=Count("id"),
            residential=Count("id", filter=Q(dwellings__gt=0)),
            dwellings=Sum("dwellings"),
            est_residents=Sum("est_residents"),
            floors_mean=Avg("floors_above_ground"),
            floors_max=Max("floors_above_ground"),
            year_min=Min("construction_year"),
        )
        by_class = {
            r["risk_class"]: r
            for r in qs.values("risk_class").annotate(
                buildings=Count("id"), dwellings=Sum("dwellings"), est_residents=Sum("est_residents")
            )
        }
        by_risk = []
        for item in risk.legend():
            r = by_class.get(item["key"], {})
            by_risk.append({
                **item,
                "buildings": r.get("buildings", 0),
                "dwellings": r.get("dwellings") or 0,
                "est_residents": round(r.get("est_residents") or 0),
            })
        by_area = list(
            qs.values("small_area").annotate(
                buildings=Count("id"), est_residents=Sum("est_residents")
            ).order_by("-est_residents")[:10]
        )
        for a in by_area:
            a["est_residents"] = round(a["est_residents"] or 0)
        priority = list(
            qs.filter(dwellings__gt=0, risk_class__in=[risk.HIGH, risk.ELEVATED])
            .order_by("-est_residents")
            .values("id", "street_address", "building_name", "construction_year",
                    "floors_above_ground", "dwellings", "est_residents", "risk_class")[:10]
        )
        return Response({
            "area_km2": round(area_m2 / 1e6, 4) if area_m2 else None,
            "buildings": totals["buildings"],
            "residential_buildings": totals["residential"],
            "dwellings": totals["dwellings"] or 0,
            "est_residents": round(totals["est_residents"] or 0),
            "floors_mean": round(totals["floors_mean"], 1) if totals["floors_mean"] else None,
            "floors_max": totals["floors_max"],
            "oldest_construction_year": totals["year_min"],
            "by_risk": by_risk,
            "by_small_area": by_area,
            "priority_buildings": priority,
            "ids": list(qs.values_list("id", flat=True)[:20000]),
            "persons_per_dwelling": settings.PERSONS_PER_DWELLING,
        })


EXPORT_FIELDS = [
    "property_id", "building_name", "street_address", "small_area", "construction_year",
    "refurbished_year", "floors_above_ground", "space_use", "dwellings", "dwelling_type",
    "est_residents", "risk_class", "latitude", "longitude",
]


class ExportView(APIView):
    """CSV export of the buildings inside an area (same body as area-stats)."""

    def post(self, request):
        qs, _ = _area_queryset(request.data)
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="ris_selection.csv"'
        w = csv.writer(resp)
        w.writerow(EXPORT_FIELDS)
        for b in qs.order_by("-est_residents"):
            w.writerow([
                b.property_id, b.building_name, b.street_address, b.small_area,
                b.construction_year or "", b.refurbished_year or "", b.floors_above_ground or "",
                b.space_use, b.dwellings, b.dwelling_type, b.est_residents, b.risk_class,
                round(b.location.y, 6), round(b.location.x, 6),
            ])
        return resp
