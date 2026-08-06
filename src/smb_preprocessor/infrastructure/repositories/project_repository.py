from pathlib import Path

from ...domain.models.project import Project


class ProjectRepository:
    """Adaptador do formato JSON e da estrutura de diretórios existente."""

    def create(self, root: Path, name: str, engine_dir: str = "") -> Project:
        return Project.create(root, name, engine_dir)

    def load(self, path: Path) -> Project:
        return Project.load(path)

    def save(self, project: Project, path: Path) -> None:
        project.ensure_structure()
        project.ensure_grid_structure()
        project.save(path)
