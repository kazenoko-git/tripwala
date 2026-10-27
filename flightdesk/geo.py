"""Offline airport coordinates and spherical route calculations."""
import json
import math
from pathlib import Path

with (Path(__file__).resolve().parent / 'assets' / 'airport-coordinates.json').open(encoding='utf-8') as stream:
    AIRPORT_COORDINATES = json.load(stream)


def great_circle_distance(start, end):
    lon1, lat1 = map(math.radians, start)
    lon2, lat2 = map(math.radians, end)
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 12742 * math.asin(math.sqrt(max(0.0, min(1.0, value))))


def great_circle_point(start, end, fraction):
    """Spherical interpolation, returning longitude and latitude in degrees."""
    lon1, lat1 = map(math.radians, start)
    lon2, lat2 = map(math.radians, end)
    a=(math.cos(lat1)*math.cos(lon1), math.cos(lat1)*math.sin(lon1), math.sin(lat1))
    b=(math.cos(lat2)*math.cos(lon2), math.cos(lat2)*math.sin(lon2), math.sin(lat2))
    dot=max(-1.0,min(1.0,sum(x*y for x,y in zip(a,b))))
    angle=math.acos(dot); fraction=max(0.0,min(1.0,fraction))
    if angle < 1e-10: return tuple(start)
    if abs(math.sin(angle)) < 1e-10:
        delta=(end[0]-start[0]+180)%360-180
        return ((start[0]+fraction*delta+180)%360-180, start[1]+fraction*(end[1]-start[1]))
    x=math.sin((1-fraction)*angle)/math.sin(angle); y=math.sin(fraction*angle)/math.sin(angle)
    vector=[x*v+y*w for v,w in zip(a,b)]
    return (math.degrees(math.atan2(vector[1],vector[0])), math.degrees(math.atan2(vector[2],math.hypot(vector[0],vector[1]))))
