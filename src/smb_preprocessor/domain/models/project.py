from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass
class Project:
    """Estado persistente de um projeto de modelagem costeira."""

    project_name: str = ""
    data_dir: str = ""
    engine_dir: str = ""
    contour: str = ""
    gebco: str = ""
    grid_output: str = "Grade/grade_500m"
    mesh_size: float = 500.0
    refinement_region: str = ""
    refinement_size: float = 100.0
    transition: float = 2000.0
    tide_file: str = ""
    flow_file: str = ""
    start: str = "2022-03-01"
    end: str = "2022-03-31"
    sea_boundary: int = 2
    river1_boundary: int = 1
    river2_boundary: int = 3
    sea_boundaries: str = "2"
    river_boundaries: str = "1, 3"
    boundary_filename: str = "fronteiras_mare_vazao.prn"
    series_output: str = "Fronteiras/grade_500m"
    cas_file: str = "Configurações/grade_500m/modelo_telemac2d.cas"
    result_file: str = ""
    result_crs: str = "EPSG:32723"

    FOLDERS = (
        "Matriz", "Grade", "Contornos", "Fronteiras",
        "Configurações", "Resultados",
    )

    @classmethod
    def create(cls, root: Path, name: str, engine_dir: str = "") -> "Project":
        root.mkdir(parents=True, exist_ok=False)
        for folder in cls.FOLDERS:
            (root / folder).mkdir()
        project = cls(
            project_name=name,
            data_dir=str(root.resolve()),
            engine_dir=engine_dir,
            grid_output="Grade/grade_500m",
            series_output="Fronteiras/grade_500m",
        )
        project.ensure_grid_structure()
        project.save(root / "projeto_cebsm.json")
        return project

    @classmethod
    def load(cls, path: Path) -> "Project":
        data = json.loads(path.read_text(encoding="utf-8"))
        if "sea_boundaries" not in data:
            data["sea_boundaries"] = str(data.get("sea_boundary", 2))
        if "river_boundaries" not in data:
            rivers = [data.get("river1_boundary"), data.get("river2_boundary")]
            data["river_boundaries"] = ", ".join(
                str(value) for value in rivers if value is not None
            )
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def root(self) -> Path:
        return Path(self.data_dir)

    def ensure_structure(self):
        if not self.data_dir:
            raise ValueError("Nenhum projeto foi criado ou carregado.")
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in self.FOLDERS:
            (self.root / folder).mkdir(exist_ok=True)

    def resolve_input(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        candidates = [self.root / "Matriz" / path, self.root / path]
        if self.engine_dir:
            candidates.append(Path(self.engine_dir) / path)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def resolve_output(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    @property
    def grid_id(self) -> str:
        name = Path(self.grid_output).name.strip()
        return name if name and name.lower() != "grade" else "grade_500m"

    @property
    def contours_dir(self) -> Path:
        return self.root / "Contornos" / self.grid_id

    @property
    def boundaries_dir(self) -> Path:
        return self.root / "Fronteiras" / self.grid_id

    @property
    def configuration_dir(self) -> Path:
        return self.root / "Configurações" / self.grid_id

    @property
    def results_dir(self) -> Path:
        return self.root / "Resultados" / self.grid_id

    def ensure_grid_structure(self):
        self.resolve_output(self.grid_output).mkdir(parents=True, exist_ok=True)
        self.contours_dir.mkdir(parents=True, exist_ok=True)
        self.boundaries_dir.mkdir(parents=True, exist_ok=True)
        self.configuration_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, value: str) -> Path:
        """Compatibilidade com projetos e integrações anteriores."""
        return self.resolve_input(value)
