from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/meta/", views.MetaView.as_view(), name="api-meta"),
    path("api/buildings/", views.BuildingListView.as_view(), name="api-buildings"),
    path("api/area-stats/", views.AreaStatsView.as_view(), name="api-area-stats"),
    path("api/export/", views.ExportView.as_view(), name="api-export"),
]
