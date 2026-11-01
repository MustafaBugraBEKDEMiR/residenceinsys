from django.db import models

# Create your models here.

class ResidentLocations(models.Model):
    residentID = models.IntegerField(primary_key=True)  # Use existing ID from CSV
    postcode = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    rooms = models.IntegerField()
    residents = models.FloatField()
    suburb = models.CharField(max_length=100)
    address = models.CharField(max_length=100)
    landsize = models.FloatField()
    buildingArea = models.FloatField()
    yearBuilt = models.FloatField()
    councilArea = models.CharField(max_length=100)
    regionname = models.CharField(max_length=100)

    def __str__(self):
        return str(self.postcode)