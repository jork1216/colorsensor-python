import json

from PySide6.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
)

from config import CSV_PATH, UI_TIMER_INTERVAL_MS, SETTINGS_PATH
from models import AppState
from storage import ensure_csv_schema
from serial_reader import SerialReader
from session_controller import SessionController
from metrics import compute_all_indices
from widgets.title_bar import TitleBar
from tabs.live_tab import LiveTab
from tabs.records_tab import RecordsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1200, 800)
        self.setMinimumSize(900,700)

        self.setWindowTitle("Real-Time Algae Biosensor")
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.state = AppState()
        
        # Restore baseline from app_settings.json if it exists
        try:
            with open(SETTINGS_PATH, "r") as f:
                settings = json.load(f)
                if "baseline_pkt" in settings and "baseline_time" in settings:
                    from datetime import datetime
                    self.state.baseline_pkt = settings["baseline_pkt"]
                    self.state.baseline_time = datetime.fromisoformat(settings["baseline_time"])
                    self.state.baseline_indices = compute_all_indices(self.state.baseline_pkt)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        ensure_csv_schema(CSV_PATH)

        self.reader = SerialReader()
        self.controller = SessionController(state=self.state, reader=self.reader)
        self.reader.packet.connect(self.controller.on_packet)
        self.reader.status.connect(self.on_status)

        try:
            self.reader.start()
        except Exception:
            self.reader.stop()
            raise

        self.drag_pos = None
        self._animations = []

        self.setup_ui()
        self.setup_animations()

        self.live_tab = LiveTab(state=self.state, reader=self.reader, controller=self.controller, refresh_sessions_callback=None)
        self.records_tab = RecordsTab()
        self.live_tab.refresh_sessions_callback = self.records_tab.refresh_sessions
        self.tabs.addTab(self.live_tab, "Live / Record")
        self.tabs.addTab(self.records_tab, "Past Records")

        self.controller.recording_started.connect(self.live_tab.on_recording_started)
        self.controller.recording_stopped.connect(self.live_tab.on_recording_stopped)
        self.controller.tick.connect(self.live_tab.on_tick)
        self.controller.snapshot_ready.connect(self.live_tab.on_snapshot_ready)
        self.controller.packet_evaluated.connect(self.live_tab.on_packet_evaluated)
        self.controller.baseline_captured.connect(self.live_tab.on_baseline_captured)
        self.controller.baseline_cleared.connect(self.live_tab.on_baseline_cleared)
        self.reader.disconnected.connect(self.controller.on_serial_disconnected)
        self.controller.recording_aborted.connect(self.on_recording_aborted)

        # Emit baseline_captured signal if baseline was restored
        if self.state.baseline_pkt and self.state.baseline_indices and self.state.baseline_time:
            timestamp_string = self.state.baseline_time.strftime("%Y-%m-%d %H:%M:%S")
            self.controller.baseline_captured.emit(self.state.baseline_indices, timestamp_string)

        self.ui_timer = QTimer()
        self.ui_timer.setInterval(UI_TIMER_INTERVAL_MS)
        self.ui_timer.timeout.connect(self.tick_ui)
        self.ui_timer.start()

        self.live_tab.refresh_ports()
        self.records_tab.refresh_sessions()
        self.animate_window_open()

    def setup_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar(parent_window=self)
        root_layout.addWidget(self.title_bar)

        self.content_wrapper = QWidget()
        self.content_wrapper.setStyleSheet("""
            QWidget {
                background-color: #281C59;
                color: white;
            }
        """)
        content_layout = QVBoxLayout(self.content_wrapper)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #4a3f8a;
                background: #1e1650;
                border-radius: 10px;
            }
            QTabBar::tab {
                background: #0f172a;
                color: white;
                padding: 10px 16px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #3d2f8f;
                color: white;
            }
        """)
        content_layout.addWidget(self.tabs)

        root_layout.addWidget(self.content_wrapper)
        self.setCentralWidget(root)

    def setup_animations(self):
        self.setWindowOpacity(0.0)

    def animate_window_open(self):
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(650)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._animations.append(anim)



    def on_recording_aborted(self, msg: str):
        self.live_tab.on_recording_aborted(msg)

    def on_status(self, msg: str):
        self.live_tab.on_status(msg)

    def tick_ui(self):
        self.live_tab.tick_ui()

    def closeEvent(self, event):
        try:
            self.reader.stop()
        except Exception:
            pass
        event.accept()