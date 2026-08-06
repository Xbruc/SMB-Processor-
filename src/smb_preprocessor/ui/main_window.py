from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import shutil
import sys

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QInputDialog, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QMenu, QScrollArea, QSizePolicy, QSplitter, QStackedLayout, QTabWidget, QToolBar, QToolButton,
    QVBoxLayout, QWidget,
)

from ..application import ProjectService, WorkflowService
from ..domain.models.project import Project
from ..domain.validation import summarize_cli, validate_prn
from ..infrastructure.files.netcdf import NetCDFFile
from ..infrastructure.files.selafin import SelafinFile, LEVEL_NAMES, U_NAMES, V_NAMES
from ..infrastructure.geospatial import load_kml_as_geojson, save_polygon_kml
from ..infrastructure.processes import ProcessRunner
from .pages import MapPage, WelcomePage
from .theme import APP_STYLESHEET
from .widgets import PathRow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SMB Processor — TELEMAC")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)
        self.project = Project()
        self.project_service = ProjectService()
        self.workflow_service = WorkflowService()
        self.project_path: Path | None = None
        self.process_runner = ProcessRunner(self)
        self.process = self.process_runner.process
        self.process_runner.output_received.connect(self.read_process)
        self.process_runner.finished.connect(self.process_finished)
        self.pending_callback = None
        self.process_output = ""

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.West)
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, 1)
        self.log = QPlainTextEdit()
        self.log.setObjectName("processLog")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setPlaceholderText("Saída dos processamentos…")
        splitter = QSplitter()
        splitter.setOrientation(Qt.Vertical)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.log)
        splitter.setSizes([650, 180])
        layout.removeWidget(self.tabs)
        layout.addWidget(splitter)

        self.build_project_tab()
        self.build_map_tab()
        self.build_grid_tab()
        self.build_boundary_tab()
        self.build_series_tab()
        self.build_configuration_tab()
        self.build_validation_tab()
        self.build_results_tab()
        self.build_netcdf_tab()
        self.setStyleSheet(APP_STYLESHEET)
        self.apply_defaults()
        self.set_modules_enabled(False)
        self.main_interface_created = False
        self.assets_stfm = (
            Path(__file__).resolve().parents[1] / "assets" / "stfm"
        )
        self.setup_stfm_toolbar()
        self.setup_stfm_welcome()

    def style_action_button(self, button: QPushButton, icon_name: str):
        """Apply the shared module-action style and a bundled vector icon."""
        button.setObjectName("mapActionButton")
        icon_path = (
            Path(__file__).resolve().parents[1]
            / "assets" / "icons" / icon_name
        )
        button.setIcon(QIcon(str(icon_path)))
        button.setIconSize(QSize(18, 18))
        return button

    def setup_stfm_toolbar(self):
        toolbar = QToolBar("Barra principal")
        toolbar.setObjectName("appHeader")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setFixedHeight(54)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        brand_mark = QLabel("▦  SMB Processor")
        brand_mark.setObjectName("brandMark")
        brand_mark.setMinimumWidth(150)
        toolbar.addWidget(brand_mark)
        toolbar.addSeparator()

        project_menu = QMenu(self)
        for label, callback in [
            ("Novo projeto", self.new_project),
            ("Abrir projeto", self.load_project),
            ("Salvar projeto", self.save_project),
            ("Fechar projeto", self.close_project),
        ]:
            action = QAction(label, self)
            action.triggered.connect(callback)
            project_menu.addAction(action)
        project_menu.addSeparator()
        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(self.close)
        project_menu.addAction(exit_action)

        project_button = QToolButton()
        project_button.setText("Projeto")
        project_button.setMenu(project_menu)
        project_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(project_button)

        tools_menu = QMenu(self)
        import_action = QAction("Importar dados para Matriz", self)
        import_action.triggered.connect(self.import_raw_files)
        tools_menu.addAction(import_action)
        tools_button = QToolButton()
        tools_button.setText("Ferramentas")
        tools_button.setMenu(tools_menu)
        tools_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(tools_button)

        help_menu = QMenu(self)
        about = QAction("Sobre o SMB Processor", self)
        about.triggered.connect(
            lambda: QMessageBox.information(
                self, "SMB Processor",
                "Pré-processamento hidrodinâmico e ambiente de modelagem costeira."
            )
        )
        help_menu.addAction(about)
        help_button = QToolButton()
        help_button.setText("Ajuda")
        help_button.setMenu(help_menu)
        help_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(help_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        self.project_status = QLabel("●  Aguardando projeto")
        self.project_status.setObjectName("projectStatus")
        toolbar.addWidget(self.project_status)

    def setup_stfm_welcome(self):
        # Preserva os módulos ocultos ao substituir o widget central inicial.
        self.tabs.setParent(self)
        self.log.setParent(self)
        self.tabs.hide()
        self.log.hide()
        welcome = WelcomePage(self.new_project, self.load_project)
        self.setCentralWidget(welcome)
        self.welcome_widget = welcome
        if hasattr(self, "project_status"):
            self.project_status.setText("●  Aguardando projeto")

    def activate_stfm_interface(self):
        if self.main_interface_created:
            self.setCentralWidget(self.main_central_widget)
            return
        root = QWidget()
        root.setObjectName("workspace")
        layout = QHBoxLayout(root)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(96)
        self.sidebar = sidebar
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 12, 0, 12)
        side_layout.setSpacing(4)
        self.panels_container = QWidget()
        self.panels_container.setObjectName("panelContainer")
        self.panels_container.setFixedWidth(0)
        self.panels_layout = QStackedLayout(self.panels_container)
        self.side_panels, self.current_panel = {}, None

        pages = {index: self.tabs.widget(index) for index in range(self.tabs.count())}
        panel_specs = [
            ("Grade", 2, "grid.png"),
            ("Contornos", 3, "polygon.png"),
            ("Fronteiras", 4, "currents.png"),
            ("Configurações", 5, "settings.png"),
            ("Validação", 6, "run.png"),
            ("Resultados", 7, "raster.png"),
            ("NetCDF", 8, "database.png"),
        ]
        for title, tab_index, icon in panel_specs:
            self.add_stfm_panel(
                title, pages[tab_index], side_layout,
                str(self.assets_stfm / icon)
            )
        side_layout.addStretch()
        map_page = pages[1]
        map_page.setMinimumHeight(280)
        console = QWidget()
        console.setObjectName("consolePanel")
        console_layout = QVBoxLayout(console)
        console_layout.setContentsMargins(12, 8, 12, 10)
        console_layout.setSpacing(6)
        console_header = QHBoxLayout()
        console_title = QLabel("Processamento")
        console_title.setObjectName("consoleTitle")
        self.console_status = QLabel("●  Pronto")
        self.console_status.setObjectName("consoleStatus")
        console_header.addWidget(console_title)
        console_header.addStretch()
        console_header.addWidget(self.console_status)
        console_layout.addLayout(console_header)
        console_layout.addWidget(self.log, 1)
        console.setMaximumHeight(175)
        content_splitter = QSplitter(Qt.Vertical)
        content_splitter.addWidget(map_page)
        content_splitter.addWidget(console)
        content_splitter.setCollapsible(0, False)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setSizes([700, 150])
        map_page.setVisible(True)
        self.map_widget.setVisible(True)
        self.log.setVisible(True)
        layout.addWidget(sidebar)
        layout.addWidget(self.panels_container)
        layout.addWidget(content_splitter, 1)
        self.main_central_widget = root
        self.main_interface_created = True
        self.setCentralWidget(root)
        self.update_project_header()

    def add_stfm_panel(self, title, content, sidebar_layout, icon_path):
        button = QToolButton()
        button.setText(title)
        button.setObjectName("navButton")
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(28, 28))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setToolTip(title)
        button.setFixedSize(96, self.responsive_nav_height())
        button.setCheckable(True)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(18, 20, 18, 16)
        wrapper_layout.setSpacing(10)
        eyebrow = QLabel("CONFIGURAÇÃO")
        eyebrow.setObjectName("panelEyebrow")
        header = QLabel(title)
        header.setObjectName("panelTitle")
        wrapper_layout.addWidget(eyebrow)
        wrapper_layout.addWidget(header)
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.HLine)
        wrapper_layout.addWidget(separator)
        wrapper_layout.addWidget(content, 1)
        content.show()
        scroll_area = QScrollArea()
        scroll_area.setObjectName("panelScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidget(wrapper)
        index = self.panels_layout.count()
        self.panels_layout.addWidget(scroll_area)
        sidebar_layout.addWidget(button)
        self.side_panels[title] = (button, index)
        button.clicked.connect(lambda checked, name=title: self.toggle_stfm_panel(name))

    def toggle_stfm_panel(self, title):
        button, index = self.side_panels[title]
        if self.current_panel and self.current_panel != title:
            self.side_panels[self.current_panel][0].setChecked(False)
        if button.isChecked():
            self.panels_container.setFixedWidth(self.responsive_panel_width())
            self.panels_layout.setCurrentIndex(index)
            self.current_panel = title
        else:
            self.panels_container.setFixedWidth(0)
            self.current_panel = None

    def responsive_panel_width(self):
        """Keep forms usable without taking over the map on smaller screens."""
        available = max(self.width() - 96, 0)
        return max(300, min(440, int(available * 0.30)))

    def responsive_nav_height(self):
        """Fit every navigation entry within the available screen height."""
        usable = max(self.height() - 54 - 24, 1)
        count = max(len(getattr(self, "side_panels", {})), 7)
        return max(48, min(74, usable // count))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if (
            getattr(self, "main_interface_created", False)
            and getattr(self, "current_panel", None)
        ):
            self.panels_container.setFixedWidth(self.responsive_panel_width())
        if getattr(self, "main_interface_created", False):
            nav_height = self.responsive_nav_height()
            for button, _ in self.side_panels.values():
                button.setFixedSize(96, nav_height)

    def update_project_header(self):
        """Reflect project state without changing the project workflow."""
        if not hasattr(self, "project_status"):
            return
        if self.project_path:
            self.project_status.setText("●  Projeto carregado")
        else:
            self.project_status.setText("●  Projeto ativo")

    def close_project(self):
        if self.project_path:
            self.save_project()
        self.project = Project(engine_dir=self.engine_dir.text())
        self.project_path = None
        self.setup_stfm_welcome()

    def build_map_tab(self):
        page = MapPage(
            self.load_contour_on_map,
            self.load_existing_grid_on_map,
            self.clear_map_layers,
            lambda: self.save_map_polygon("domain"),
            lambda: self.save_map_polygon("refinement"),
        )
        self.map_widget = page.map_widget
        self.tabs.addTab(page, "Mapa")

    def load_existing_grid_on_map(self):
        """Select and display a previously generated georeferenced grid."""
        try:
            self.ui_to_project()
            current = self.project.resolve_output(self.project.grid_output)
            initial = current if current.is_dir() else self.project.root / "Grade"
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar um arquivo da grade gerada",
                str(initial),
                (
                    "Arquivos da grade (*.slf *.msh *.png *.json *.cli);;"
                    "Overlay do mapa (grade_CEBSM_overlay.png "
                    "grade_CEBSM_overlay.json);;Todos os arquivos (*)"
                ),
            )
            if not selected:
                return

            # Any generated artifact identifies the result directory; this is
            # more transparent than a native folder picker, which hides files.
            folder = Path(selected).parent
            overlay = folder / "grade_CEBSM_overlay.png"
            metadata_path = folder / "grade_CEBSM_overlay.json"
            missing = [
                path.name for path in (overlay, metadata_path) if not path.is_file()
            ]
            if missing:
                raise FileNotFoundError(
                    "A pasta selecionada não contém uma grade visualizável. "
                    "Arquivo(s) ausente(s): " + ", ".join(missing)
                )

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not {"bounds", "min", "max"}.issubset(metadata):
                raise ValueError(
                    "O arquivo grade_CEBSM_overlay.json não contém limites "
                    "geográficos e faixa batimétrica válidos."
                )

            # Keep later boundary/validation actions pointed at the selected
            # result folder, whether it is inside or outside the project root.
            try:
                configured_output = str(folder.relative_to(self.project.root))
            except ValueError:
                configured_output = str(folder)
            self.grid_name.blockSignals(True)
            self.grid_name.setText(folder.name)
            self.grid_name.blockSignals(False)
            self.grid_output.setText(configured_output)
            self.series_output.setText(str(Path("Fronteiras") / folder.name))
            self.project.grid_output = configured_output
            self.project.series_output = str(Path("Fronteiras") / folder.name)
            self.cas_path.setText(
                str(
                    self.project.root / "Configurações" / folder.name
                    / "modelo_telemac2d.cas"
                )
            )

            self.map_widget.load_bathymetry_overlay(overlay, metadata)
            self.log.appendPlainText(f"Grade existente carregada no mapa: {folder}")
            if hasattr(self, "console_status"):
                self.console_status.setText("●  Grade carregada")
        except Exception as exc:
            self.error(exc)

    def load_contour_on_map(self):
        try:
            self.ui_to_project()
            configured = self.project.contour.strip()
            configured_path = (
                self.project.resolve_input(configured) if configured else None
            )
            initial = (
                configured_path.parent
                if configured_path is not None and configured_path.is_file()
                else self.project.root / "Matriz"
            )
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar contorno",
                str(initial),
                "Contornos KML/KMZ (*.kml *.kmz)",
            )
            if not selected:
                return
            path = Path(selected)
            matrix = self.project.root / "Matriz"
            try:
                value = str(path.relative_to(matrix))
            except ValueError:
                value = str(path)
            self.contour.setText(value)
            self.project.contour = value

            if not path.is_file():
                raise ValueError(f"O contorno selecionado não é um arquivo: {path}")
            if path.suffix.lower() not in {".kml", ".kmz"}:
                raise ValueError("Selecione um arquivo de contorno KML ou KMZ.")

            self.map_widget.load_geojson(load_kml_as_geojson(path))
            self.map_active_role = "domain"
            self.log.appendPlainText(f"Contorno carregado no mapa: {path}")
        except Exception as exc:
            self.error(exc)

    def clear_map_layers(self):
        """Remove every project layer while preserving the selected base map."""
        self.map_widget.clear_layers()
        self.map_active_role = None
        self.log.appendPlainText("Camadas removidas do mapa.")
        if hasattr(self, "console_status"):
            self.console_status.setText("●  Camadas removidas")

    def save_map_polygon(self, role):
        try:
            self.ui_to_project()
            if not self.project.data_dir:
                raise ValueError("Selecione primeiro a pasta de dados na aba Projeto.")
            filename = (
                "dominio_desenhado.kml"
                if role == "domain"
                else "regiao_refinamento_desenhada.kml"
            )
            path = self.project.root / "Matriz" / filename

            def received(data):
                try:
                    if data.get("error"):
                        raise ValueError(data["error"])
                    save_polygon_kml(data, path, filename.removesuffix(".kml"))
                    if role == "domain":
                        self.contour.setText(filename)
                        self.project.contour = filename
                    else:
                        self.refinement_region.setText(filename)
                        self.refine.setChecked(True)
                        self.project.refinement_region = filename
                    self.map_active_role = role
                    self.map_widget.mark_drawings_clean()
                    self.log.appendPlainText(f"Polígono salvo: {path}")
                    QMessageBox.information(
                        self, "Mapa", f"Polígono aplicado e salvo em:\n{path}"
                    )
                except Exception as exc:
                    self.error(exc)

            self.map_widget.request_drawings(received)
        except Exception as exc:
            self.error(exc)

    def build_project_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.data_dir = PathRow(directory=True)
        self.engine_dir = PathRow(directory=True)
        self.project_file = PathRow(save=True)
        form.addRow("Pasta do projeto:", self.data_dir)
        form.addRow("Motores de processamento:", self.engine_dir)
        form.addRow("Arquivo do projeto:", self.project_file)
        row = QHBoxLayout()
        for label, callback in [
            ("Criar novo projeto…", self.new_project),
            ("Carregar", self.load_project),
            ("Salvar", self.save_project),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch()
        form.addRow(row)
        data_actions = QHBoxLayout()
        import_button = QPushButton("Importar dados para Matriz…")
        import_button.clicked.connect(self.import_raw_files)
        open_button = QPushButton("Abrir pasta Matriz")
        open_button.clicked.connect(self.open_matrix)
        data_actions.addWidget(import_button)
        data_actions.addWidget(open_button)
        data_actions.addStretch()
        form.addRow(data_actions)
        structure = QLabel(
            "Estrutura do projeto:\n"
            "Matriz/       dados brutos (GEBCO, TPXO, marégrafo, ADCP, batimetria)\n"
            "Grade/        malha, SELAFIN, Gmsh e figuras\n"
            "Contornos/    CLI, mapa, nós e configuração das aberturas\n"
            "Fronteiras/   PRN, séries interpoladas e gráficos"
        )
        structure.setStyleSheet(
            "font-family:'Cascadia Mono',Consolas;"
            "background:#0c151e;border:1px solid #263a4b;"
            "padding:12px;border-radius:6px;color:#aebdca"
        )
        form.addRow(structure)
        note = QLabel(
            "Ao criar um projeto, o software monta automaticamente Matriz, "
            "Grade, Contornos e Fronteiras. A pasta de motores deve conter os "
            "scripts criar_grade_telemac.py, definir_condicoes_contorno.py e "
            "criar_series_fronteiras.py."
        )
        note.setWordWrap(True)
        form.addRow(note)
        self.tabs.addTab(tab, "Projeto")

    def build_grid_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.contour = PathRow()
        self.gebco = PathRow()
        self.grid_name = QLineEdit()
        self.grid_name.setPlaceholderText("Ex.: grade_500m_sem_refino")
        self.grid_name.textChanged.connect(self.update_grid_output)
        self.grid_output = QLineEdit()
        self.grid_output.setReadOnly(True)
        self.mesh_size = QDoubleSpinBox()
        self.mesh_size.setRange(10, 100000)
        self.mesh_size.setSuffix(" m")
        self.mesh_size.setDecimals(1)
        self.refine = QCheckBox("Ativar refinamento localizado")
        self.refinement_region = PathRow()
        self.refinement_size = QDoubleSpinBox()
        self.refinement_size.setRange(1, 100000)
        self.refinement_size.setSuffix(" m")
        self.transition = QDoubleSpinBox()
        self.transition.setRange(1, 100000)
        self.transition.setSuffix(" m")

        domain_box = QGroupBox("Domínio e dados")
        domain_form = QFormLayout(domain_box)
        domain_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        domain_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        domain_form.addRow("Contorno KML/KMZ:", self.contour)
        domain_form.addRow("GEBCO NetCDF:", self.gebco)
        domain_form.addRow("Nome da grade:", self.grid_name)
        domain_form.addRow("Pasta de saída:", self.grid_output)
        layout.addWidget(domain_box)

        resolution_box = QGroupBox("Resolução da malha")
        resolution_form = QFormLayout(resolution_box)
        resolution_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        resolution_form.addRow("Tamanho geral:", self.mesh_size)
        layout.addWidget(resolution_box)

        refinement_box = QGroupBox("Região de refinamento")
        refinement_form = QFormLayout(refinement_box)
        refinement_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        refinement_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        refinement_form.addRow(self.refine)
        refinement_form.addRow("Polígono:", self.refinement_region)
        refinement_form.addRow("Tamanho refinado:", self.refinement_size)
        refinement_form.addRow("Faixa de transição:", self.transition)
        layout.addWidget(refinement_box)

        buttons = QVBoxLayout()
        generate = QPushButton("Gerar grade e interpolar GEBCO")
        generate.setObjectName("mapActionButton")
        generate.setIcon(QIcon(str(
            Path(__file__).resolve().parents[1]
            / "assets" / "icons" / "generate-grid.svg"
        )))
        generate.setIconSize(QSize(18, 18))
        generate.clicked.connect(self.generate_grid)
        preview = QPushButton("Visualizar resultado")
        preview.setObjectName("mapActionButton")
        preview.setIcon(QIcon(str(
            Path(__file__).resolve().parents[1]
            / "assets" / "icons" / "preview-result.svg"
        )))
        preview.setIconSize(QSize(18, 18))
        preview.clicked.connect(self.preview_grid)
        buttons.addWidget(generate)
        buttons.addWidget(preview)
        layout.addLayout(buttons)
        hint = QLabel("A visualização será aberta sobre o mapa.")
        hint.setObjectName("mutedText")
        layout.addWidget(hint)
        layout.addStretch(1)
        self.tabs.addTab(tab, "Grade e batimetria")

    def build_boundary_tab(self):
        tab = QWidget()
        self.validation_tab = tab
        layout = QVBoxLayout(tab)
        buttons = QGridLayout()
        actions = [
            ("Exportar nós e ordens", self.export_boundaries, "export.svg"),
            ("Encontrar ordem", self.find_boundary_orders, "search.svg"),
            ("Carregar JSON", self.load_boundary_json, "open-file.svg"),
            ("Salvar JSON", self.save_boundary_json, "save.svg"),
            ("Aplicar e gerar CLI", self.apply_boundaries, "apply.svg"),
        ]
        for index, (label, callback, icon) in enumerate(actions):
            button = QPushButton(label)
            self.style_action_button(button, icon)
            button.clicked.connect(callback)
            buttons.addWidget(button, index // 2, index % 2)
        layout.addLayout(buttons)
        self.boundary_editor = QPlainTextEdit()
        self.boundary_editor.setPlaceholderText(
            "O conteúdo de configurar_aberturas.json aparecerá aqui."
        )
        layout.addWidget(self.boundary_editor, 1)
        self.boundary_summary = QLabel("Nenhum CLI validado.")
        layout.addWidget(self.boundary_summary)
        self.tabs.addTab(tab, "Fronteiras")

    def build_series_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.tide_file = PathRow()
        self.flow_file = PathRow()
        self.start = QLineEdit()
        self.end = QLineEdit()
        self.sea_numbers = QLineEdit()
        self.sea_numbers.setPlaceholderText("Ex.: 2, 4, 7")
        self.river_numbers = QLineEdit()
        self.river_numbers.setPlaceholderText("Ex.: 1, 3")
        self.boundary_filename = QLineEdit()
        self.boundary_filename.setPlaceholderText("Ex.: fronteiras_marco_2022.prn")
        self.series_output = QLineEdit()
        self.series_output.setReadOnly(True)
        form.addRow("Série de maré:", self.tide_file)
        form.addRow("Série de vazão:", self.flow_file)
        form.addRow("Início:", self.start)
        form.addRow("Fim inclusivo:", self.end)
        form.addRow("Números dos oceanos SL:", self.sea_numbers)
        form.addRow("Números dos rios Q:", self.river_numbers)
        form.addRow("Pasta de saída:", self.series_output)
        form.addRow("Nome do arquivo PRN:", self.boundary_filename)
        note = QLabel(
            "Separe os números por vírgula. A mesma vazão será aplicada a todos "
            "os rios e a mesma maré a todos os oceanos informados."
        )
        note.setWordWrap(True)
        form.addRow(note)
        button = QPushButton("Gerar PRN e gráfico")
        self.style_action_button(button, "chart.svg")
        button.clicked.connect(self.generate_series)
        form.addRow(button)
        self.tabs.addTab(tab, "Séries temporais")

    def build_configuration_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        path_label = QLabel("Arquivo de parâmetros TELEMAC (.cas)")
        path_label.setObjectName("sectionTitle")
        layout.addWidget(path_label)
        self.cas_path = QLineEdit()
        self.cas_path.setPlaceholderText(
            "Informe o caminho e o nome do arquivo .cas"
        )
        self.cas_path.setToolTip(
            "Edite o nome do arquivo e clique em Salvar. A extensão .cas "
            "será acrescentada automaticamente."
        )
        layout.addWidget(self.cas_path)
        buttons = QGridLayout()
        actions = [
            ("Novo modelo", self.new_cas_file, "new-file.svg"),
            ("Abrir .cas", self.open_cas_file, "open-file.svg"),
            ("Salvar", self.save_cas_file, "save.svg"),
            ("Salvar como…", lambda: self.save_cas_file(save_as=True), "save-as.svg"),
        ]
        for index, (label, callback, icon) in enumerate(actions):
            button = QPushButton(label)
            self.style_action_button(button, icon)
            button.clicked.connect(callback)
            buttons.addWidget(button, index // 2, index % 2)
        layout.addLayout(buttons)
        hint = QLabel(
            "Edite diretamente as palavras-chave do TELEMAC. Linhas iniciadas "
            "por / são comentários; caminhos relativos são resolvidos a partir "
            "da pasta Configurações correspondente à grade."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.cas_editor = QPlainTextEdit()
        self.cas_editor.setPlaceholderText("O conteúdo do arquivo .cas aparecerá aqui.")
        layout.addWidget(self.cas_editor, 1)
        self.tabs.addTab(tab, "Configurações")

    def build_results_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        source_box = QGroupBox("Simulação SELAFIN")
        source_form = QFormLayout(source_box)
        source_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.result_file = QLineEdit()
        self.result_file.setReadOnly(True)
        self.result_crs = QLineEdit("EPSG:32723")
        source_form.addRow("Arquivo:", self.result_file)
        source_form.addRow("CRS da malha:", self.result_crs)
        open_result = QPushButton("Abrir simulação .slf")
        self.style_action_button(open_result, "open-file.svg")
        open_result.clicked.connect(self.open_result_file)
        source_form.addRow(open_result)
        layout.addWidget(source_box)

        variables_box = QGroupBox("Variáveis do modelo")
        variables_form = QFormLayout(variables_box)
        variables_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.result_u = QComboBox()
        self.result_v = QComboBox()
        self.result_level = QComboBox()
        variables_form.addRow("Velocidade U:", self.result_u)
        variables_form.addRow("Velocidade V:", self.result_v)
        variables_form.addRow("Nível:", self.result_level)
        layout.addWidget(variables_box)

        self.result_summary = QLabel("Nenhuma simulação carregada.")
        self.result_summary.setObjectName("mutedText")
        self.result_summary.setWordWrap(True)
        layout.addWidget(self.result_summary)
        animate = QPushButton("Gerar animação de correntes")
        self.style_action_button(animate, "animation.svg")
        animate.clicked.connect(self.generate_current_animation)
        level = QPushButton("Plotar variação de nível")
        self.style_action_button(level, "chart.svg")
        level.clicked.connect(self.generate_level_plot)
        layout.addWidget(animate)
        layout.addWidget(level)
        layout.addStretch()
        self.tabs.addTab(tab, "Resultados")

    def build_netcdf_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        source_box = QGroupBox("Arquivo científico NetCDF")
        source_form = QFormLayout(source_box)
        source_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.netcdf_file = QLineEdit()
        self.netcdf_file.setReadOnly(True)
        source_form.addRow("Arquivo:", self.netcdf_file)
        open_button = QPushButton("Adicionar arquivo .nc")
        self.style_action_button(open_button, "open-file.svg")
        open_button.clicked.connect(self.open_netcdf_file)
        source_form.addRow(open_button)
        self.netcdf_v_file = QLineEdit()
        self.netcdf_v_file.setReadOnly(True)
        source_form.addRow("Arquivo da componente V:", self.netcdf_v_file)
        open_v_button = QPushButton("Adicionar segundo arquivo (componente V)")
        self.style_action_button(open_v_button, "open-file.svg")
        open_v_button.clicked.connect(self.open_netcdf_v_file)
        source_form.addRow(open_v_button)
        layout.addWidget(source_box)

        variable_box = QGroupBox("Variável e recortes")
        self.netcdf_form = QFormLayout(variable_box)
        self.netcdf_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.netcdf_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        scalar_heading = QLabel("CAMPO ESCALAR — temperatura, salinidade, pressão, nível…")
        scalar_heading.setObjectName("panelEyebrow")
        scalar_heading.setWordWrap(True)
        self.netcdf_form.addRow(scalar_heading)
        self.netcdf_variable = QComboBox()
        self.netcdf_variable.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.netcdf_variable.setMinimumContentsLength(12)
        self.netcdf_variable.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.netcdf_variable.currentIndexChanged.connect(self.update_netcdf_dimensions)
        self.netcdf_form.addRow("Variável para visualizar:", self.netcdf_variable)
        vector_heading = QLabel("CAMPO VETORIAL — corrente ou vento")
        vector_heading.setObjectName("panelEyebrow")
        self.netcdf_form.addRow(vector_heading)
        self.netcdf_u = QComboBox()
        self.netcdf_v = QComboBox()
        for combo in (self.netcdf_u, self.netcdf_v):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.netcdf_u.currentIndexChanged.connect(self.update_netcdf_dimensions)
        self.netcdf_v.currentIndexChanged.connect(self.update_netcdf_vector_state)
        self.netcdf_form.addRow("Componente U:", self.netcdf_u)
        self.netcdf_form.addRow("Componente V:", self.netcdf_v)
        self.netcdf_dimension_combos = {}
        layout.addWidget(variable_box)

        self.netcdf_summary = QLabel(
            "Nenhum arquivo carregado. São reconhecidos metadados CF e nomes usuais "
            "de modelos atmosféricos e oceânicos."
        )
        self.netcdf_summary.setObjectName("mutedText")
        self.netcdf_summary.setWordWrap(True)
        layout.addWidget(self.netcdf_summary)
        plot_button = QPushButton("Plotar variável selecionada no mapa")
        self.style_action_button(plot_button, "preview-result.svg")
        plot_button.clicked.connect(self.plot_netcdf_variable)
        layout.addWidget(plot_button)
        animate_scalar = QPushButton("Animar variável ao longo do tempo")
        self.style_action_button(animate_scalar, "animation.svg")
        animate_scalar.clicked.connect(self.animate_netcdf_variable)
        layout.addWidget(animate_scalar)
        self.netcdf_speed_button = QPushButton("Calcular velocidade U/V e plotar no mapa")
        self.style_action_button(self.netcdf_speed_button, "calculate.svg")
        self.netcdf_speed_button.clicked.connect(self.plot_netcdf_speed)
        self.netcdf_speed_button.setEnabled(False)
        layout.addWidget(self.netcdf_speed_button)
        self.netcdf_vector_animation_button = QPushButton(
            "Animar velocidade U/V com vetores"
        )
        self.style_action_button(
            self.netcdf_vector_animation_button, "animation.svg"
        )
        self.netcdf_vector_animation_button.clicked.connect(self.animate_netcdf_speed)
        self.netcdf_vector_animation_button.setEnabled(False)
        layout.addWidget(self.netcdf_vector_animation_button)
        layout.addStretch()
        self.tabs.addTab(tab, "NetCDF")

    def open_netcdf_file(self):
        initial = self.project.root / "Matriz" if self.project.data_dir else Path.home()
        path, _ = QFileDialog.getOpenFileName(
            self, "Adicionar NetCDF", str(initial),
            "NetCDF (*.nc *.nc4 *.cdf);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            with NetCDFFile(path) as reader:
                summary = reader.summary()
            self.netcdf_file.setText(path)
            self.netcdf_summary_data = summary
            self.netcdf_variable.clear()
            self.netcdf_u.clear()
            self.netcdf_v.clear()
            self.netcdf_u.addItem("Selecione uma componente U…", None)
            self.netcdf_v.addItem("Selecione uma componente V…", None)
            for variable in summary["variables"]:
                unit = f" [{variable['unit']}]" if variable["unit"] else ""
                shape = " × ".join(map(str, variable["shape"]))
                self.netcdf_variable.addItem(
                    f"{variable['label']}{unit} — {shape}", variable["name"]
                )
                self.netcdf_u.addItem(f"{variable['label']}{unit}", variable["name"])
                self.netcdf_v.addItem(f"{variable['label']}{unit}", variable["name"])
            self._select_netcdf_component(self.netcdf_u, summary, "u")
            self._select_netcdf_component(self.netcdf_v, summary, "v")
            self.netcdf_v_file.setText(path)
            self.netcdf_v_summary_data = summary
            self.update_netcdf_vector_state()
            dimensions = ", ".join(
                f"{name}={size}" for name, size in summary["dimensions"].items()
            )
            coordinates = ", ".join(
                f"{role}: {name}" for role, name in summary["coordinates"].items()
            ) or "não identificadas"
            self.netcdf_summary.setText(
                f"{len(summary['variables'])} variáveis · {dimensions}\n"
                f"Coordenadas detectadas — {coordinates}"
            )
            self.log.appendPlainText(f"NetCDF carregado: {path}")
        except Exception as exc:
            self.error(exc)

    @staticmethod
    def _select_netcdf_component(combo, summary, component):
        patterns = {
            "u": ("eastward", "u_component", "uo", "ugrd", "u10", "uwnd", "water_u", "wind_u"),
            "v": ("northward", "v_component", "vo", "vgrd", "v10", "vwnd", "water_v", "wind_v"),
        }[component]
        for variable in summary["variables"]:
            text = " ".join((variable["name"], variable["label"], variable["standard_name"])).lower()
            if any(pattern == variable["name"].lower() or pattern in text for pattern in patterns):
                index = combo.findData(variable["name"])
                if index >= 0:
                    combo.setCurrentIndex(index)
                    return True
        combo.setCurrentIndex(0)
        return False

    def update_netcdf_vector_state(self):
        if hasattr(self, "netcdf_speed_button"):
            enabled = bool(self.netcdf_u.currentData() and self.netcdf_v.currentData())
            self.netcdf_speed_button.setEnabled(enabled)
            self.netcdf_vector_animation_button.setEnabled(enabled)

    def open_netcdf_v_file(self):
        initial = Path(self.netcdf_file.text()).parent if self.netcdf_file.text() else Path.home()
        path, _ = QFileDialog.getOpenFileName(
            self, "Adicionar NetCDF da componente V", str(initial),
            "NetCDF (*.nc *.nc4 *.cdf);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            with NetCDFFile(path) as reader:
                summary = reader.summary()
            self.netcdf_v_file.setText(path)
            self.netcdf_v_summary_data = summary
            self.netcdf_v.clear()
            self.netcdf_v.addItem("Selecione uma componente V…", None)
            for variable in summary["variables"]:
                unit = f" [{variable['unit']}]" if variable["unit"] else ""
                self.netcdf_v.addItem(f"{variable['label']}{unit}", variable["name"])
            self._select_netcdf_component(self.netcdf_v, summary, "v")
            self.update_netcdf_vector_state()
            self.log.appendPlainText(f"Componente V carregada de: {path}")
        except Exception as exc:
            self.error(exc)

    def update_netcdf_dimensions(self):
        while self.netcdf_form.rowCount() > 5:
            self.netcdf_form.removeRow(5)
        self.netcdf_dimension_combos = {}
        name = (self.netcdf_u.currentData() if self.sender() is self.netcdf_u
                else self.netcdf_variable.currentData())
        if not name or not hasattr(self, "netcdf_summary_data"):
            return
        variable = next(
            item for item in self.netcdf_summary_data["variables"]
            if item["name"] == name
        )
        spatial = set(variable.get("spatial_dimensions", []))
        try:
            with NetCDFFile(self.netcdf_file.text()) as reader:
                for dimension in variable["dimensions"]:
                    if dimension in spatial:
                        continue
                    combo = QComboBox()
                    for value in reader.dimension_values(dimension):
                        combo.addItem(value["label"], value["index"])
                    combo.setToolTip(
                        f"Escolha o índice de {dimension}; dimensões espaciais são mantidas."
                    )
                    self.netcdf_form.addRow(f"{dimension}:", combo)
                    self.netcdf_dimension_combos[dimension] = combo
        except Exception as exc:
            self.error(exc)

    def plot_netcdf_variable(self):
        try:
            source = Path(self.netcdf_file.text())
            variable = self.netcdf_variable.currentData()
            if not source.is_file() or not variable:
                raise FileNotFoundError("Adicione primeiro um arquivo NetCDF válido.")
            selections = {
                dimension: int(combo.currentData())
                for dimension, combo in self.netcdf_dimension_combos.items()
            }
            root = self.project.root if self.project.data_dir else source.parent
            safe_variable = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(variable))
            output = root / "Resultados" / source.stem / f"netcdf_{safe_variable}.png"
            command = (
                sys.executable,
                ["-m", "smb_preprocessor.core.netcdf_data", "overlay",
                 str(source), str(variable), str(output), "--selections",
                 json.dumps(selections)],
                root,
            )
            self.run(command, lambda: self.load_netcdf_overlay(output))
        except Exception as exc:
            self.error(exc)

    def plot_netcdf_speed(self):
        try:
            source_u = Path(self.netcdf_file.text())
            source_v = Path(self.netcdf_v_file.text())
            variable_u, variable_v = self.netcdf_u.currentData(), self.netcdf_v.currentData()
            if not source_u.is_file() or not source_v.is_file() or not variable_u or not variable_v:
                raise FileNotFoundError("Selecione os arquivos e as componentes U e V.")
            selections = {name: int(combo.currentData()) for name, combo in self.netcdf_dimension_combos.items()}
            u_info = next(v for v in self.netcdf_summary_data["variables"] if v["name"] == variable_u)
            v_info = next(v for v in self.netcdf_v_summary_data["variables"] if v["name"] == variable_v)
            u_extra = [d for d in u_info["dimensions"] if d not in set(u_info["spatial_dimensions"])]
            v_extra = [d for d in v_info["dimensions"] if d not in set(v_info["spatial_dimensions"])]
            values = [selections.get(d, 0) for d in u_extra]
            selections_v = {dimension: values[i] if i < len(values) else 0 for i, dimension in enumerate(v_extra)}
            root = self.project.root if self.project.data_dir else source_u.parent
            output = root / "Resultados" / source_u.stem / "netcdf_velocidade_uv.png"
            args = ["-m", "smb_preprocessor.core.netcdf_data", "overlay",
                    str(source_u), str(variable_u), str(output), "--selections", json.dumps(selections),
                    "--source-v", str(source_v), "--variable-v", str(variable_v),
                    "--selections-v", json.dumps(selections_v)]
            self.run((sys.executable, args, root), lambda: self.load_netcdf_overlay(output))
        except Exception as exc:
            self.error(exc)

    def load_netcdf_overlay(self, output):
        metadata_path = Path(output).with_suffix(".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.map_widget.load_netcdf_overlay(Path(output), metadata)
        self.log.appendPlainText(f"Campo NetCDF carregado no mapa: {output}")

    def animate_netcdf_variable(self):
        try:
            source = Path(self.netcdf_file.text())
            variable = self.netcdf_variable.currentData()
            if not source.is_file() or not variable:
                raise FileNotFoundError("Selecione um arquivo e uma variável NetCDF.")
            selections = {
                name: int(combo.currentData())
                for name, combo in self.netcdf_dimension_combos.items()
            }
            root = self.project.root if self.project.data_dir else source.parent
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(variable))
            output = root / "Resultados" / source.stem / f"animacao_{safe}"
            args = ["-m", "smb_preprocessor.core.netcdf_data", "animate",
                    str(source), str(variable), str(output), "--selections",
                    json.dumps(selections)]
            self.run((sys.executable, args, root), lambda: self.load_netcdf_animation(output))
        except Exception as exc:
            self.error(exc)

    def animate_netcdf_speed(self):
        try:
            source_u = Path(self.netcdf_file.text())
            source_v = Path(self.netcdf_v_file.text())
            variable_u, variable_v = self.netcdf_u.currentData(), self.netcdf_v.currentData()
            if not source_u.is_file() or not source_v.is_file() or not variable_u or not variable_v:
                raise FileNotFoundError("Selecione os arquivos e as componentes U e V.")
            selections = {name: int(combo.currentData()) for name, combo in self.netcdf_dimension_combos.items()}
            u_info = next(v for v in self.netcdf_summary_data["variables"] if v["name"] == variable_u)
            v_info = next(v for v in self.netcdf_v_summary_data["variables"] if v["name"] == variable_v)
            u_extra = [d for d in u_info["dimensions"] if d not in set(u_info["spatial_dimensions"])]
            v_extra = [d for d in v_info["dimensions"] if d not in set(v_info["spatial_dimensions"])]
            values = [selections.get(d, 0) for d in u_extra]
            selections_v = {d: values[i] if i < len(values) else 0 for i, d in enumerate(v_extra)}
            root = self.project.root if self.project.data_dir else source_u.parent
            output = root / "Resultados" / source_u.stem / "animacao_velocidade_uv"
            args = ["-m", "smb_preprocessor.core.netcdf_data", "animate",
                    str(source_u), str(variable_u), str(output), "--selections", json.dumps(selections),
                    "--source-v", str(source_v), "--variable-v", str(variable_v),
                    "--selections-v", json.dumps(selections_v)]
            self.run((sys.executable, args, root), lambda: self.load_netcdf_animation(output))
        except Exception as exc:
            self.error(exc)

    def load_netcdf_animation(self, output):
        metadata_path = Path(output) / "animacao_netcdf.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        frames = [Path(output) / name for name in metadata["frames"]]
        self.map_widget.load_result_animation(frames, metadata)
        self.log.appendPlainText(f"Animação NetCDF carregada no mapa: {output}")

    def cas_template(self) -> str:
        grid_id = self.project.grid_id
        boundary_file = self.boundary_filename.text().strip() or "fronteiras.prn"
        return (
            "/ Arquivo de configuração TELEMAC-2D — SMB Processor\n"
            "/ Revise os caminhos e parâmetros antes de executar a simulação.\n\n"
            "TITLE = 'SIMULACAO SMB PROCESSOR'\n"
            "GEOMETRY FILE = '../../Grade/" + grid_id + "/geo_CEBSM.slf'\n"
            "GEOMETRY FILE FORMAT = 'SERAFIND'\n"
            "BOUNDARY CONDITIONS FILE = '../../Contornos/" + grid_id
            + "/geo_CEBSM_configurado.cli'\n"
            "LIQUID BOUNDARIES FILE = '../../Fronteiras/" + grid_id + "/"
            + boundary_file + "'\n"
            "RESULTS FILE = '../../Resultados/" + grid_id + "/resultados.slf'\n\n"
            "/ Tempo e saídas\n"
            "TIME STEP = 10.0\n"
            "NUMBER OF TIME STEPS = 8640\n"
            "GRAPHIC PRINTOUT PERIOD = 60\n"
            "VARIABLES FOR GRAPHIC PRINTOUTS = 'U,V,H,S,B'\n\n"
            "/ Física e solução numérica\n"
            "EQUATIONS = 'SAINT-VENANT FE'\n"
            "TURBULENCE MODEL = 1\n"
            "LAW OF BOTTOM FRICTION = 3\n"
            "FRICTION COEFFICIENT = 0.025\n"
            "PARALLEL PROCESSORS = 1\n"
        )

    def new_cas_file(self):
        try:
            self.ui_to_project()
            if not self.project.data_dir:
                raise ValueError("Crie ou carregue um projeto primeiro.")
            path = self.project.configuration_dir / "modelo_telemac2d.cas"
            self.cas_path.setText(str(path))
            self.cas_editor.setPlainText(self.cas_template())
            self.project.cas_file = str(path.relative_to(self.project.root))
        except Exception as exc:
            self.error(exc)

    def open_cas_file(self):
        if not self.project.data_dir:
            self.error(ValueError("Crie ou carregue um projeto primeiro."))
            return
        initial = self.project.configuration_dir
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir configuração TELEMAC", str(initial),
            "Configuração TELEMAC (*.cas);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            selected = Path(path)
            self.cas_editor.setPlainText(selected.read_text(encoding="utf-8"))
            self.cas_path.setText(str(selected))
            try:
                self.project.cas_file = str(selected.relative_to(self.project.root))
            except ValueError:
                self.project.cas_file = str(selected)
        except Exception as exc:
            self.error(exc)

    def save_cas_file(self, save_as=False):
        try:
            if not self.project.data_dir:
                raise ValueError("Crie ou carregue um projeto primeiro.")
            current = self.cas_path.text().strip()
            if save_as or not current:
                initial = self.project.configuration_dir / "modelo_telemac2d.cas"
                current, _ = QFileDialog.getSaveFileName(
                    self, "Salvar configuração TELEMAC", str(initial),
                    "Configuração TELEMAC (*.cas)",
                )
            if not current:
                return
            path = Path(current)
            if not path.is_absolute():
                path = self.project.configuration_dir / path
            if path.suffix.lower() != ".cas":
                path = path.with_suffix(".cas")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.cas_editor.toPlainText(), encoding="utf-8")
            self.cas_path.setText(str(path))
            try:
                self.project.cas_file = str(path.relative_to(self.project.root))
            except ValueError:
                self.project.cas_file = str(path)
            self.log.appendPlainText(f"Configuração TELEMAC salva: {path}")
        except Exception as exc:
            self.error(exc)

    @staticmethod
    def _select_combo_data(combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def open_result_file(self):
        if not self.project.data_dir:
            self.error(ValueError("Crie ou carregue um projeto primeiro."))
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir resultado SELAFIN", str(self.project.root / "Matriz"),
            "Resultados SELAFIN (*.slf);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            selected = Path(path)
            with SelafinFile(selected) as reader:
                summary = reader.summary()
                combos = (self.result_u, self.result_v, self.result_level)
                for combo in combos:
                    combo.clear()
                    for variable in summary["variables"]:
                        label = variable["name"]
                        if variable["unit"]:
                            label += f" [{variable['unit']}]"
                        combo.addItem(label, variable["index"])
                self._select_combo_data(self.result_u, reader.variable_index(U_NAMES))
                self._select_combo_data(self.result_v, reader.variable_index(V_NAMES))
                self._select_combo_data(
                    self.result_level, reader.variable_index(LEVEL_NAMES)
                )
            self.result_file.setText(str(selected))
            self.project.result_file = str(selected)
            self.result_summary.setText(
                f"{summary['steps']} passos de tempo · {summary['nodes']:,} nós · "
                f"{summary['elements']:,} elementos · "
                f"{len(summary['variables'])} variáveis"
            )
            self.log.appendPlainText(f"Simulação SELAFIN carregada: {selected}")
            existing_animation = (
                self.project.root / "Resultados" / selected.stem / "correntes"
            )
            if (existing_animation / "animacao_correntes.json").is_file():
                self.load_current_animation(existing_animation)
        except Exception as exc:
            self.error(exc)

    def generate_current_animation(self):
        try:
            source = Path(self.result_file.text().strip())
            if not source.is_file():
                raise FileNotFoundError("Abra primeiro uma simulação .slf válida.")
            output = self.project.root / "Resultados" / source.stem / "correntes"
            command = (
                sys.executable,
                [
                    "-m", "smb_preprocessor.core.selafin_results",
                    "velocity-animation", str(source), str(output),
                    "--crs", self.result_crs.text().strip() or "EPSG:32723",
                    "--u-variable", str(self.result_u.currentData()),
                    "--v-variable", str(self.result_v.currentData()),
                ],
                self.project.root,
            )
            self.project.result_file = str(source)
            self.project.result_crs = self.result_crs.text().strip()
            self.run(command, lambda: self.load_current_animation(output))
        except Exception as exc:
            self.error(exc)

    def load_current_animation(self, output: Path):
        try:
            metadata_path = output / "animacao_correntes.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            # The static grid gives geographic context to the wet-only current
            # field and makes its alignment/complete model footprint explicit.
            grid = self.project.resolve_output(self.project.grid_output)
            bathymetry = grid / "grade_CEBSM_overlay.png"
            bathymetry_metadata = grid / "grade_CEBSM_overlay.json"
            if bathymetry.is_file() and bathymetry_metadata.is_file():
                grid_info = json.loads(
                    bathymetry_metadata.read_text(encoding="utf-8")
                )
                self.map_widget.load_bathymetry_overlay(bathymetry, grid_info)
            if metadata.get("video"):
                self.map_widget.load_result_video(output / metadata["video"], metadata)
            else:
                frames = [output / name for name in metadata["frames"]]
                self.map_widget.load_result_animation(frames, metadata)
            self.log.appendPlainText(f"Animação de correntes carregada: {output}")
        except Exception as exc:
            self.error(exc)

    def generate_level_plot(self):
        try:
            source = Path(self.result_file.text().strip())
            if not source.is_file():
                raise FileNotFoundError("Abra primeiro uma simulação .slf válida.")
            output = (
                self.project.root / "Resultados" / source.stem
                / "variacao_nivel.png"
            )
            command = (
                sys.executable,
                [
                    "-m", "smb_preprocessor.core.selafin_results",
                    "level-plot", str(source), str(output),
                    "--variable", str(self.result_level.currentData()),
                ],
                self.project.root,
            )
            self.run(command, lambda: self.show_series_popup(output))
        except Exception as exc:
            self.error(exc)

    def build_validation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        button = QPushButton("Validar arquivos gerados")
        self.style_action_button(button, "validate.svg")
        button.clicked.connect(self.validate_outputs)
        layout.addWidget(button)
        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        layout.addWidget(self.validation_text, 1)
        self.tabs.addTab(tab, "Validação")

    def apply_defaults(self):
        known_engine = Path(
            r"C:\Users\wesxl\Documents\TELEMAC\dados_preproc\CEBSM"
        )
        if (known_engine / "criar_grade_telemac.py").is_file():
            self.project.engine_dir = str(known_engine)
        self.project_to_ui()

    def ui_to_project(self):
        p = self.project
        p.data_dir = self.data_dir.text()
        p.engine_dir = self.engine_dir.text()
        p.contour = self.contour.text()
        p.gebco = self.gebco.text()
        p.grid_output = self.grid_output.text().strip()
        p.mesh_size = self.mesh_size.value()
        p.refinement_region = (
            self.refinement_region.text() if self.refine.isChecked() else ""
        )
        p.refinement_size = self.refinement_size.value()
        p.transition = self.transition.value()
        p.tide_file = self.tide_file.text()
        p.flow_file = self.flow_file.text()
        p.start, p.end = self.start.text().strip(), self.end.text().strip()
        p.sea_boundaries = self.sea_numbers.text().strip()
        p.river_boundaries = self.river_numbers.text().strip()
        filename = Path(self.boundary_filename.text().strip()).name
        if filename and not filename.lower().endswith(".prn"):
            filename += ".prn"
            self.boundary_filename.setText(filename)
        p.boundary_filename = filename
        p.series_output = self.series_output.text().strip()
        if hasattr(self, "cas_path") and self.cas_path.text().strip():
            cas_path = Path(self.cas_path.text().strip())
            try:
                p.cas_file = str(cas_path.relative_to(p.root))
            except ValueError:
                p.cas_file = str(cas_path)
        if hasattr(self, "result_file"):
            p.result_file = self.result_file.text().strip()
            p.result_crs = self.result_crs.text().strip() or "EPSG:32723"

    def project_to_ui(self):
        p = self.project
        self.data_dir.setText(p.data_dir)
        self.engine_dir.setText(p.engine_dir)
        self.contour.setText(p.contour)
        self.gebco.setText(p.gebco)
        output = Path(p.grid_output)
        if p.grid_output in {"", "Grade"}:
            name = f"grade_{int(p.mesh_size)}m"
        elif output.parent.name.lower() == "grade":
            name = output.name
        else:
            name = output.name
        self.grid_name.blockSignals(True)
        self.grid_name.setText(name)
        self.grid_name.blockSignals(False)
        configured_output = (
            str(Path("Grade") / name)
            if p.grid_output in {"", "Grade"}
            else p.grid_output
        )
        p.grid_output = configured_output
        self.grid_output.setText(configured_output)
        self.mesh_size.setValue(p.mesh_size)
        self.refine.setChecked(bool(p.refinement_region))
        self.refinement_region.setText(p.refinement_region)
        self.refinement_size.setValue(p.refinement_size)
        self.transition.setValue(p.transition)
        self.tide_file.setText(p.tide_file)
        self.flow_file.setText(p.flow_file)
        self.start.setText(p.start)
        self.end.setText(p.end)
        self.sea_numbers.setText(p.sea_boundaries)
        self.river_numbers.setText(p.river_boundaries)
        self.boundary_filename.setText(p.boundary_filename)
        p.series_output = str(Path("Fronteiras") / p.grid_id)
        self.series_output.setText(p.series_output)
        if p.data_dir:
            cas_path = Path(p.cas_file)
            if not cas_path.is_absolute():
                cas_path = p.root / cas_path
            self.cas_path.setText(str(cas_path))
            if cas_path.is_file():
                self.cas_editor.setPlainText(cas_path.read_text(encoding="utf-8"))
        else:
            self.cas_path.clear()
            self.cas_editor.clear()
        self.result_file.setText(p.result_file)
        self.result_crs.setText(p.result_crs or "EPSG:32723")

    def update_grid_output(self, name):
        name = str(name).strip()
        self.grid_output.setText(str(Path("Grade") / name) if name else "Grade")
        if hasattr(self, "series_output"):
            self.series_output.setText(
                str(Path("Fronteiras") / name) if name else "Fronteiras"
            )
        if name and self.project.data_dir and hasattr(self, "cas_path"):
            self.cas_path.setText(
                str(self.project.root / "Configurações" / name / "modelo_telemac2d.cas")
            )

    def new_project(self):
        parent = QFileDialog.getExistingDirectory(
            self, "Escolha onde criar o projeto", str(Path.home() / "Documents")
        )
        if not parent:
            return
        name, ok = QInputDialog.getText(
            self, "Nome do projeto", "Nome da nova pasta do projeto:"
        )
        name = name.strip()
        if not ok or not name:
            return
        if any(char in name for char in '<>:"/\\|?*'):
            self.error(ValueError("O nome contém caracteres inválidos."))
            return
        root = Path(parent) / name
        try:
            engine = self.engine_dir.text() or self.project.engine_dir
            self.project = self.project_service.create(root, name, engine)
            self.project_path = root / "projeto_cebsm.json"
            self.project_file.setText(str(self.project_path))
            self.project_to_ui()
            cas_path = self.project.configuration_dir / "modelo_telemac2d.cas"
            cas_path.write_text(self.cas_template(), encoding="utf-8")
            self.project.cas_file = str(cas_path.relative_to(self.project.root))
            self.cas_path.setText(str(cas_path))
            self.cas_editor.setPlainText(cas_path.read_text(encoding="utf-8"))
            self.project_service.save(self.project, self.project_path)
            self.set_modules_enabled(True)
            self.update_project_header()
            self.log.appendPlainText(f"Projeto criado: {root}")
            QMessageBox.information(
                self, "Projeto criado",
                "Estrutura criada:\n"
                f"{root}\n\nMatriz\nGrade\nContornos\nFronteiras\n"
                "Configurações\nResultados\n\n"
                f"Subpastas iniciais: {self.project.grid_id}"
            )
        except Exception as exc:
            self.error(exc)

    def load_project(self):
        path = self.project_file.text()
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Carregar projeto", str(Path.home()), "JSON (*.json)"
            )
        if not path:
            return
        try:
            self.project = self.project_service.load(Path(path))
            self.project.ensure_structure()
            self.project_path = Path(path)
            self.project_file.setText(path)
            self.project_to_ui()
            self.set_modules_enabled(True)
            self.update_project_header()
            self.log.appendPlainText(f"Projeto carregado: {path}")
        except Exception as exc:
            self.error(exc)

    def save_project(self):
        self.ui_to_project()
        if not self.project.data_dir:
            self.error(ValueError("Crie ou carregue um projeto antes de salvar."))
            return
        path = self.project_file.text()
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salvar projeto", "projeto_cebsm.json", "JSON (*.json)"
            )
        if not path:
            return
        try:
            self.project_path = Path(path)
            self.project_service.save(self.project, self.project_path)
            self.project_file.setText(path)
            self.update_project_header()
            self.log.appendPlainText(f"Projeto salvo: {path}")
        except Exception as exc:
            self.error(exc)

    def import_raw_files(self):
        if not self.project.data_dir:
            self.error(ValueError("Crie ou carregue um projeto primeiro."))
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Importar dados brutos para Matriz", str(Path.home())
        )
        if not files:
            return
        matrix = self.project.root / "Matriz"
        matrix.mkdir(exist_ok=True)
        copied = 0
        try:
            for file in files:
                source = Path(file)
                destination = matrix / source.name
                if destination.exists():
                    answer = QMessageBox.question(
                        self, "Arquivo existente",
                        f"{source.name} já existe em Matriz. Substituir?"
                    )
                    if answer != QMessageBox.Yes:
                        continue
                shutil.copy2(source, destination)
                copied += 1
            self.log.appendPlainText(f"{copied} arquivo(s) importado(s) para {matrix}")
        except Exception as exc:
            self.error(exc)

    def open_matrix(self):
        if not self.project.data_dir:
            self.error(ValueError("Crie ou carregue um projeto primeiro."))
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str((self.project.root / "Matriz").resolve()))
        )

    def set_modules_enabled(self, enabled):
        # Projeto é sempre a primeira aba; os módulos operacionais exigem projeto.
        for index in range(1, self.tabs.count()):
            self.tabs.setTabEnabled(index, enabled)
        if enabled:
            self.activate_stfm_interface()
        elif hasattr(self, "assets_stfm"):
            self.setup_stfm_welcome()

    def run(self, command, callback=None):
        if self.process_runner.running:
            QMessageBox.warning(self, "Processamento", "Já existe uma tarefa em execução.")
            return
        program, args, cwd = command
        self.pending_callback = callback
        self.process_output = ""
        if hasattr(self, "console_status"):
            self.console_status.setText("●  Processando")
        self.log.appendPlainText(f"\n> {program} {' '.join(args)}")
        self.process_runner.start(command)

    def read_process(self, text):
        self.process_output += text
        self.log.moveCursor(self.log.textCursor().End)
        self.log.insertPlainText(text)
        self.log.ensureCursorVisible()

    def process_finished(self, code, output):
        self.process_output = output
        self.log.appendPlainText(f"\nProcesso concluído com código {code}.")
        if hasattr(self, "console_status"):
            self.console_status.setText(
                "●  Concluído" if code == 0 else "●  Falha no processamento"
            )
        callback, self.pending_callback = self.pending_callback, None
        if code == 0 and callback:
            callback()
        elif code != 0:
            detail = self.process_output.strip()
            if len(detail) > 1600:
                detail = detail[-1600:]
            QMessageBox.critical(
                self,
                "Falha",
                "O processamento falhou.\n\n"
                + (detail or "Consulte o painel de log."),
            )

    def generate_grid(self):
        """Use the current edited map geometry before running the grid engine."""
        try:
            self.ui_to_project()
            role = getattr(self, "map_active_role", None)

            def received(state):
                try:
                    if state.get("error"):
                        raise ValueError(state["error"])
                    if state.get("dirty") and role in {"domain", "refinement"}:
                        filename = (
                            "dominio_desenhado.kml"
                            if role == "domain"
                            else "regiao_refinamento_desenhada.kml"
                        )
                        path = self.project.root / "Matriz" / filename
                        save_polygon_kml(
                            state.get("drawings", {}),
                            path,
                            filename.removesuffix(".kml"),
                        )
                        if role == "domain":
                            self.contour.setText(filename)
                            self.project.contour = filename
                        else:
                            self.refinement_region.setText(filename)
                            self.refine.setChecked(True)
                            self.project.refinement_region = filename
                        self.map_widget.mark_drawings_clean()
                        self.log.appendPlainText(
                            f"Contorno editado sincronizado antes da grade: {path}"
                        )
                    self._start_grid_generation()
                except Exception as exc:
                    self.error(exc)

            self.map_widget.request_drawing_state(received)
        except Exception as exc:
            self.error(exc)

    def _start_grid_generation(self):
        try:
            self.ui_to_project()
            name = self.grid_name.text().strip()
            if not name:
                raise ValueError("Informe um nome para a grade.")
            if any(char in name for char in '<>:"/\\|?*'):
                raise ValueError(
                    "O nome da grade contém caracteres inválidos. "
                    "Use letras, números, hífen ou sublinhado."
                )
            output = self.project.resolve_output(self.project.grid_output)
            self.project.ensure_grid_structure()
            if output.exists() and any(output.iterdir()):
                raise FileExistsError(
                    f"Já existem arquivos para a grade '{name}'.\n"
                    "Escolha outro nome para não sobrescrever os resultados."
                )
            self.run(self.workflow_service.grid(self.project), self.preview_grid)
        except Exception as exc:
            self.error(exc)

    def preview_grid(self):
        self.ui_to_project()
        output = self.project.resolve_output(self.project.grid_output)
        image = output / "grade_CEBSM_overlay.png"
        metadata_path = output / "grade_CEBSM_overlay.json"
        if not image.is_file() or not metadata_path.is_file():
            self.error(
                FileNotFoundError(
                    "A camada cartográfica da grade não foi encontrada. "
                    "Gere novamente esta grade para criar o overlay do mapa."
                )
            )
            return
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.map_widget.load_bathymetry_overlay(image, metadata)
        self.log.appendPlainText(f"Batimetria carregada sobre o mapa: {image}")

    def show_image_over_map(self, image: Path, title: str):
        pixmap = QPixmap(str(image))
        if pixmap.isNull():
            self.error(ValueError(f"Não foi possível abrir a figura: {image}"))
            return

        previous = getattr(self, "image_overlay", None)
        if previous is not None:
            previous.close()

        dialog = QDialog(self.map_widget)
        dialog.setWindowTitle(title)
        dialog.setModal(False)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setStyleSheet(
            "QDialog{background:#17232d;border:2px solid #4f7589;border-radius:8px}"
            "QLabel{color:white} QPushButton{min-width:34px;min-height:28px}"
        )
        layout = QVBoxLayout(dialog)
        header = QHBoxLayout()
        heading = QLabel(title)
        heading.setStyleSheet("font-size:16px;font-weight:700;padding:4px")
        close_button = QPushButton("×")
        close_button.setToolTip("Fechar visualização")
        close_button.clicked.connect(dialog.close)
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(close_button)
        layout.addLayout(header)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        available = self.map_widget.size() - QSize(70, 90)
        image_label.setPixmap(
            pixmap.scaled(
                max(available.width(), 360),
                max(available.height(), 280),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        layout.addWidget(image_label, 1)

        width = min(
            max(image_label.pixmap().width() + 28, 420),
            max(self.map_widget.width() - 30, 320),
        )
        height = min(
            max(image_label.pixmap().height() + 72, 340),
            max(self.map_widget.height() - 30, 260),
        )
        dialog.resize(width, height)
        dialog.move(
            max((self.map_widget.width() - dialog.width()) // 2, 0),
            max((self.map_widget.height() - dialog.height()) // 2, 0),
        )
        dialog.show()
        dialog.raise_()
        self.image_overlay = dialog

    def show_series_popup(self, image: Path):
        pixmap = QPixmap(str(image))
        if pixmap.isNull():
            self.error(ValueError(f"Não foi possível abrir o gráfico: {image}"))
            return
        previous = getattr(self, "series_popup", None)
        if previous is not None:
            previous.close()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Séries geradas — {image.name}")
        dialog.setModal(False)
        dialog.resize(1050, 650)
        layout = QVBoxLayout(dialog)
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setPixmap(
            pixmap.scaled(1000, 590, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        layout.addWidget(label, 1)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button, 0, Qt.AlignRight)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self.series_popup = dialog

    def export_boundaries(self):
        try:
            self.ui_to_project()
            self.run(
                self.workflow_service.boundary(self.project, "exportar"),
                self.after_boundary_export,
            )
        except Exception as exc:
            self.error(exc)

    def boundary_json_path(self):
        self.ui_to_project()
        return self.project.contours_dir / "configurar_aberturas.json"

    def sync_boundary_outputs(self):
        grade = self.project.resolve_output(self.project.grid_output)
        destination = self.project.contours_dir
        destination.mkdir(parents=True, exist_ok=True)
        names = [
            "nos_de_contorno.csv",
            "mapa_nos_contorno.html",
            "configurar_aberturas.json",
            "geo_CEBSM.cli",
            "geo_CEBSM_configurado.cli",
        ]
        for name in names:
            source = grade / name
            if source.is_file():
                shutil.copy2(source, destination / name)

        # Uma exportação nova ainda não possui CLI configurado. Não deixe um
        # arquivo homônimo da grade anterior parecer válido na pasta oficial.
        configured_source = grade / "geo_CEBSM_configurado.cli"
        configured_destination = destination / "geo_CEBSM_configurado.cli"
        if not configured_source.is_file() and configured_destination.is_file():
            index = 1
            while True:
                backup = destination / (
                    f"geo_CEBSM_configurado_grade_anterior_{index}.cli"
                )
                if not backup.exists():
                    configured_destination.replace(backup)
                    self.log.appendPlainText(
                        "CLI da grade anterior arquivado: " + str(backup)
                    )
                    break
                index += 1

    def after_boundary_export(self):
        self.sync_boundary_outputs()
        self.load_boundary_json()

    def load_boundary_json(self):
        path = self.boundary_json_path()
        try:
            self.boundary_editor.setPlainText(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.error(exc)

    def save_boundary_json(self):
        path = self.boundary_json_path()
        try:
            parsed = json.loads(self.boundary_editor.toPlainText())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # O motor lê a configuração junto da grade; Contornos é a pasta
            # oficial do projeto e Grade recebe apenas uma cópia de trabalho.
            grade_copy = (
                self.project.resolve_output(self.project.grid_output)
                / "configurar_aberturas.json"
            )
            grade_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, grade_copy)
            self.log.appendPlainText(f"JSON salvo: {path}")
        except Exception as exc:
            self.error(exc)

    def find_boundary_orders(self):
        """Show exported boundary order points on the application's main map."""
        try:
            self.ui_to_project()
            csv_path = self.project.contours_dir / "nos_de_contorno.csv"
            if not csv_path.is_file():
                grid_copy = (
                    self.project.resolve_output(self.project.grid_output)
                    / "nos_de_contorno.csv"
                )
                if grid_copy.is_file():
                    csv_path = grid_copy
                else:
                    raise FileNotFoundError(
                        "Os nós de contorno ainda não foram exportados. "
                        "Clique primeiro em ‘Exportar nós e ordens’."
                    )

            with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            required = {
                "contorno", "tipo_contorno", "ordem", "no_telemac",
                "longitude", "latitude",
            }
            if not rows or not required.issubset(rows[0]):
                raise ValueError(
                    "O CSV de contornos não possui as colunas necessárias "
                    "para localizar as ordens."
                )

            records = []
            for row in rows:
                records.append(
                    {
                        "contorno": int(row["contorno"]),
                        "tipo_contorno": row["tipo_contorno"],
                        "ordem": int(row["ordem"]),
                        "no_telemac": int(row["no_telemac"]),
                        "longitude": float(row["longitude"]),
                        "latitude": float(row["latitude"]),
                    }
                )

            # Restore the generated grid beneath the interactive node markers
            # when a project was reopened in a new application session.
            grid = self.project.resolve_output(self.project.grid_output)
            overlay = grid / "grade_CEBSM_overlay.png"
            metadata_path = grid / "grade_CEBSM_overlay.json"
            if overlay.is_file() and metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.map_widget.load_bathymetry_overlay(overlay, metadata)
            self.map_widget.load_boundary_nodes(records)
            self.log.appendPlainText(
                f"{len(records)} nós carregados no mapa para encontrar ordens: "
                f"{csv_path}"
            )
        except Exception as exc:
            self.error(exc)

    def open_map(self):
        """Backward-compatible alias for projects using the previous action."""
        self.find_boundary_orders()

    def apply_boundaries(self):
        try:
            self.save_boundary_json()
            self.run(
                self.workflow_service.boundary(self.project, "aplicar"),
                self.after_boundary_apply,
            )
        except Exception as exc:
            self.error(exc)

    def after_boundary_apply(self):
        self.sync_boundary_outputs()
        self.update_cli_summary()

    def update_cli_summary(self):
        path = self.project.contours_dir / "geo_CEBSM_configurado.cli"
        summary = summarize_cli(path)
        self.boundary_summary.setText(
            " | ".join(f"{key}: {value}" for key, value in summary.items())
            or "Nenhum código encontrado."
        )

    def generate_series(self):
        try:
            self.ui_to_project()
            if not self.project.sea_boundaries:
                raise ValueError("Informe ao menos um número de oceano.")
            if not self.project.river_boundaries:
                raise ValueError("Informe ao menos um número de rio.")
            if not self.project.boundary_filename:
                raise ValueError("Informe o nome do arquivo PRN.")
            self.run(
                self.workflow_service.series(self.project),
                self.after_series_generated,
            )
        except Exception as exc:
            self.error(exc)

    def after_series_generated(self):
        self.validate_outputs()
        image = (
            self.project.resolve_output(self.project.series_output)
            / f"{Path(self.project.boundary_filename).stem}_conferencia.png"
        )
        if image.is_file():
            self.show_series_popup(image)

    def validate_outputs(self):
        self.ui_to_project()
        grid = self.project.resolve_output(self.project.grid_output)
        contours = self.project.contours_dir
        series = self.project.resolve_output(self.project.series_output)
        paths = {
            "SELAFIN": grid / "geo_CEBSM.slf",
            "CLI configurado": contours / "geo_CEBSM_configurado.cli",
            "PRN": series / self.project.boundary_filename,
            "Figura da grade": grid / "grade_CEBSM_batimetria.png",
            "Figura das séries": (
                series
                / f"{Path(self.project.boundary_filename).stem}_conferencia.png"
            ),
        }
        lines = []
        for name, path in paths.items():
            lines.append(f"{'OK' if path.is_file() else 'FALTA'} — {name}: {path}")
        cli_summary = summarize_cli(paths["CLI configurado"])
        if cli_summary:
            lines.append("\nResumo CLI:")
            lines.extend(f"  {k}: {v}" for k, v in cli_summary.items())
        errors = validate_prn(paths["PRN"])
        lines.append("\nPRN: " + ("válido" if not errors else "com problemas"))
        lines.extend(f"  - {error}" for error in errors)
        self.validation_text.setPlainText("\n".join(lines))
        if hasattr(self, "side_panels") and "Validação" in self.side_panels:
            button, _ = self.side_panels["Validação"]
            button.setChecked(True)
            self.toggle_stfm_panel("Validação")

    def error(self, exc):
        self.log.appendPlainText(f"ERRO: {exc}")
        QMessageBox.critical(self, "Erro", str(exc))


def create_window():
    return MainWindow()
