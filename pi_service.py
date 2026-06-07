"""
라즈베리파이 서비스 — 책 모드 카메라 감지 + 아두이노 부저 + UDP 수신.

실행:
  export BUZZER_SERIAL_PORT=/dev/ttyUSB0
  python pi_service.py
"""
from __future__ import annotations

import atexit
import sys
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.buzzer_controller import get_buzzer_controller
from src.camera_focus_monitor import get_camera_monitor
from src.device_config import pi_service_port

app = Flask(__name__)

_buzzer = get_buzzer_controller()
_monitor = get_camera_monitor()
_distract_watcher_stop = threading.Event()
_distract_thread = None
_was_focused = True


def _attach_buzzer(status: dict) -> dict:
    status.update(_buzzer.get_status())
    return status


def _distract_watcher_loop() -> None:
    global _was_focused
    while not _distract_watcher_stop.is_set():
        status = _monitor.get_status()
        focused = bool(status.get("focused"))
        running = bool(status.get("running"))

        if running and _was_focused and not focused:
            _buzzer.trigger()

        if running:
            _was_focused = focused
        else:
            _was_focused = True

        time.sleep(0.5)


def _start_distract_watcher() -> None:
    global _distract_thread
    if _distract_thread is not None and _distract_thread.is_alive():
        return
    _distract_watcher_stop.clear()
    _distract_thread = threading.Thread(
        target=_distract_watcher_loop,
        name="PiDistractWatcher",
        daemon=True,
    )
    _distract_thread.start()


@atexit.register
def _shutdown() -> None:
    _distract_watcher_stop.set()
    _monitor.stop()
    _buzzer.stop()


@app.route("/api/status")
def api_status():
    return jsonify(_attach_buzzer(_monitor.get_status()))


@app.route("/api/buzzer/status")
def api_buzzer_status():
    return jsonify(_buzzer.get_status())


@app.route("/api/monitor/start", methods=["POST"])
def api_monitor_start():
    if not _monitor.is_running():
        _monitor.start()
    _start_distract_watcher()
    return jsonify(_attach_buzzer(_monitor.get_status()))


@app.route("/api/monitor/pause", methods=["POST"])
def api_monitor_pause():
    if hasattr(_monitor, "pause"):
        _monitor.pause()
    else:
        _monitor.stop()
    return jsonify(_attach_buzzer(_monitor.get_status()))


@app.route("/api/monitor/reset", methods=["POST"])
def api_monitor_reset():
    if hasattr(_monitor, "pause"):
        _monitor.pause()
    else:
        _monitor.stop()
    _monitor.reset()
    return jsonify(_attach_buzzer(_monitor.get_status()))


@app.route("/api/camera/frame")
def api_camera_frame():
    _monitor.ensure_preview()
    return Response(
        _monitor.stream_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    _start_distract_watcher()
    app.run(debug=False, host="0.0.0.0", port=pi_service_port())
