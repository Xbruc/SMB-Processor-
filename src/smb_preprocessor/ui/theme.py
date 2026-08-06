"""Visual system for the SMB Processor desktop interface.

Keeping the stylesheet separate makes the UI easier to evolve without mixing
visual decisions with the scientific workflow callbacks.
"""

APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0b1118;
    color: #f3f7fa;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QLabel, QCheckBox, QRadioButton {
    background-color: transparent;
}
QToolBar#appHeader {
    background: #0d1620;
    border: none;
    border-bottom: 1px solid #243342;
    spacing: 6px;
    padding: 0 14px;
}
QToolBar#appHeader QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: #c7d2dc;
    min-height: 30px;
    padding: 2px 10px;
}
QToolBar#appHeader QToolButton:hover,
QToolBar#appHeader QToolButton:pressed {
    background: #172330;
    border-color: #2a3c4c;
    color: #ffffff;
}
QMenu {
    background: #121d28;
    border: 1px solid #2a3c4c;
    border-radius: 7px;
    padding: 6px;
}
QMenu::item { padding: 8px 30px 8px 12px; border-radius: 4px; }
QMenu::item:selected { background: #1b3440; color: #56d6d0; }
QLabel#brandMark { color: #56d6d0; font-size: 16px; font-weight: 800; }
QLabel#brandName { color: #f3f7fa; font-size: 15px; font-weight: 600; }
QLabel#projectStatus {
    color: #55d99b;
    background: #102c25;
    border: 1px solid #205542;
    border-radius: 12px;
    padding: 4px 10px;
}
QWidget#sidebar { background: #0d1721; border-right: 1px solid #243342; }
QToolButton#navButton {
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    color: #8fa3b5;
    padding: 8px 3px;
    text-align: center;
}
QToolButton#navButton:hover { background: #13232e; color: #f3f7fa; }
QToolButton#navButton:checked {
    background: #142a35;
    border-left-color: #22c7c0;
    color: #66e0da;
}
QWidget#panelContainer { background: #101a24; border-right: 1px solid #263646; }
QLabel#panelTitle { color: #f3f7fa; font-size: 20px; font-weight: 650; }
QLabel#panelEyebrow {
    color: #56d6d0;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#sectionTitle { color: #f3f7fa; font-size: 15px; font-weight: 650; }
QLabel#mutedText { color: #8fa3b5; }
QFrame#separator { background: #263646; border: none; max-height: 1px; }
QGroupBox {
    background: #121e29;
    border: 1px solid #263a4b;
    border-radius: 8px;
    margin-top: 18px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #dce6ed;
}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #0c151e;
    border: 1px solid #2a3d4e;
    border-radius: 6px;
    color: #eef5f8;
    min-height: 24px;
    padding: 5px 8px;
    selection-background-color: #168e8b;
}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover,
QDoubleSpinBox:hover, QComboBox:hover { border-color: #40596c; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #22bdb7; }
QLineEdit:read-only { color: #8fa3b5; background: #101923; }
QCheckBox { spacing: 8px; color: #c7d2dc; }
QCheckBox::indicator { width: 17px; height: 17px; }
QPushButton {
    background: #1a2936;
    border: 1px solid #32485a;
    border-radius: 6px;
    color: #dce6ed;
    min-height: 28px;
    padding: 5px 12px;
}
QPushButton:hover { background: #223746; border-color: #456276; color: white; }
QPushButton:pressed { background: #13232e; }
QPushButton:disabled { color: #596b79; background: #121b24; border-color: #202e3a; }
QPushButton#primaryButton {
    background: #16aaa5;
    border-color: #22c7c0;
    color: #061719;
    font-weight: 700;
}
QPushButton#primaryButton:hover { background: #24c2bc; border-color: #56d6d0; }
QPushButton#primaryButton { min-height: 34px; }
QPushButton#quietButton { background: transparent; border-color: #2a3d4e; }
QWidget#mapHeader { background: #101a24; border-bottom: 1px solid #263646; }
QPushButton#mapActionButton {
    background: #172633;
    border: 1px solid #304657;
    border-radius: 6px;
    color: #e6eef4;
    min-height: 32px;
    padding: 4px 13px;
}
QPushButton#mapActionButton:hover {
    background: #1d3442;
    border-color: #3f6374;
    color: #ffffff;
}
QPushButton#mapActionButton:pressed { background: #10222d; }
QWidget#consolePanel { background: #0d1721; border-top: 1px solid #263646; }
QLabel#consoleTitle { color: #dce6ed; font-weight: 650; }
QLabel#consoleStatus {
    color: #55d99b;
    background: #102c25;
    border: 1px solid #205542;
    border-radius: 10px;
    padding: 2px 9px;
}
QPlainTextEdit#processLog {
    background: #091119;
    border: 1px solid #1f303e;
    border-radius: 5px;
    color: #9fb3c2;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}
QSplitter::handle { background: #263646; }
QSplitter::handle:vertical { height: 1px; }
QToolTip {
    background: #172330;
    color: #f3f7fa;
    border: 1px solid #32485a;
    padding: 5px;
}
"""
