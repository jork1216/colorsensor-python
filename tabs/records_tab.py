import numpy as np
import pandas as pd
import pyqtgraph as pg

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QMessageBox,
    QFileDialog,
)

from models import CSV_PATH
from storage import load_records_df
from widgets.history_table import HistoryTable


class RecordsTab(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        root.addLayout(top)

        self.session_combo = QComboBox()
        self.btn_refresh_sessions = QPushButton("Refresh Sessions")
        self.btn_delete_session = QPushButton("Delete Session")
        self.btn_export = QPushButton("Export Excel…")

        top.addWidget(QLabel("Session:"))
        top.addWidget(self.session_combo, 4)
        top.addWidget(self.btn_refresh_sessions)
        top.addWidget(self.btn_delete_session)
        top.addWidget(self.btn_export)

        self.btn_refresh_sessions.clicked.connect(self.refresh_sessions)
        self.session_combo.currentIndexChanged.connect(self.load_selected_session_plot)
        self.btn_delete_session.clicked.connect(self.delete_selected_session)
        self.btn_export.clicked.connect(self.export_selected_session)

        self.session_info = QLabel("—")
        self.session_info.setStyleSheet("color: white;")
        root.addWidget(self.session_info)

        self.session_indices_info = QLabel("—")
        self.session_indices_info.setStyleSheet("color: white; font-weight:600;")
        root.addWidget(self.session_indices_info)

        # Index graph for past records
        self.plot_hist = pg.PlotWidget()
        self.plot_hist.showGrid(x=True, y=True)
        self.plot_hist.setLabel("left", "Index Value")
        self.plot_hist.setLabel("bottom", "Samples (session)")
        self.plot_hist.setBackground("#1e1650")
        root.addWidget(self.plot_hist, 1)

        self.hist_legend = self._make_legend(self.plot_hist)

        self.curves_hist = {}
        index_cfg = {
            "chlorophyll_index": ("Chlorophyll Index", "#10b981"),
            "car_chl_ratio": ("Car:Chl Ratio", "#3b82f6"),
            "yellow_index": ("Yellow Index", "#f59e0b"),
            "stress_ratio": ("Stress Ratio", "#ef4444"),
        }

        for key, (label, color) in index_cfg.items():
            pen = pg.mkPen(color=color, width=3)
            curve = pg.PlotDataItem([], [], pen=pen)
            self.plot_hist.addItem(curve)
            self.curves_hist[key] = curve
            self.hist_legend.addItem(curve, self._colored_label(label, color))

        records_header = QHBoxLayout()
        root.addLayout(records_header)

        records_title = QLabel("📋  Session History")
        records_title.setStyleSheet("font-size:18px;font-weight:800;color:white;")
        self.records_history_count = QLabel("0 snaps recorded")
        self.records_history_count.setStyleSheet("color:#c4b5fd;font-weight:600;")

        records_header.addWidget(records_title)
        records_header.addStretch()
        records_header.addWidget(self.records_history_count)

        self.records_history_table = HistoryTable()
        self.records_history_table.setMinimumHeight(180)
        root.addWidget(self.records_history_table, 1)

    def _make_legend(self, plot_widget: pg.PlotWidget):
        leg = plot_widget.addLegend(offset=(10, 10))
        if leg is None:
            leg = pg.LegendItem(offset=(10, 10))
            leg.setParentItem(plot_widget.getPlotItem())
        return leg

    def _colored_label(self, text: str, color_hex: str) -> str:
        return f'<span style="color:{color_hex}; font-weight:700;">{text}</span>'

    def refresh_sessions(self):
        df = load_records_df(CSV_PATH)
        if df.empty:
            self.session_combo.clear()
            self.session_combo.addItem("No sessions")
            self.session_info.setText("—")
            self.session_indices_info.setText("—")
            self.clear_hist_plot()
            self.records_history_table.setRowCount(0)
            self.records_history_count.setText("0 snaps recorded")
            return

        sessions = (
            df.groupby("session_id")
            .agg(
                start=("time", "min"),
                end=("time", "max"),
                count=("time", "count"),
                session_name=("session_name", "last"),
                overall_status=("overall_status", "last"),
            )
            .sort_values("end", ascending=False)
            .reset_index()
        )

        def label_row(r):
            nm = str(r["session_name"]).strip()
            status = str(r["overall_status"]).strip()
            if not nm:
                nm = "Unnamed"
            return f"{nm} [{status}] ({r['end']:%Y-%m-%d %I:%M %p})"

        self._sessions_df = sessions
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        for _, r in sessions.iterrows():
            self.session_combo.addItem(label_row(r), userData=str(r["session_id"]))
        self.session_combo.blockSignals(False)

        self.load_selected_session_plot()

    def clear_hist_plot(self):
        for key in self.curves_hist:
            self.curves_hist[key].setData([], [])

    def load_selected_session_plot(self):
        sid = self.session_combo.currentData()
        if not sid or str(sid).lower().startswith("no sessions"):
            self.session_info.setText("—")
            self.session_indices_info.setText("—")
            self.clear_hist_plot()
            self.records_history_table.setRowCount(0)
            self.records_history_count.setText("0 snaps recorded")
            return

        df = load_records_df(CSV_PATH)
        sdf = df[df["session_id"].astype(str) == str(sid)].sort_values("time").copy()
        if sdf.empty:
            self.session_info.setText("Session empty.")
            self.session_indices_info.setText("—")
            self.clear_hist_plot()
            self.records_history_table.setRowCount(0)
            self.records_history_count.setText("0 snaps recorded")
            return

        start = sdf["time"].iloc[0]
        end = sdf["time"].iloc[-1]
        count = len(sdf)
        name = str(sdf["session_name"].iloc[-1]).strip() or "Unnamed"
        overall = str(sdf["overall_status"].iloc[-1]).strip() or "—"

        self.session_info.setText(
            f"Session: {name} | {start:%Y-%m-%d %I:%M:%S %p} → {end:%I:%M:%S %p} | "
            f"Samples: {count} | Overall: {overall} | ID: {sid}"
        )

        try:
            last = sdf.iloc[-1]
            self.session_indices_info.setText(
                f"Chl={float(last['chlorophyll_index']):.4f} "
                f"(Δ {float(last['chlorophyll_index_delta_pct']):.2f}% | {last['chlorophyll_index_status']})   |   "
                f"Car:Chl={float(last['car_chl_ratio']):.4f} "
                f"(Δ {float(last['car_chl_ratio_delta_pct']):.2f}% | {last['car_chl_ratio_status']})   |   "
                f"Yellow={float(last['yellow_index']):.4f} "
                f"(Δ {float(last['yellow_index_delta_pct']):.2f}% | {last['yellow_index_status']})   |   "
                f"Stress={float(last['stress_ratio']):.4f} "
                f"(Δ {float(last['stress_ratio_delta_pct']):.2f}% | {last['stress_ratio_status']})"
            )
        except Exception:
            self.session_indices_info.setText("Index summary unavailable.")

        x = np.arange(count)

        for key in self.curves_hist:
            if key in sdf.columns:
                y = pd.to_numeric(sdf[key], errors="coerce").to_numpy()
                self.curves_hist[key].setData(x, y)
            else:
                self.curves_hist[key].setData([], [])

        self.records_history_table.populate_records_history_table(sdf, self.records_history_count)

    def delete_selected_session(self):
        sid = self.session_combo.currentData()
        if not sid:
            return

        reply = QMessageBox.question(
            self,
            "Delete Session",
            "Delete this entire session from the CSV? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        df = load_records_df(CSV_PATH)
        new_df = df[df["session_id"].astype(str) != str(sid)].copy()
        new_df2 = new_df.copy()
        new_df2["time"] = new_df2["time"].dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        new_df2.to_csv(CSV_PATH, index=False)

        self.refresh_sessions()

    def export_selected_session(self):
        # Get selected session ID
        sid = self.session_combo.currentData()
        if not sid:
            return

        # Load and filter DataFrame to this session
        df = load_records_df(CSV_PATH)
        sdf = df[df["session_id"].astype(str) == str(sid)].sort_values("time").copy()
        if sdf.empty:
            QMessageBox.critical(self, "Error", "Session has no data.")
            return

        # Open save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Session", "", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            # Prepare data for sheets
            index_cols = [
                "chlorophyll_index",
                "chlorophyll_index_delta_pct",
                "car_chl_ratio",
                "car_chl_ratio_delta_pct",
                "yellow_index",
                "yellow_index_delta_pct",
                "stress_ratio",
                "stress_ratio_delta_pct",
            ]
            session_data_cols = ["time"] + index_cols + ["overall_status"]
            session_data = sdf[session_data_cols].copy()

            # Prepare summary data (first and last rows)
            first_row = sdf[session_data_cols].iloc[0].copy()
            last_row = sdf[session_data_cols].iloc[-1].copy()

            summary_data = pd.DataFrame(
                [
                    {"type": "Baseline", **first_row.to_dict()},
                    {"type": "Final", **last_row.to_dict()},
                ]
            )

            # Write Excel file with two sheets
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                session_data.to_excel(writer, sheet_name="Session Data", index=False)
                summary_data.to_excel(writer, sheet_name="Summary", index=False)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Session exported successfully to:\n{file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Export Failed", f"Failed to export session:\n{str(e)}"
            )

