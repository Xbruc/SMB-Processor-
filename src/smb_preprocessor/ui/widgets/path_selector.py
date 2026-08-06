from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathRow(QWidget):
    """Campo de caminho com seletor de arquivo ou diretório."""

    def __init__(self, directory=False, save=False):
        super().__init__()
        self.directory, self.save = directory, save
        self.edit = QLineEdit()
        self.edit.setMinimumWidth(165)
        self.edit.setPlaceholderText("Selecione um arquivo ou pasta")
        self.edit.textChanged.connect(self.edit.setToolTip)
        button = QPushButton()
        button.setObjectName("mapActionButton")
        button.setIcon(QIcon(str(
            Path(__file__).resolve().parents[2] / "assets" / "icons" / "browse.svg"
        )))
        button.setIconSize(QSize(17, 17))
        button.setFixedWidth(38)
        button.setToolTip("Selecionar arquivo ou pasta")
        button.clicked.connect(self.choose)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def choose(self):
        current = self.edit.text() or str(Path.home())
        if self.directory:
            value = QFileDialog.getExistingDirectory(self, "Selecionar pasta", current)
        elif self.save:
            value, _ = QFileDialog.getSaveFileName(
                self, "Salvar arquivo", current, "JSON (*.json)"
            )
        else:
            value, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", current)
        if value:
            self.edit.setText(value)

    def text(self):
        return self.edit.text().strip()

    def setText(self, value):
        self.edit.setText(str(value))
