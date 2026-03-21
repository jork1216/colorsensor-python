# Baud rate for serial communication with the sensor
SERIAL_BAUD = 115200

# Delay in seconds to flush serial buffer
SERIAL_FLUSH_SECONDS = 0.6

# Sleep duration in seconds when establishing serial connection
SERIAL_CONNECT_SLEEP = 2.0

# Time interval in seconds between sensor snapshot readings
SNAPSHOT_INTERVAL_SECONDS = 30

# Maximum number of data points to keep in live view history
LIVE_HISTORY_LIMIT = 100

# Maximum number of points to buffer before storage operations
MAX_BUFFER_POINTS = 800

# Default duration in seconds for automated recordings
DEFAULT_RECORDING_DURATION = 30

# UI refresh interval in milliseconds for timer events
UI_TIMER_INTERVAL_MS = 80

# File path for storing algae biosensor records
CSV_PATH = "records_as7341_algae.csv"

# File path for persisting app settings (e.g. last used serial port)
SETTINGS_PATH = "app_settings.json"
