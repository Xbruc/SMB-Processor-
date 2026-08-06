"""Fachada de infraestrutura para operações KML/KMZ validadas."""

from ...core.geo import (
    dumps_geojson, load_kml_as_geojson, polygon_feature, save_polygon_kml,
)

__all__ = [
    "dumps_geojson", "load_kml_as_geojson", "polygon_feature", "save_polygon_kml",
]
