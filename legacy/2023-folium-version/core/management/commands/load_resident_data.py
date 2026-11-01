                        ### load_resident_data ###
import csv
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import ResidentLocations


class Command(BaseCommand):
    help = 'Load data from EV Station file'

    def handle(self, *args, **kwargs):
        data_file = settings.BASE_DIR / 'data' / 'melb_organised_data.csv'
        keys = ('ID', 'Suburb', 'Address', 'Rooms', 'Postcode', 'Residents', 'Landsize', 'BuildingArea', 
                'YearBuilt', 'CouncilArea', 'Latitude', 'Longitude', 'Regionname')  # the CSV columns we will gather data from.
        
        records = []
        with open(data_file, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                records.append({k: row[k] for k in keys})

        # extract the latitude and longitude from the Point object
        for record in records:
            latitude = record['Latitude']
            longitude = record['Longitude']
            record['longitude'] = float(longitude)
            record['latitude'] = float(latitude)
            record['residentID'] = int(record['ID'])
            record['rooms'] = int(record['Rooms'])
            record['residents'] = float(record['Residents'])
            record['landsize'] = float(record['Landsize'])
            record['buildingArea'] = float(record['BuildingArea'])
            record['yearBuilt'] = float(record['YearBuilt'])

            # add the data to the database
            ResidentLocations.objects.get_or_create(
                postcode=record['Postcode'],
                latitude=record['latitude'],
                longitude=record['longitude'],
                residentID=record['residentID'],
                rooms=record['rooms'],
                suburb=record['Suburb'],
                address=record['Address'],
                residents=record['residents'],
                landsize=record['landsize'],
                buildingArea=record['buildingArea'],
                yearBuilt=record['yearBuilt'],
                councilArea=record['CouncilArea'],
                regionname=record['Regionname']
                )
            