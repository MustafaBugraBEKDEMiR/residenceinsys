                            ### views.py ###
from django.shortcuts import render
import folium
from folium.plugins import FastMarkerCluster
from core.models import ResidentLocations
from folium import plugins
from folium import TileLayer


# Create your views here.

def index(request):
    # Retrieve filter criteria from the request
    suburb_filter = request.GET.get('suburb_filter')
    # Add more filter criteria if needed

    # Apply filters to the query
    filtered_residents = ResidentLocations.objects.all()
    if suburb_filter:
        filtered_residents = filtered_residents.filter(suburb=suburb_filter)
    # Apply more filters if needed

    # Create a Folium map centred on Melbourne
    f = folium.Figure(width=1532, height=625)
    m = folium.Map(location=[-37.815018, 144.946014], zoom_start=10, control_scale = True).add_to(f)

    # Create a FastMarkerCluster instance
    marker_cluster = FastMarkerCluster([], overlay=True)

    # Iterate over filtered residents and add markers to the marker cluster
    for resident in filtered_residents:
        # Create a popup message with filtered resident information
        popup_message = f"ID:{resident.residentID}<br>Rooms:{resident.rooms}<br>Residents:{resident.residents}<br>Landsize:{resident.landsize}<br>BuildingArea:{resident.buildingArea}<br>YearBuilt:{resident.yearBuilt}<br>CouncilArea:{resident.councilArea}<br>RegionName:{resident.regionname}<br>Suburb:{resident.suburb}<br>Address:{resident.address}<br>Postcode:{resident.postcode}<br>Latitude:{resident.latitude}<br>Longitude:{resident.longitude}"

        # Create a marker with the resident's latitude, longitude, and popup message
        marker = folium.Marker([resident.latitude, resident.longitude], popup=popup_message)

        # Add the marker to the marker cluster
        marker_cluster.add_child(marker)

    # Add the marker cluster to the map
    m.add_child(marker_cluster)

    # Add OpenStreetMap basemap
    TileLayer('openstreetmap').add_to(m)

    # Add Satellite basemap
    TileLayer('Stamen Terrain',name='Stamen Terrain').add_to(m)

    
    TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}', attr='Esri World Terrain',name='ESRI Terrain (Not effective below 20km scale)').add_to(m)


    # Add layer control
    folium.LayerControl().add_to(m)

    context = {
        'map': m._repr_html_(),
        'suburb_filter': suburb_filter,
        # Add more filter criteria to pass to the template if needed
    }
    return render(request, 'index.html', context)