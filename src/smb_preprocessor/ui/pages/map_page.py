from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..map_widget import MapWidget


class MapPage(QWidget):
    """Mapa central e ações de domínio, sem regras de processamento."""

    def __init__(
        self,
        load_contour,
        load_grid,
        clear_layers,
        use_domain,
        use_refinement,
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header_widget = QWidget()
        header_widget.setObjectName("mapHeader")
        header = QHBoxLayout(header_widget)
        header.setContentsMargins(16, 10, 16, 10)
        header.addStretch()
        actions = [
            ("Carregar contorno", load_contour, "load-contour.svg"),
            ("Carregar grade", load_grid, "load-grid.svg"),
            ("Remover camadas", clear_layers, "remove-layers.svg"),
            ("Usar como domínio", use_domain, "domain.svg"),
            ("Usar como refinamento", use_refinement, "refinement.svg"),
        ]
        icon_dir = Path(__file__).resolve().parents[2] / "assets" / "icons"
        for label, callback, icon in actions:
            button = QPushButton(label)
            button.setObjectName("mapActionButton")
            button.setIcon(QIcon(str(icon_dir / icon)))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(callback)
            header.addWidget(button)
        layout.addWidget(header_widget)
        self.map_widget = MapWidget()
        layout.addWidget(self.map_widget, 1)
        note = QLabel(
            "Use a ferramenta de polígono no canto superior esquerdo. O último "
            "polígono desenhado pode ser usado como domínio ou área de refinamento."
        )
        note.setObjectName("mutedText")
        note.setContentsMargins(14, 8, 14, 8)
        note.setWordWrap(True)
        layout.addWidget(note)
