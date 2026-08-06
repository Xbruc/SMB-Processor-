from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


NS = {"kml": "http://www.opengis.net/kml/2.2"}


def polygon_feature(feature_collection: dict) -> dict:
    features = feature_collection.get("features", [])
    polygons = [
        feature for feature in features
        if feature.get("geometry", {}).get("type") == "Polygon"
    ]
    if not polygons:
        raise ValueError("Desenhe pelo menos um polígono no mapa.")
    return polygons[-1]


def save_polygon_kml(feature_collection: dict, path: Path, name: str):
    feature = polygon_feature(feature_collection)
    rings = feature["geometry"]["coordinates"]
    if not rings or len(rings[0]) < 3:
        raise ValueError("O polígono desenhado é inválido.")

    def coordinates(ring):
        closed = list(ring)
        if closed[0][:2] != closed[-1][:2]:
            closed.append(closed[0])
        return " ".join(f"{p[0]:.10f},{p[1]:.10f},0" for p in closed)

    inner = "".join(
        "<innerBoundaryIs><LinearRing><coordinates>"
        + coordinates(ring)
        + "</coordinates></LinearRing></innerBoundaryIs>"
        for ring in rings[1:]
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>'
        f"<name>{name}</name><Polygon><outerBoundaryIs><LinearRing><coordinates>"
        f"{coordinates(rings[0])}</coordinates></LinearRing></outerBoundaryIs>"
        f"{inner}</Polygon></Placemark></Document></kml>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_kml_as_geojson(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"O contorno não é um arquivo KML/KMZ válido: {path}")
    if path.suffix.lower() not in {".kml", ".kmz"}:
        raise ValueError("O arquivo de contorno deve ter extensão .kml ou .kmz.")
    if path.suffix.lower() == ".kmz":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".kml")]
            if not names:
                raise ValueError("O KMZ não contém um arquivo KML.")
            root = ET.fromstring(archive.read(names[0]))
    else:
        root = ET.parse(path).getroot()
    element = root.find(".//kml:coordinates", NS)
    if element is None or not element.text:
        raise ValueError("O arquivo não contém um polígono KML.")
    ring = []
    for token in element.text.split():
        values = token.split(",")
        ring.append([float(values[0]), float(values[1])])
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"source": path.name},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }],
    }


def dumps_geojson(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
