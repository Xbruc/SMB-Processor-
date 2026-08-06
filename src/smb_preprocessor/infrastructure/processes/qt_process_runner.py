import locale

from PySide6.QtCore import QObject, QProcess, Signal


class ProcessRunner(QObject):
    """Adaptador único de QProcess para todos os fluxos da aplicação."""

    output_received = Signal(str)
    finished = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.output = ""

    @property
    def running(self) -> bool:
        return self.process.state() != QProcess.NotRunning

    def start(self, command) -> bool:
        if self.running:
            return False
        program, args, cwd = command
        self.output = ""
        self.process.setWorkingDirectory(str(cwd))
        self.process.start(program, args)
        return True

    def _read_output(self):
        text = bytes(self.process.readAllStandardOutput()).decode(
            locale.getpreferredencoding(False), errors="replace"
        )
        self.output += text
        self.output_received.emit(text)

    def _finished(self, code, status):
        self.finished.emit(code, self.output)
