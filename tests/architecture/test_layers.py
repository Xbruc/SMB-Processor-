from pathlib import Path

from smb_preprocessor.application import ProjectService, WorkflowService
from smb_preprocessor.core.project import Project as LegacyProject
from smb_preprocessor.domain.models.project import Project
from smb_preprocessor.ui.pages import MapPage, WelcomePage
from smb_preprocessor.ui.widgets import PathRow


def test_legacy_project_import_points_to_domain_model():
    assert LegacyProject is Project


def test_project_service_preserves_project_format(tmp_path):
    service = ProjectService()
    project = service.create(tmp_path / "project", "project")
    path = project.root / "projeto_cebsm.json"
    loaded = service.load(path)
    assert loaded.project_name == project.project_name
    assert loaded.grid_output == project.grid_output


def test_workflow_service_exposes_existing_process_contract():
    service = WorkflowService()
    assert callable(service.grid)
    assert callable(service.boundary)
    assert callable(service.series)


def test_ui_components_are_importable_from_dedicated_packages():
    assert WelcomePage.__module__.endswith("welcome_page")
    assert MapPage.__module__.endswith("map_page")
    assert PathRow.__module__.endswith("path_selector")
