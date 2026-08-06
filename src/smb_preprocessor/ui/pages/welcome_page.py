from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class WelcomePage(QWidget):
    """Tela inicial responsiva do SMB Processor."""

    def __init__(self, create_project, open_project, parent=None):
        super().__init__(parent)
        self.setObjectName("welcomePage")
        image_path = (
            Path(__file__).resolve().parents[2]
            / "assets" / "branding" / "smb_processor_welcome.png"
        )
        self.background = QPixmap(str(image_path))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(7)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        create_button = QPushButton("＋  Criar novo projeto")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(create_project)
        open_button = QPushButton("Abrir projeto existente")
        open_button.setObjectName("quietButton")
        open_button.clicked.connect(open_project)
        actions.insertStretch(0, 1)
        actions.addWidget(create_button)
        actions.addWidget(open_button)
        actions.addStretch(3)
        outer.addLayout(actions)
        outer.addStretch(2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.background.isNull():
            painter.fillRect(self.rect(), Qt.black)
            return
        source_width = self.background.width()
        source_height = self.background.height()
        target_ratio = self.width() / max(self.height(), 1)
        source_ratio = source_width / source_height
        if source_ratio > target_ratio:
            crop_width = int(source_height * target_ratio)
            source = QRect(
                (source_width - crop_width) // 2, 0, crop_width, source_height
            )
        else:
            crop_height = int(source_width / target_ratio)
            source = QRect(
                0, (source_height - crop_height) // 2, source_width, crop_height
            )
        painter.drawPixmap(self.rect(), self.background, source)
