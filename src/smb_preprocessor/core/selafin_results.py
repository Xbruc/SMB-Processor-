"""Read classic SELAFIN results and create lightweight map products.

The reader intentionally has no TELEMAC Python dependency.  It supports the
classic big/little-endian, single/double precision SELAFIN layout and reads
result variables on demand so long simulations do not need to fit in memory.
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import struct

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
from pyproj import Transformer


def _decode(value: bytes) -> str:
    return value.decode("latin-1", errors="replace").strip(" \x00")


class SelafinFile:
    """Indexed reader for a classic TELEMAC SELAFIN result file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._stream = self.path.open("rb")
        self.endian = self._detect_endian()
        self._read_header()
        self._index_steps()

    def close(self):
        self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _detect_endian(self) -> str:
        marker = self._stream.read(4)
        if len(marker) != 4:
            raise ValueError("Arquivo SELAFIN vazio ou incompleto.")
        self._stream.seek(0)
        for endian in (">", "<"):
            size = struct.unpack(endian + "i", marker)[0]
            if 0 < size < 10_000_000:
                return endian
        raise ValueError("Não foi possível identificar a ordem binária do SELAFIN.")

    def _record(self) -> bytes:
        marker = self._stream.read(4)
        if not marker:
            raise EOFError
        if len(marker) != 4:
            raise ValueError("Registro SELAFIN truncado.")
        size = struct.unpack(self.endian + "i", marker)[0]
        data = self._stream.read(size)
        closing = self._stream.read(4)
        if len(data) != size or len(closing) != 4:
            raise ValueError("Registro SELAFIN incompleto.")
        if struct.unpack(self.endian + "i", closing)[0] != size:
            raise ValueError("Marcadores de registro SELAFIN inconsistentes.")
        return data

    def _read_header(self):
        self.title = _decode(self._record())
        counts = np.frombuffer(self._record(), dtype=self.endian + "i4")
        if len(counts) < 2:
            raise ValueError("Cabeçalho SELAFIN sem contagem de variáveis.")
        self.nvar = int(counts[0] + counts[1])
        self.variables = []
        self.units = []
        for _ in range(self.nvar):
            raw = self._record()
            self.variables.append(_decode(raw[:16]))
            self.units.append(_decode(raw[16:32]))
        self.iparam = np.frombuffer(
            self._record(), dtype=self.endian + "i4"
        ).astype(int)
        self.date = None
        if len(self.iparam) >= 10 and self.iparam[9] == 1:
            self.date = np.frombuffer(
                self._record(), dtype=self.endian + "i4"
            ).astype(int).tolist()

        mesh = np.frombuffer(self._record(), dtype=self.endian + "i4")
        if len(mesh) < 4:
            raise ValueError("Cabeçalho SELAFIN sem dimensões da malha.")
        self.nelem, self.npoin, self.ndp, self.nplan = map(int, mesh[:4])
        self.triangles = np.frombuffer(
            self._record(), dtype=self.endian + "i4"
        ).astype(np.int64).reshape(self.nelem, self.ndp)[:, :3] - 1
        self.ipobo = np.frombuffer(
            self._record(), dtype=self.endian + "i4"
        ).astype(np.int64)
        raw_x = self._record()
        self.float_size = len(raw_x) // self.npoin
        if self.float_size not in (4, 8):
            raise ValueError("Precisão numérica SELAFIN não suportada.")
        self.float_dtype = self.endian + ("f4" if self.float_size == 4 else "f8")
        self.x = np.frombuffer(raw_x, dtype=self.float_dtype).astype(float)
        self.y = np.frombuffer(self._record(), dtype=self.float_dtype).astype(float)
        self.data_start = self._stream.tell()

    def _index_steps(self):
        self.times: list[float] = []
        self.offsets: list[list[int]] = []
        self._stream.seek(self.data_start)
        while True:
            try:
                raw_time = self._record()
            except EOFError:
                break
            if len(raw_time) not in (4, 8):
                raise ValueError("Registro de tempo SELAFIN inválido.")
            dtype = self.endian + ("f4" if len(raw_time) == 4 else "f8")
            self.times.append(float(np.frombuffer(raw_time, dtype=dtype)[0]))
            step_offsets = []
            for _ in range(self.nvar):
                marker = self._stream.read(4)
                if len(marker) != 4:
                    raise ValueError("Passo de tempo SELAFIN truncado.")
                size = struct.unpack(self.endian + "i", marker)[0]
                step_offsets.append(self._stream.tell())
                self._stream.seek(size, 1)
                closing = self._stream.read(4)
                if len(closing) != 4 or struct.unpack(
                    self.endian + "i", closing
                )[0] != size:
                    raise ValueError("Variável SELAFIN com registro inconsistente.")
            self.offsets.append(step_offsets)

    def values(self, step: int, variable: int) -> np.ndarray:
        self._stream.seek(self.offsets[step][variable])
        raw = self._stream.read(self.npoin * self.float_size)
        if len(raw) != self.npoin * self.float_size:
            raise ValueError("Valores SELAFIN truncados.")
        return np.frombuffer(raw, dtype=self.float_dtype).astype(float)

    def variable_index(self, terms: tuple[str, ...]) -> int | None:
        normalized = [name.upper().replace("_", " ") for name in self.variables]
        for term in terms:
            term = term.upper()
            for index, name in enumerate(normalized):
                if term in name:
                    return index
        return None

    def summary(self) -> dict:
        return {
            "title": self.title,
            "variables": [
                {"index": i, "name": name, "unit": self.units[i]}
                for i, name in enumerate(self.variables)
            ],
            "steps": len(self.times),
            "times": self.times,
            "nodes": self.npoin,
            "elements": self.nelem,
        }


U_NAMES = ("VELOCITY U", "VITESSE U", "VELOCIDADE U", "U VELOCITY")
V_NAMES = ("VELOCITY V", "VITESSE V", "VELOCIDADE V", "V VELOCITY")
LEVEL_NAMES = (
    "FREE SURFACE", "SURFACE LIBRE", "NIVEL LIVRE", "NÍVEL LIVRE",
    "WATER LEVEL", "COTE Z",
)
DEPTH_NAMES = ("WATER DEPTH", "HAUTEUR D'EAU", "PROFUNDIDADE", "DEPTH")


def _coordinates(reader: SelafinFile, crs: str):
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(reader.x, reader.y)
    return np.asarray(lon), np.asarray(lat)


def generate_velocity_animation(
    source: Path, output: Path, crs: str = "EPSG:32723", max_frames: int = 0,
    u_variable: int | None = None, v_variable: int | None = None,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    with SelafinFile(source) as reader:
        u_index = u_variable if u_variable is not None else reader.variable_index(U_NAMES)
        v_index = v_variable if v_variable is not None else reader.variable_index(V_NAMES)
        if u_index is None or v_index is None:
            raise ValueError(
                "A simulação precisa conter as componentes VELOCITY U e VELOCITY V. "
                f"Variáveis encontradas: {', '.join(reader.variables)}"
            )
        if not reader.times:
            raise ValueError("A simulação não contém passos de tempo.")
        if max_frames and max_frames > 0 and len(reader.times) > max_frames:
            indices = np.unique(np.linspace(
                0, len(reader.times) - 1, max_frames, dtype=int
            ))
        else:
            # Preserve the exact temporal resolution written by TELEMAC.
            indices = np.arange(len(reader.times), dtype=int)
        lon, lat = _coordinates(reader, crs)
        to_mercator = Transformer.from_crs(crs, "EPSG:3857", always_xy=True)
        map_x, map_y = to_mercator.transform(reader.x, reader.y)
        map_x, map_y = np.asarray(map_x), np.asarray(map_y)
        triangulation = mtri.Triangulation(map_x, map_y, reader.triangles)
        depth_index = reader.variable_index(DEPTH_NAMES)
        # Keep glyph origins two element rings away from every physical mesh
        # boundary, so arrow heads cannot leak outside narrow channels.
        unsafe_vectors = reader.ipobo != 0
        for _ in range(2):
            touching = np.any(unsafe_vectors[reader.triangles], axis=1)
            expanded = unsafe_vectors.copy()
            expanded[reader.triangles[touching].ravel()] = True
            unsafe_vectors = expanded

        percentiles = []
        for step in indices:
            u = reader.values(int(step), u_index)
            v = reader.values(int(step), v_index)
            percentiles.append(float(np.nanpercentile(np.hypot(u, v), 98)))
        vmax = max(max(percentiles), 1e-9)

        # Old PNG sequences could consume several GB once decoded by Chromium.
        # They are generated artifacts and are superseded by the streamed video.
        for stale_frame in output.glob("corrente_*.png"):
            stale_frame.unlink(missing_ok=True)
        video_path = output / "animacao_correntes.webm"
        video_path.unlink(missing_ok=True)
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError(
                "Instale imageio-ffmpeg para gerar a animação com baixo uso de memória."
            ) from exc
        fps = 10
        map_width = max(float(np.ptp(map_x)), 1e-12)
        map_height = max(float(np.ptp(map_y)), 1e-12)
        # HTML video preserves its intrinsic aspect ratio. Match it to the
        # projected Leaflet bounds (multiples of 16 for efficient VP8) so the
        # mesh cannot be squashed or letterboxed inside the overlay element.
        longest_edge = 1440
        if map_width >= map_height:
            pixel_width = longest_edge
            pixel_height = max(16, round(longest_edge * map_height / map_width / 16) * 16)
        else:
            pixel_height = longest_edge
            pixel_width = max(16, round(longest_edge * map_width / map_height / 16) * 16)
        pixel_size = (pixel_width, pixel_height)
        writer = imageio_ffmpeg.write_frames(
            str(video_path), pixel_size, fps=fps, codec="libvpx",
            pix_fmt_in="rgba", pix_fmt_out="yuva420p",
            quality=None, bitrate="2M",
            output_params=[
                "-auto-alt-ref", "0", "-lag-in-frames", "0",
                "-threads", "2", "-deadline", "realtime", "-cpu-used", "8",
            ],
        )
        writer.send(None)
        try:
            for frame_number, step in enumerate(indices):
                u = reader.values(int(step), u_index)
                v = reader.values(int(step), v_index)
                speed = np.hypot(u, v)
                wet = np.isfinite(speed)
                if depth_index is not None:
                    depth = reader.values(int(step), depth_index)
                    wet &= np.isfinite(depth) & (depth > 0.05)
                    triangulation.set_mask(
                        np.any(~wet[reader.triangles], axis=1)
                    )
                fig = plt.figure(
                    figsize=(pixel_width / 120, pixel_height / 120),
                    dpi=120, frameon=False,
                )
                axis = fig.add_axes([0, 0, 1, 1])
                axis.tripcolor(
                    triangulation, speed, shading="gouraud", cmap="YlGnBu",
                    vmin=0, vmax=vmax, alpha=0.82,
                )
                # One interior wet node per geographic cell gives a stable,
                # homogeneous vector field regardless of node ordering.
                candidates = np.flatnonzero(
                    wet & ~unsafe_vectors & (speed > 1e-8)
                )
                width = map_width
                height = map_height
                columns = 20
                rows = min(30, max(10, round(columns * height / width)))
                cell_x = np.clip(((map_x[candidates] - np.min(map_x)) / width * columns).astype(int), 0, columns - 1)
                cell_y = np.clip(((map_y[candidates] - np.min(map_y)) / height * rows).astype(int), 0, rows - 1)
                cell_ids = cell_y * columns + cell_x
                _, first = np.unique(cell_ids, return_index=True)
                selected = candidates[first]
                magnitude = np.maximum(speed[selected], 1e-12)
                arrow_length = min(width / columns, height / rows) * 0.62
                arrow_u = u[selected] / magnitude * arrow_length
                arrow_v = v[selected] / magnitude * arrow_length
                axis.quiver(
                    map_x[selected], map_y[selected], arrow_u, arrow_v,
                    color="#071a27", alpha=0.50, angles="xy", scale_units="xy",
                    scale=1, width=0.0030, pivot="mid", headwidth=4.2,
                    headlength=4.8, headaxislength=4.2,
                )
                axis.quiver(
                    map_x[selected], map_y[selected], arrow_u, arrow_v,
                    color="#e9ffff", alpha=0.92, angles="xy", scale_units="xy",
                    scale=1, width=0.0015, pivot="mid", headwidth=4.2,
                    headlength=4.8, headaxislength=4.2,
                )
                axis.set_xlim(float(np.min(map_x)), float(np.max(map_x)))
                axis.set_ylim(float(np.min(map_y)), float(np.max(map_y)))
                axis.set_axis_off()
                canvas = FigureCanvasAgg(fig)
                canvas.draw()
                writer.send(np.asarray(canvas.buffer_rgba()))
                plt.close(fig)
                del canvas, fig, axis
                if frame_number % 5 == 0:
                    gc.collect()
                if frame_number % 10 == 0 or frame_number == len(indices) - 1:
                    print(
                        f"Quadro {frame_number + 1}/{len(indices)} · "
                        f"t={reader.times[int(step)] / 3600:.2f} h",
                        flush=True,
                    )
        finally:
            writer.close()
            gc.collect()

        metadata = {
            "type": "velocity",
            "source": str(source),
            "bounds": [
                [float(np.min(lat)), float(np.min(lon))],
                [float(np.max(lat)), float(np.max(lon))],
            ],
            "video": video_path.name,
            "fps": fps,
            "frame_count": len(indices),
            "pixel_size": list(pixel_size),
            "times": [float(reader.times[int(index)]) for index in indices],
            "min": 0.0,
            "max": vmax,
            "unit": reader.units[u_index] or "m/s",
        }
    path = output / "animacao_correntes.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def plot_level_variation(
    source: Path, output: Path, variable: int | None = None
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with SelafinFile(source) as reader:
        index = variable
        if index is None:
            index = reader.variable_index(LEVEL_NAMES)
        if index is None:
            raise ValueError(
                "Variável de nível não encontrada. Variáveis disponíveis: "
                + ", ".join(reader.variables)
            )
        depth_index = reader.variable_index(DEPTH_NAMES)
        lower, mean, upper = [], [], []
        for step in range(len(reader.times)):
            values = reader.values(step, index)
            valid = np.isfinite(values)
            if depth_index is not None:
                # FREE SURFACE equals BOTTOM at dry nodes in TELEMAC. Excluding
                # the numerical wet/dry fringe prevents land elevations from
                # being reported as water levels.
                depth = reader.values(step, depth_index)
                valid &= np.isfinite(depth) & (depth > 0.05)
            sample = values[valid]
            if not len(sample):
                sample = values[np.isfinite(values)]
            lower.append(float(np.nanpercentile(sample, 1)))
            mean.append(float(np.nanmean(sample)))
            upper.append(float(np.nanpercentile(sample, 99)))
        hours = np.asarray(reader.times) / 3600.0
        fig, axis = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
        axis.fill_between(hours, lower, upper, color="#56d6d0", alpha=0.18,
                          label="Faixa espacial P1–P99 (nós molhados)")
        axis.plot(hours, mean, color="#087f8c", linewidth=2, label="Média espacial")
        axis.plot(hours, lower, color="#3c78a8", linewidth=0.8, alpha=0.8)
        axis.plot(hours, upper, color="#3c78a8", linewidth=0.8, alpha=0.8)
        axis.set(title=f"Variação de nível — {reader.variables[index]}",
                 xlabel="Tempo de simulação (h)",
                 ylabel=reader.units[index] or "Nível")
        axis.grid(True, alpha=0.22)
        axis.legend(loc="upper right", fontsize=9)
        fig.savefig(output, dpi=180)
        plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    info = subparsers.add_parser("info")
    info.add_argument("source", type=Path)
    animation = subparsers.add_parser("velocity-animation")
    animation.add_argument("source", type=Path)
    animation.add_argument("output", type=Path)
    animation.add_argument("--crs", default="EPSG:32723")
    animation.add_argument(
        "--max-frames", type=int, default=0,
        help="limite opcional; 0 preserva todos os passos do SELAFIN",
    )
    animation.add_argument("--u-variable", type=int)
    animation.add_argument("--v-variable", type=int)
    level = subparsers.add_parser("level-plot")
    level.add_argument("source", type=Path)
    level.add_argument("output", type=Path)
    level.add_argument("--variable", type=int)
    args = parser.parse_args()
    if args.action == "info":
        with SelafinFile(args.source) as reader:
            print(json.dumps(reader.summary(), ensure_ascii=False))
    elif args.action == "velocity-animation":
        print(generate_velocity_animation(
            args.source, args.output, args.crs, args.max_frames,
            args.u_variable, args.v_variable,
        ))
    else:
        print(plot_level_variation(args.source, args.output, args.variable))


if __name__ == "__main__":
    main()
