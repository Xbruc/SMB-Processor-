from pathlib import Path
import json
import struct

import numpy as np
import pytest

from smb_preprocessor.core.project import Project
from smb_preprocessor.core.geo import load_kml_as_geojson, save_polygon_kml
from smb_preprocessor.core.validation import summarize_cli, validate_prn
from smb_preprocessor.core.selafin_results import (
    SelafinFile, generate_velocity_animation, plot_level_variation,
)
from smb_preprocessor.core.netcdf_data import (
    NetCDFFile, generate_map_animation, generate_map_overlay,
)
from netCDF4 import Dataset


def test_project_roundtrip(tmp_path):
    path = tmp_path / "project.json"
    project = Project(data_dir="dados", mesh_size=500)
    project.save(path)
    loaded = Project.load(path)
    assert loaded.data_dir == "dados"
    assert loaded.mesh_size == 500


def test_project_creates_structure(tmp_path):
    root = tmp_path / "MeuProjeto"
    project = Project.create(root, "MeuProjeto", "motores")
    assert project.project_name == "MeuProjeto"
    assert (root / "projeto_cebsm.json").is_file()
    assert all((root / name).is_dir() for name in Project.FOLDERS)
    assert (root / "Configurações").is_dir()
    assert (root / "Grade" / "grade_500m").is_dir()
    assert (root / "Contornos" / "grade_500m").is_dir()
    assert (root / "Fronteiras" / "grade_500m").is_dir()
    assert (root / "Configurações" / "grade_500m").is_dir()

    project.grid_output = "Grade/grade_refinada"
    project.ensure_grid_structure()
    assert project.contours_dir == root / "Contornos" / "grade_refinada"
    assert project.boundaries_dir == root / "Fronteiras" / "grade_refinada"
    assert project.configuration_dir == root / "Configurações" / "grade_refinada"
    assert project.results_dir == root / "Resultados" / "grade_refinada"
    assert (root / "Resultados").is_dir()


def test_project_resolves_legacy_input_from_engine_directory(tmp_path):
    root = tmp_path / "project"
    matrix = root / "Matriz"
    engine = tmp_path / "engine"
    matrix.mkdir(parents=True)
    engine.mkdir()
    source = engine / "GEBCO.nc"
    source.write_bytes(b"netcdf")

    project = Project(data_dir=str(root), engine_dir=str(engine))
    assert project.resolve_input("GEBCO.nc") == source


def test_cli_summary(tmp_path):
    path = tmp_path / "test.cli"
    path.write_text(
        "5 4 4 0 0 0 0 2 0 0 0 1 1\n"
        "4 5 5 0 0 0 0 2 0 0 0 2 2\n"
        "2 2 2 0 0 0 0 2 0 0 0 3 3\n",
        encoding="ascii",
    )
    assert summarize_cli(path) == {
        "oceano_nivel": 1, "rio_vazao": 1, "parede": 1
    }


def test_prn_validation(tmp_path):
    path = tmp_path / "test.prn"
    path.write_text(
        "T Q(1) SL(2) Q(3)\n"
        "s m3/s m m3/s\n"
        "0 10 1 10\n"
        "300 11 2 11\n",
        encoding="ascii",
    )
    assert validate_prn(path) == []


def test_map_polygon_to_kml(tmp_path):
    data = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-44.5, -2.5], [-44.4, -2.5],
                    [-44.4, -2.6], [-44.5, -2.5],
                ]],
            },
        }],
    }
    path = tmp_path / "domain.kml"
    save_polygon_kml(data, path, "domain")
    loaded = load_kml_as_geojson(path)
    assert loaded["features"][0]["geometry"]["type"] == "Polygon"


def _write_record(stream, data):
    stream.write(struct.pack(">i", len(data)))
    stream.write(data)
    stream.write(struct.pack(">i", len(data)))


def test_selafin_results_reader_and_level_plot(tmp_path):
    path = tmp_path / "simulation.slf"
    variables = [
        ("VELOCITY U", "M/S"),
        ("VELOCITY V", "M/S"),
        ("FREE SURFACE", "M"),
    ]
    with path.open("wb") as stream:
        _write_record(stream, b"TEST RESULT".ljust(80))
        _write_record(stream, np.asarray([3, 0], dtype=">i4").tobytes())
        for name, unit in variables:
            _write_record(stream, name.encode().ljust(16) + unit.encode().ljust(16))
        _write_record(stream, np.zeros(10, dtype=">i4").tobytes())
        _write_record(stream, np.asarray([1, 3, 3, 1], dtype=">i4").tobytes())
        _write_record(stream, np.asarray([1, 2, 3], dtype=">i4").tobytes())
        _write_record(stream, np.asarray([1, 2, 3], dtype=">i4").tobytes())
        _write_record(stream, np.asarray([500000, 500100, 500000], dtype=">f4").tobytes())
        _write_record(stream, np.asarray([9600000, 9600000, 9600100], dtype=">f4").tobytes())
        for time, level in ((0.0, [0.0, 0.1, 0.2]), (60.0, [0.2, 0.3, 0.4])):
            _write_record(stream, np.asarray([time], dtype=">f4").tobytes())
            _write_record(stream, np.asarray([3.0, 4.0, 0.0], dtype=">f4").tobytes())
            _write_record(stream, np.asarray([4.0, 3.0, 0.0], dtype=">f4").tobytes())
            _write_record(stream, np.asarray(level, dtype=">f4").tobytes())

    with SelafinFile(path) as result:
        assert result.variables == ["VELOCITY U", "VELOCITY V", "FREE SURFACE"]
        assert result.times == [0.0, 60.0]
        assert result.values(1, 2)[1] == pytest.approx(0.3)
    plot = plot_level_variation(path, tmp_path / "level.png")
    assert plot.is_file()
    animation = generate_velocity_animation(
        path, tmp_path / "animation", max_frames=1
    )
    metadata = json.loads(animation.read_text(encoding="utf-8"))
    assert metadata["frame_count"] == 1
    assert metadata["video"] == "animacao_correntes.webm"
    assert (animation.parent / metadata["video"]).is_file()


def test_adaptive_netcdf_reader_and_plot(tmp_path):
    path = tmp_path / "atmosphere.nc"
    with Dataset(path, "w") as dataset:
        dataset.createDimension("forecast", 2)
        dataset.createDimension("south_north", 3)
        dataset.createDimension("west_east", 4)
        time = dataset.createVariable("forecast", "f8", ("forecast",))
        time.standard_name = "time"
        time.units = "hours since 2026-01-01 00:00:00"
        time[:] = [0, 6]
        lat = dataset.createVariable("XLAT", "f4", ("south_north", "west_east"))
        lon = dataset.createVariable("XLONG", "f4", ("south_north", "west_east"))
        lat.standard_name, lon.standard_name = "latitude", "longitude"
        lat.units, lon.units = "degrees_north", "degrees_east"
        lon_grid, lat_grid = np.meshgrid(np.linspace(-45, -44, 4), np.linspace(-3, -2, 3))
        lat[:], lon[:] = lat_grid, lon_grid
        temp = dataset.createVariable("T2", "f4", ("forecast", "south_north", "west_east"))
        temp.long_name = "Air temperature"
        temp.units = "K"
        temp.coordinates = "XLONG XLAT"
        temp[:] = np.arange(24).reshape(2, 3, 4)
        north = dataset.createVariable("V2", "f4", ("forecast", "south_north", "west_east"))
        north.long_name = "Northward velocity"
        north.units = "m/s"
        north.coordinates = "XLONG XLAT"
        north[:] = 1

    with NetCDFFile(path) as reader:
        summary = reader.summary()
        assert summary["coordinates"]["time"] == "forecast"
        assert summary["coordinates"]["x"] == "XLONG"
        variable = next(v for v in summary["variables"] if v["name"] == "T2")
        assert variable["spatial_dimensions"] == ["south_north", "west_east"]
        output = reader.plot("T2", tmp_path / "temperature.png", {"forecast": 1})
    assert output.is_file()
    overlay = generate_map_overlay(
        path, "T2", tmp_path / "temperature_overlay.png", {"forecast": 0},
        path, "V2", {"forecast": 1},
    )
    metadata = json.loads(overlay.read_text(encoding="utf-8"))
    assert metadata["label"] == "Velocidade resultante"
    assert metadata["bounds"] == [[-3.0, -45.0], [-2.0, -44.0]]
    assert (tmp_path / metadata["image"]).is_file()


def test_rectilinear_netcdf_axes_with_different_lengths(tmp_path):
    path = tmp_path / "temperature.nc"
    with Dataset(path, "w") as dataset:
        dataset.createDimension("time", 1)
        dataset.createDimension("lat", 3)
        dataset.createDimension("lon", 5)
        lat = dataset.createVariable("lat", "f4", ("lat",))
        lon = dataset.createVariable("lon", "f4", ("lon",))
        lat.units, lon.units = "degrees_north", "degrees_east"
        lat[:] = [-3, -2.5, -2]
        lon[:] = [-45, -44.75, -44.5, -44.25, -44]
        temp = dataset.createVariable("temperature", "f4", ("time", "lat", "lon"))
        temp.long_name = "Sea surface temperature"
        temp.units = "degC"
        temp[:] = np.arange(15).reshape(1, 3, 5)
    metadata_path = generate_map_overlay(
        path, "temperature", tmp_path / "regular.png", {"time": 0}
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["bounds"] == [[-3.0, -45.0], [-2.0, -44.0]]


def test_staggered_uv_grid_is_centered_automatically(tmp_path):
    path = tmp_path / "staggered.nc"
    with Dataset(path, "w") as dataset:
        dataset.createDimension("time", 2)
        time = dataset.createVariable("time", "f8", ("time",))
        time.units = "hours since 2026-01-01 00:00:00"
        time[:] = [0, 6]
        for name, size in (("yh", 3), ("yq", 4), ("xh", 4), ("xq", 5)):
            dataset.createDimension(name, size)
            coordinate = dataset.createVariable(name, "f4", (name,))
            if name.startswith("x"):
                coordinate.units = "degrees_east"
                coordinate[:] = np.linspace(-45, -44, size)
            else:
                coordinate.units = "degrees_north"
                coordinate[:] = np.linspace(-3, -2, size)
        u = dataset.createVariable("uo", "f4", ("time", "yh", "xq"))
        v = dataset.createVariable("vo", "f4", ("time", "yq", "xh"))
        u.standard_name = "eastward_sea_water_velocity"
        v.standard_name = "northward_sea_water_velocity"
        u.units = v.units = "m/s"
        u[:] = 3
        v[:] = 4
    metadata_path = generate_map_overlay(
        path, "uo", tmp_path / "speed.png", {}, path, "vo", {}
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["label"] == "Velocidade resultante"
    assert metadata["min"] == pytest.approx(5)
    animation = generate_map_animation(
        path, "uo", tmp_path / "animation_uv", {}, path, "vo", {}
    )
    animation_metadata = json.loads(animation.read_text(encoding="utf-8"))
    assert animation_metadata["frame_count"] == 2
    assert animation_metadata["times"] == [0.0, 21600.0]
