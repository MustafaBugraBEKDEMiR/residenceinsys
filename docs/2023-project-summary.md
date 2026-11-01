# 2023 project summary (GMT 458)

Short summary of the original term report, *Resident Information System*,
submitted on 9 June 2023 for **GMT 458 – Internet-Based Geographic Information
Systems**, Hacettepe University, Department of Geomatics Engineering.
Team 14: Mustafa Buğra Bekdemir, Alperen Mollaahmet. Supervisor: Prof. Dr.
Sultan Kocaman Gökçeoğlu.

## Aim

Give authorised responders information about the buildings in an area hit by
an earthquake, flood or fire: how many people live in each building, how big
and how old it is, and where exactly it is. With this, responders can estimate
how many people may be affected, judge the risk of a building and plan rescue
work faster.

## Problem and motivation

Disasters bring disinformation, limited access to qualified information and
missing data. As geomatics engineering students we wanted to address this
with a GIS application.

## Actors and scenarios

* **Rescue team member:** filters the affected suburb, selects a building and
  reads its construction year, rooms and residents to judge possible damage
  and plan the rescue, then shares the coordinates with other teams.
* **Disaster victim:** finds their building and sends its coordinates and
  likely number of occupants to aid teams.

## Data

The authoritative Turkish sources (KBS, UAVT address register, TKGM parcel
query) are not openly available. We therefore used the Kaggle *Melbourne
Housing Market* dataset (`melb_data.csv`) as the closest freely available
substitute. Its bedroom count was renamed to *Residents* (assumption: one
person per bedroom). Attributes: ID, rooms, residents, land size, building
area, year built, council area, region, suburb, address, postcode,
latitude, longitude.

## Method and tools

1. Read the CSV and keep only the needed columns (pandas).
2. Convert it to a data frame, then to SQLite, export as JSON and migrate to
   PostgreSQL for faster queries.
3. Visualise the buildings on a map with Folium (Leaflet.js).
4. Serve the web interface with Django.
5. Workflow: accept the suburb query → filter → show the filtered buildings →
   show the details of the clicked building in a popup.

## Project plan

Four months, eleven work packages: problem definition, literature review,
tool search, data collection, analysis and preprocessing, two coding phases,
application development, testing and finalisation. Weekly online meetings
(Google Meet, WhatsApp, Discord).

## Conclusion and future work (as written in 2023)

The application matched the initial idea and gave the team experience with
Python, pandas, Folium, SQLite and PostgreSQL. Future work: a mobile version,
user location sharing, and connection to real, up-to-date data sources.

**Follow-up:** the 2026 rebuild addresses the data and analysis points. See
the main [README](../README.md).
