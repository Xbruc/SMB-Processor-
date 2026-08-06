from pathlib import Path

from ..domain.models.project import Project
from ..infrastructure.repositories import ProjectRepository


class ProjectService:
    """Criação, leitura e persistência de projetos, sem dependência de Qt."""

    def __init__(self, repository: ProjectRepository | None = None):
        self.repository = repository or ProjectRepository()

    def create(self, root: Path, name: str, engine_dir: str = "") -> Project:
        return self.repository.create(root, name, engine_dir)

    def load(self, path: Path) -> Project:
        return self.repository.load(path)

    def save(self, project: Project, path: Path) -> None:
        self.repository.save(project, path)
