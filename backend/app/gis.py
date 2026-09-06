"""GeoJSON validation and normalization boundary for future municipal GIS adapters."""
from typing import Any

def validate_geojson(obj: dict[str, Any]) -> dict[str, Any]:
    if obj.get('type') != 'FeatureCollection' or not isinstance(obj.get('features'), list):
        raise ValueError('Expected a GeoJSON FeatureCollection')
    for i, feature in enumerate(obj['features']):
        if feature.get('type') != 'Feature' or not isinstance(feature.get('geometry'), dict):
            raise ValueError(f'Feature {i} is invalid')
        geom=feature['geometry']
        if geom.get('type') not in {'Point','LineString','Polygon','MultiPoint','MultiLineString','MultiPolygon'}:
            raise ValueError(f'Feature {i} has unsupported geometry type')
        if 'coordinates' not in geom:
            raise ValueError(f'Feature {i} is missing coordinates')
    return obj
