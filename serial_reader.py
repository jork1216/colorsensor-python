import time
import json

import serial
import serial.tools.list_ports

from PySide6.QtCore import QThread, Signal

from models import JSON_ALIAS_TO_AS, AS_COLS, KV_PATTERN


class SerialReader(QThread):
    packet = Signal(dict)
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False
        self._pending = {}

    def list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect_port(self, port, baud=115200):
        self.disconnect_port()
        try:
            self._ser = serial.Serial(port, baud, timeout=0.2)
            time.sleep(2.0)
            self.flush_buffer(0.5)
            self.clear_pending()
            self.status.emit(f"Connected: {port} @ {baud}")
            return True
        except Exception as e:
            self._ser = None
            self.status.emit(f"Connect error: {e}")
            return False

    def disconnect_port(self):
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None
        self._pending = {}
        self.status.emit("Disconnected")

    def clear_pending(self):
        self._pending.clear()

    def _coerce_as7341_packet(self, obj: dict) -> dict | None:
        if not isinstance(obj, dict) or not obj:
            return None

        pkt = {}
        for raw_key, value in obj.items():
            key = str(raw_key).strip()
            mapped = JSON_ALIAS_TO_AS.get(key, key)
            if mapped not in AS_COLS:
                continue
            try:
                pkt[mapped] = int(value)
            except Exception:
                try:
                    pkt[mapped] = int(float(value))
                except Exception:
                    continue

        if not pkt:
            return None
        return pkt

    def flush_buffer(self, seconds=0.6):
        if not self._ser:
            return
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass

        t0 = time.time()
        while time.time() - t0 < seconds:
            try:
                while self._ser.in_waiting > 0:
                    self._ser.readline()
            except Exception:
                break
            time.sleep(0.01)

    def run(self):
        self._running = True
        while self._running:
            if not self._ser:
                time.sleep(0.05)
                continue

            try:
                while self._ser.in_waiting > 0:
                    line = self._ser.readline().decode(errors="ignore").strip()
                    if not line:
                        continue
                    if "OK=" in line or "ERR=" in line:
                        continue

                    if line.startswith("{") and line.endswith("}"):
                        try:
                            parsed = json.loads(line)
                            pkt = self._coerce_as7341_packet(parsed)
                            if pkt:
                                for k, v in pkt.items():
                                    self._pending[k] = v
                        except Exception:
                            pass
                    else:
                        for k, v in KV_PATTERN.findall(line):
                            self._pending[k] = int(v)

                    if all(k in self._pending for k in AS_COLS):
                        pkt = {k: self._pending[k] for k in AS_COLS}
                        self._pending.clear()
                        self.packet.emit(pkt)

            except Exception as e:
                self.status.emit(f"Serial read error: {e}")
                time.sleep(0.2)

            time.sleep(0.005)

    def stop(self):
        self._running = False
        self.wait(800)
        self.disconnect_port()
