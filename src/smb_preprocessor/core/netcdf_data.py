"""Leitura e visualizacao adaptativa de arquivos NetCDF geocientificos."""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from netCDF4 import Dataset, num2date


ROLE_TERMS = {
    "x": ("longitude", "lon", "x", "nav_lon", "rlon", "projection_x_coordinate"),
    "y": ("latitude", "lat", "y", "nav_lat", "rlat", "projection_y_coordinate"),
    "time": ("time", "times", "date", "datetime", "forecast_time"),
    "z": ("depth", "lev", "level", "height", "altitude", "pressure", "sigma", "z"),
}


def _text(value) -> str:
    return str(value or "").strip().lower()


def _role(name, variable) -> str | None:
    fields = (_text(name), _text(getattr(variable, "standard_name", "")),
              _text(getattr(variable, "long_name", "")))
    axis = _text(getattr(variable, "axis", ""))
    if axis in {"x", "y", "z", "t"}:
        return "time" if axis == "t" else axis
    units = _text(getattr(variable, "units", ""))
    if "degrees_east" in units or "degree_east" in units:
        return "x"
    if "degrees_north" in units or "degree_north" in units:
        return "y"
    if " since " in units:
        return "time"
    tokens = set(re.split(r"[^a-z0-9]+", " ".join(fields)))
    for role, terms in ROLE_TERMS.items():
        if any(term in fields or term in tokens for term in terms):
            return role
    return None


class NetCDFFile:
    """Inspeciona um NetCDF sem pressupor convencoes de nomes de um modelo."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.dataset = Dataset(self.path, "r")

    def close(self):
        self.dataset.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def coordinate_roles(self) -> dict[str, str]:
        found = {}
        for name, variable in self.dataset.variables.items():
            role = _role(name, variable)
            if role and role not in found:
                found[role] = name
        return found

    def data_variables(self) -> list[dict]:
        roles = self.coordinate_roles()
        coordinates = set(roles.values())
        result = []
        for name, variable in self.dataset.variables.items():
            if name in coordinates or not variable.dimensions or variable.dtype.kind in "OSU":
                continue
            x, y = self._coordinates_for(variable)
            spatial_dimensions = []
            for coordinate in (x, y):
                if coordinate is not None:
                    spatial_dimensions.extend(coordinate.dimensions)
            result.append({
                "name": name,
                "label": getattr(variable, "long_name", name),
                "standard_name": getattr(variable, "standard_name", ""),
                "unit": getattr(variable, "units", ""),
                "dimensions": list(variable.dimensions),
                "shape": list(variable.shape),
                "spatial_dimensions": list(dict.fromkeys(spatial_dimensions)),
            })
        return result

    def dimension_values(self, dimension: str, limit: int = 500) -> list[dict]:
        size = len(self.dataset.dimensions[dimension])
        coordinate = self.dataset.variables.get(dimension)
        if coordinate is None or coordinate.ndim != 1 or coordinate.shape[0] != size:
            return [{"index": i, "label": str(i)} for i in range(min(size, limit))]
        values = coordinate[:min(size, limit)]
        labels = None
        units = _text(getattr(coordinate, "units", ""))
        if " since " in units:
            try:
                dates = num2date(values, coordinate.units,
                    calendar=getattr(coordinate, "calendar", "standard"),
                    only_use_cftime_datetimes=False)
                labels = [str(value) for value in dates]
            except Exception:
                pass
        if labels is None:
            labels = [f"{value:g}" if np.issubdtype(np.asarray(value).dtype, np.number)
                      else str(value) for value in values]
        return [{"index": i, "label": label} for i, label in enumerate(labels)]

    def summary(self) -> dict:
        return {
            "path": str(self.path),
            "dimensions": {name: len(dim) for name, dim in self.dataset.dimensions.items()},
            "coordinates": self.coordinate_roles(),
            "variables": self.data_variables(),
            "title": getattr(self.dataset, "title", self.path.name),
        }

    def _coordinates_for(self, variable):
        candidates = list(variable.dimensions)
        candidates += str(getattr(variable, "coordinates", "") or "").split()
        x = y = None
        for name in dict.fromkeys(candidates):
            coordinate = self.dataset.variables.get(name)
            if coordinate is None:
                continue
            role = _role(name, coordinate)
            if role == "x" and x is None:
                x = coordinate
            elif role == "y" and y is None:
                y = coordinate
        return x, y

    def plot(self, variable_name: str, output: Path | str,
             selections: dict[str, int] | None = None, cmap="viridis") -> Path:
        selections = selections or {}
        variable = self.dataset.variables[variable_name]
        index = []
        remaining = []
        for dimension in variable.dimensions:
            if dimension in selections:
                size = len(self.dataset.dimensions[dimension])
                index.append(max(0, min(int(selections[dimension]), size - 1)))
            else:
                index.append(slice(None))
                remaining.append(dimension)
        data = np.ma.masked_invalid(np.ma.asarray(variable[tuple(index)]).squeeze())
        while data.ndim > 2:
            data = data[0]
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig, axis = plt.subplots(figsize=(11, 7), constrained_layout=True)
        label = getattr(variable, "long_name", variable_name)
        unit = getattr(variable, "units", "")
        title = f"{label} ({unit})" if unit else label
        x, y = self._coordinates_for(variable)
        def coordinate_values(coordinate):
            coordinate_index = tuple(
                max(0, min(int(selections[dim]), len(self.dataset.dimensions[dim]) - 1))
                if dim in selections else slice(None)
                for dim in coordinate.dimensions
            )
            return np.asarray(coordinate[coordinate_index]).squeeze()
        plotted_map = False
        if data.ndim == 2:
            try:
                xv, yv = coordinate_values(x), coordinate_values(y)
                # Coordinates may contain dimensions that were sliced in data.
                if xv.ndim == 1 and yv.ndim == 1 and data.shape == (len(yv), len(xv)):
                    artist = axis.pcolormesh(xv, yv, data, shading="auto", cmap=cmap)
                elif xv.shape == data.shape and yv.shape == data.shape:
                    artist = axis.pcolormesh(xv, yv, data, shading="auto", cmap=cmap)
                else:
                    raise ValueError
                axis.set_xlabel(getattr(x, "long_name", x.name))
                axis.set_ylabel(getattr(y, "long_name", y.name))
                plotted_map = True
            except Exception:
                artist = axis.imshow(data, origin="lower", aspect="auto", cmap=cmap)
            fig.colorbar(artist, ax=axis, label=unit)
        elif data.ndim == 1:
            try:
                xv, yv = coordinate_values(x), coordinate_values(y)
                if xv.shape != data.shape or yv.shape != data.shape:
                    raise ValueError
                artist = axis.scatter(xv, yv, c=data, s=14, cmap=cmap)
                fig.colorbar(artist, ax=axis, label=unit)
                axis.set_xlabel(getattr(x, "long_name", x.name))
                axis.set_ylabel(getattr(y, "long_name", y.name))
            except Exception:
                coordinate = self.dataset.variables.get(remaining[-1]) if remaining else None
                values = np.asarray(coordinate[:]) if coordinate is not None and coordinate.ndim == 1 else np.arange(data.size)
                axis.plot(values, data, color="#087f8c", linewidth=1.6)
                axis.set_xlabel(getattr(coordinate, "long_name", remaining[-1] if remaining else "Índice"))
                axis.set_ylabel(unit or label)
                axis.grid(alpha=.25)
        else:
            axis.text(.5, .5, f"Valor: {data.item():g}", ha="center", va="center", fontsize=20)
            axis.set_axis_off()
        axis.set_title(title)
        if plotted_map and _role(x.name, x) == "x" and _role(y.name, y) == "y":
            axis.set_aspect("auto")
        fig.savefig(output, dpi=180)
        plt.close(fig)
        return output

    def field(self, variable_name: str, selections=None):
        """Return a sliced field and its best geographic coordinates."""
        selections = selections or {}
        variable = self.dataset.variables[variable_name]
        index = tuple(
            max(0, min(int(selections[dim]), len(self.dataset.dimensions[dim]) - 1))
            if dim in selections else slice(None)
            for dim in variable.dimensions
        )
        # float32 halves the working set used by matplotlib and is more than
        # sufficient for a screen raster. Preserve the mask without creating
        # repeated float64/RGBA copies for multi-million-cell model grids.
        data = np.ma.masked_invalid(
            np.ma.asarray(variable[index]).squeeze().astype(np.float32, copy=False)
        )
        while data.ndim > 2:
            data = data[0]
        x, y = self._coordinates_for(variable)
        if x is None or y is None:
            raise ValueError(
                f"Não foi possível identificar latitude/longitude de {variable_name}. "
                "Inclua atributos CF ou o atributo coordinates na variável."
            )
        def values(coordinate):
            idx = tuple(
                int(selections[dim]) if dim in selections else slice(None)
                for dim in coordinate.dimensions
            )
            return np.asarray(coordinate[idx]).squeeze()
        return data, values(x), values(y), variable


def generate_map_overlay(source: Path, variable_name: str, output: Path,
                         selections=None, source_v: Path | None = None,
                         variable_v: str | None = None, selections_v=None,
                         render_size: tuple[int, int] = (1100, 720)) -> Path:
    """Render a scalar or U/V magnitude as a transparent geographic overlay."""
    vector_u = vector_v = None
    with NetCDFFile(source) as first:
        data, lon, lat, variable = first.field(variable_name, selections)
        label = getattr(variable, "long_name", variable_name)
        unit = getattr(variable, "units", "")
        if variable_v:
            if Path(source_v or source) == Path(source) and variable_v == variable_name:
                raise ValueError(
                    "As componentes U e V não podem ser a mesma variável. "
                    "Selecione as componentes vetoriais corretas."
                )
            second_reader = first if source_v is None or Path(source_v) == Path(source) else NetCDFFile(source_v)
            try:
                v, lon_v, lat_v, v_variable = second_reader.field(variable_v, selections_v)
                if data.shape != v.shape:
                    original_shapes = (data.shape, v.shape)
                    if data.ndim != 2 or v.ndim != 2 or any(
                        abs(a - b) > 1 for a, b in zip(data.shape, v.shape)
                    ):
                        raise ValueError(
                            f"U e V possuem grades incompatíveis: {data.shape} e {v.shape}."
                        )
                    target = tuple(min(a, b) for a, b in zip(data.shape, v.shape))

                    def center_field(values, coordinates_x, coordinates_y, shape):
                        values = np.ma.asarray(values)
                        coordinates_x = np.asarray(coordinates_x)
                        coordinates_y = np.asarray(coordinates_y)
                        for axis in range(2):
                            if values.shape[axis] == target[axis] + 1:
                                left = [slice(None), slice(None)]
                                right = [slice(None), slice(None)]
                                left[axis] = slice(0, -1); right[axis] = slice(1, None)
                                values = (values[tuple(left)] + values[tuple(right)]) * np.float32(.5)
                                adjusted = []
                                for coordinate in (coordinates_x, coordinates_y):
                                    if coordinate.ndim == 2 and coordinate.shape[axis] == shape[axis]:
                                        adjusted.append((coordinate[tuple(left)] + coordinate[tuple(right)]) * .5)
                                    elif coordinate.ndim == 1 and coordinate.size == shape[axis]:
                                        adjusted.append((coordinate[:-1] + coordinate[1:]) * .5)
                                    else:
                                        adjusted.append(coordinate)
                                coordinates_x, coordinates_y = adjusted
                                shape = list(shape); shape[axis] -= 1; shape = tuple(shape)
                        return values, coordinates_x, coordinates_y

                    data, lon, lat = center_field(data, lon, lat, original_shapes[0])
                    v, lon_v, lat_v = center_field(v, lon_v, lat_v, original_shapes[1])
                if data.shape != v.shape:
                    raise ValueError(
                        f"Não foi possível centralizar as grades U e V: {data.shape} e {v.shape}."
                    )
                vector_u, vector_v = data, v
                data = np.ma.sqrt(
                    data.astype(np.float32, copy=False) ** 2
                    + v.astype(np.float32, copy=False) ** 2
                ).astype(np.float32, copy=False)
                label = "Velocidade resultante"
                unit = unit or getattr(v_variable, "units", "")
            finally:
                if second_reader is not first:
                    second_reader.close()
    lon = np.asarray(lon); lat = np.asarray(lat)
    # Em grades regulares, lon e lat são eixos 1-D independentes e normalmente
    # possuem comprimentos diferentes (nx != ny).
    if not np.any(np.isfinite(lon)) or not np.any(np.isfinite(lat)):
        raise ValueError("O arquivo não contém coordenadas geográficas válidas.")
    bounds = [[float(np.nanmin(lat)), float(np.nanmin(lon))],
              [float(np.nanmax(lat)), float(np.nanmax(lon))]]
    finite = np.asarray(data.compressed(), dtype=np.float32)
    if not finite.size:
        raise ValueError("A seleção não contém valores válidos para plotagem.")
    vmin, vmax = np.nanpercentile(finite, [1, 99])
    if vmin == vmax:
        vmax = vmin + 1e-12
    width, height = render_size
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100, frameon=False)
    axis = fig.add_axes([0, 0, 1, 1])
    if data.ndim == 2:
        if lon.ndim == lat.ndim == 1:
            # imshow avoids the per-cell polygon/color buffers allocated by
            # pcolormesh. Flip descending axes so geographic bounds stay true.
            raster = data
            if lat[0] > lat[-1]:
                raster = raster[::-1, :]
            if lon[0] > lon[-1]:
                raster = raster[:, ::-1]
            # More source cells than output pixels add no visible detail and
            # can exhaust RAM while matplotlib expands them to RGBA.
            row_step = max(1, int(np.ceil(raster.shape[0] / height)))
            col_step = max(1, int(np.ceil(raster.shape[1] / width)))
            raster = raster[::row_step, ::col_step]
            axis.imshow(
                raster, origin="lower", interpolation="bilinear", aspect="auto",
                extent=[bounds[0][1], bounds[1][1], bounds[0][0], bounds[1][0]],
                cmap="turbo", vmin=vmin, vmax=vmax,
            )
        else:
            row_step = max(1, int(np.ceil(data.shape[0] / height)))
            col_step = max(1, int(np.ceil(data.shape[1] / width)))
            axis.pcolormesh(
                lon[::row_step, ::col_step], lat[::row_step, ::col_step],
                data[::row_step, ::col_step], shading="auto", cmap="turbo",
                vmin=vmin, vmax=vmax, rasterized=True,
            )
    elif data.ndim == 1 and lon.shape == lat.shape == data.shape:
        axis.scatter(lon, lat, c=data, s=18, linewidths=0, cmap="turbo", vmin=vmin, vmax=vmax)
    else:
        plt.close(fig)
        raise ValueError("A variável selecionada não forma um campo geográfico 1D ou 2D.")
    if vector_u is not None and vector_u.ndim == 2:
        # A stable screen-density sampling keeps arrows legible independently
        # of the native model resolution.
        arrow_rows = max(1, int(np.ceil(vector_u.shape[0] / 24)))
        arrow_cols = max(1, int(np.ceil(vector_u.shape[1] / 32)))
        if lon.ndim == lat.ndim == 1:
            arrow_lon, arrow_lat = np.meshgrid(lon[::arrow_cols], lat[::arrow_rows])
        else:
            arrow_lon = lon[::arrow_rows, ::arrow_cols]
            arrow_lat = lat[::arrow_rows, ::arrow_cols]
        arrow_u = vector_u[::arrow_rows, ::arrow_cols]
        arrow_v = vector_v[::arrow_rows, ::arrow_cols]
        valid = np.isfinite(arrow_u) & np.isfinite(arrow_v)
        axis.quiver(
            arrow_lon[valid], arrow_lat[valid], arrow_u[valid], arrow_v[valid],
            color="white", edgecolor="#102431", linewidth=.35, alpha=.9,
            angles="uv", scale_units="inches", scale=None, width=.0024,
            headwidth=4.2, headlength=5,
        )
    axis.set_xlim(bounds[0][1], bounds[1][1]); axis.set_ylim(bounds[0][0], bounds[1][0])
    axis.set_axis_off(); axis.patch.set_alpha(0); fig.patch.set_alpha(0)
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, transparent=True, dpi=100, pad_inches=0)
    axis.clear()
    fig.clear()
    plt.close(fig)
    metadata = {"bounds": bounds, "min": float(vmin), "max": float(vmax),
                "unit": unit, "label": label, "image": output.name}
    metadata_path = output.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    del data, finite, fig, axis
    if vector_u is not None:
        del vector_u, vector_v
    gc.collect()
    return metadata_path


def _time_dimension(path: Path, variable_name: str):
    with NetCDFFile(path) as reader:
        variable = reader.dataset.variables[variable_name]
        for dimension in variable.dimensions:
            coordinate = reader.dataset.variables.get(dimension)
            if coordinate is not None and _role(dimension, coordinate) == "time":
                raw = np.asarray(coordinate[:])
                units = getattr(coordinate, "units", "")
                if " since " in _text(units):
                    dates = num2date(raw, units, calendar=getattr(coordinate, "calendar", "standard"))
                    origin = dates[0]
                    seconds = [float((date - origin).total_seconds()) for date in dates]
                    labels = [str(date) for date in dates]
                else:
                    raw = raw.astype(float)
                    seconds = (raw - raw[0]).tolist()
                    labels = [f"{value:g}" for value in raw]
                return dimension, seconds, labels
    raise ValueError(f"A variável {variable_name} não possui dimensão temporal identificável.")


def generate_map_animation(source: Path, variable_name: str, output: Path,
                           selections=None, source_v: Path | None = None,
                           variable_v: str | None = None, selections_v=None) -> Path:
    """Generate transparent map frames using every available NetCDF time."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    time_dim, times, labels = _time_dimension(source, variable_name)
    selections = dict(selections or {})
    selections_v = dict(selections_v or {})
    time_dim_v = None
    if variable_v:
        time_dim_v, times_v, _ = _time_dimension(Path(source_v or source), variable_v)
        if len(times_v) != len(times):
            raise ValueError(
                f"U e V possuem quantidades de tempos diferentes: {len(times)} e {len(times_v)}."
            )
    frames = []
    metadata = None
    for index in range(len(times)):
        selections[time_dim] = index
        if time_dim_v:
            selections_v[time_dim_v] = index
        frame = output / f"frame_{index:05d}.png"
        metadata_path = generate_map_overlay(
            source, variable_name, frame, selections,
            source_v, variable_v, selections_v, render_size=(640, 420),
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata_path.unlink(missing_ok=True)
        frames.append(frame.name)
        gc.collect()
        print(f"Quadro {index + 1}/{len(times)}", flush=True)
    metadata.update({"frames": frames, "times": times, "time_labels": labels,
                     "frame_count": len(frames), "type": "netcdf-animation"})
    path = output / "animacao_netcdf.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    info = commands.add_parser("info")
    info.add_argument("source", type=Path)
    plot = commands.add_parser("plot")
    plot.add_argument("source", type=Path)
    plot.add_argument("variable")
    plot.add_argument("output", type=Path)
    plot.add_argument("--selections", default="{}")
    overlay = commands.add_parser("overlay")
    overlay.add_argument("source", type=Path)
    overlay.add_argument("variable")
    overlay.add_argument("output", type=Path)
    overlay.add_argument("--selections", default="{}")
    overlay.add_argument("--source-v", type=Path)
    overlay.add_argument("--variable-v")
    overlay.add_argument("--selections-v", default="{}")
    animate = commands.add_parser("animate")
    animate.add_argument("source", type=Path)
    animate.add_argument("variable")
    animate.add_argument("output", type=Path)
    animate.add_argument("--selections", default="{}")
    animate.add_argument("--source-v", type=Path)
    animate.add_argument("--variable-v")
    animate.add_argument("--selections-v", default="{}")
    args = parser.parse_args()
    with NetCDFFile(args.source) as reader:
        if args.action == "info":
            print(json.dumps(reader.summary(), ensure_ascii=False))
        elif args.action == "plot":
            print(reader.plot(args.variable, args.output, json.loads(args.selections)))
        else:
            # generate_map_overlay opens both files itself; close this preliminary handle.
            pass
    if args.action == "overlay":
        print(generate_map_overlay(
            args.source, args.variable, args.output, json.loads(args.selections),
            args.source_v, args.variable_v, json.loads(args.selections_v),
        ))
    elif args.action == "animate":
        print(generate_map_animation(
            args.source, args.variable, args.output, json.loads(args.selections),
            args.source_v, args.variable_v, json.loads(args.selections_v),
        ))


if __name__ == "__main__":
    main()
