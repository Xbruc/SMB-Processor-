from pathlib import Path

from ..cli.commands import boundary_command, grid_command, series_command
from ..domain.models.project import Project

ProcessSpec = tuple[str, list[str], Path]


class WorkflowService:
    """Prepara processos científicos sem conhecer a interface Qt."""

    def grid(self, project: Project) -> ProcessSpec:
        return grid_command(project)

    def boundary(self, project: Project, action: str) -> ProcessSpec:
        return boundary_command(project, action)

    def series(self, project: Project) -> ProcessSpec:
        return series_command(project)
