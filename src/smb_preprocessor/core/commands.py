from __future__ import annotations

from pathlib import Path
import sys

from .project import Project


def _engine(project: Project, name: str) -> Path:
    base = Path(project.engine_dir or project.data_dir)
    path = base / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Motor não encontrado: {path}\n"
            "Selecione uma pasta de dados que contenha os scripts do SMB Processor."
        )
    return path


def _input(project: Project, value: str, label: str) -> Path:
    path = project.resolve_input(value)
    if not path.is_file():
        raise FileNotFoundError(
            f"{label} não encontrado: {path}\n"
            "Selecione novamente o arquivo pelo botão ‘…’."
        )
    return path


def grid_command(project: Project) -> tuple[str, list[str], Path]:
    args = [
        str(_engine(project, "criar_grade_telemac.py")),
        "--kml-estuario", str(_input(project, project.contour, "Contorno")),
        "--gebco", str(_input(project, project.gebco, "Arquivo GEBCO")),
        "--tamanho", str(project.mesh_size),
        "--saida", str(project.resolve_output(project.grid_output)),
    ]
    if project.refinement_region:
        args += [
            "--regiao-refino", str(
                _input(project, project.refinement_region, "Região de refinamento")
            ),
            "--tamanho-refino", str(project.refinement_size),
            "--transicao", str(project.transition),
        ]
    return sys.executable, args, project.root


def boundary_command(project: Project, action: str) -> tuple[str, list[str], Path]:
    args = [
        str(_engine(project, "definir_condicoes_contorno.py")),
        action,
        "--pasta-grade", str(project.resolve_output(project.grid_output)),
    ]
    return sys.executable, args, project.root


def series_command(project: Project) -> tuple[str, list[str], Path]:
    args = [
        str(_engine(project, "criar_series_fronteiras.py")),
        "--inicio", project.start,
        "--fim", project.end,
        "--mare", str(project.resolve_input(project.tide_file)),
        "--vazao", str(project.resolve_input(project.flow_file)),
        "--numeros-mare", project.sea_boundaries,
        "--numeros-vazao", project.river_boundaries,
        "--nome-arquivo", project.boundary_filename,
        "--saida", str(project.resolve_output(project.series_output)),
    ]
    return sys.executable, args, project.root


# Os nomes públicos permanecem neste módulo para compatibilidade, mas a
# implementação canônica é a camada CLI.
from ..cli.commands import (  # noqa: E402
    boundary_command as boundary_command,
    grid_command as grid_command,
    series_command as series_command,
)
