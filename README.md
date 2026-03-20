# Algae Biosensor - AS7341 Spectrophotometer Monitor

A real-time algae health monitoring application using the **AS7341 11-channel spectrophotometer** sensor. This project captures spectral light intensity measurements across 8 spectral bands (415nm to 680nm) plus a clear channel, processes them into biophysical indices, and provides an interactive GUI for live monitoring, baseline management, and data recording.

## Overview

This application is designed to monitor algae health and stress levels in real-time by analyzing spectral characteristics of light reflectance. It connects to an Arduino-compatible device running AS7341 sensor firmware and displays:

- **Real-time metrics** for chlorophyll content and stress indicators
- **Live visualization** of spectral color swatches and historical data
- **Baseline capture** for healthy algae reference measurements
- **Timed recordings** with automatic data logging to CSV files
- **Historical analysis** through an integrated records viewer

## Key Features

- **AS7341 Serial Integration**: USB/serial connection to sensor with real-time packet parsing
- **Biophysical Indices Calculation**:
  - Chlorophyll Index: F8(680nm) / F2(445nm)
  - CAR:CHL Ratio: F3(480nm) / F8(680nm)  
  - Yellow Index: F6(590nm) / F3(480nm)
  - Stress Ratio: (F5+F6) / (F2+F8) normalized by Clear channel
- **Health Status Assessment**: Automated status classification (Healthy, Warning, Stressed) based on delta from baseline
- **Live Recording**: Capture snapshot data at configurable intervals (default 30s)
- **Data Persistence**: CSV storage with session management and naming
- **Multi-tab Interface**: Live monitoring and historical records tabs with PySide6 GUI

## Project Structure

```
color_sensor/
├── main.py                 # Application entry point
├── ui.py                   # Main window and tab management
├── config.py               # Configuration constants
├── serial_reader.py        # AS7341 serial communication handler
├── models.py               # Data models and channel definitions
├── metrics.py              # Biophysical index calculations
├── color_utils.py          # Color space conversions (RGB/HEX)
├── services.py             # Business logic and data processing
├── storage.py              # CSV I/O and session management
├── session_controller.py    # Recording/baseline state management
├── tabs/                   # UI tab components
│   ├── live_tab.py         # Real-time monitoring interface
│   └── records_tab.py      # Historical data browser
├── widgets/                # Reusable UI components
│   ├── metric_card.py      # Metric display cards
│   ├── history_table.py    # Data table widget
│   └── title_bar.py        # Custom title bar
└── records_as7341_algae.csv # Data storage file
```

## Requirements

- Python 3.8+
- PySerial for hardware communication
- PySide6 for GUI
- NumPy/Pandas for data processing
- PyQtGraph for visualization

## Installation & Usage

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the application:
```bash
python main.py
```

1. **Connect sensor** via USB and select COM port
2. **Capture baseline** from healthy algae sample
3. **Start recording** to monitor changes over time
4. **View records** tab to analyze historical trends
