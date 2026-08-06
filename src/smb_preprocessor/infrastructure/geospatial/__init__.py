"""Adaptadores de dados geoespaciais."""

from .kml import dumps_geojson, load_kml_as_geojson, save_polygon_kml

__all__ = ["dumps_geojson", "load_kml_as_geojson", "save_polygon_kml"]
