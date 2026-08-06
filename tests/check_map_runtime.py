from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from smb_preprocessor.ui.map_widget import MapWidget


app = QApplication([])
widget = MapWidget()


def loaded(ok):
    print(f"pagina={ok}")
    widget.page().runJavaScript(
        'typeof L + "/" + typeof window.getDrawings',
        0,
        lambda value: (print(f"javascript={value}"), app.quit()),
    )


widget.loadFinished.connect(loaded)
QTimer.singleShot(20000, lambda: (print("timeout"), app.quit()))
app.exec()
