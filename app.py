"""
Smart Focus Management System — Flask GUI 진입점
"""
import atexit
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template

# src 패키지 import 경로
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.detect_active_window import ensure_monitor_started, get_default_monitor

app = Flask(__name__)


def _monitor():
    return ensure_monitor_started()


@atexit.register
def _stop_monitor():
    try:
        get_default_monitor().stop()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """대시보드 — 집중도 요약"""
    _monitor()
    return render_template("index.html", page_title="대시보드")


@app.route("/camera")
def camera():
    """카메라 — 시선·얼굴 방향 모니터링"""
    return render_template("camera.html", page_title="카메라 모니터")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    """활성 창 기반 집중도 상태"""
    return jsonify(_monitor().get_status())


@app.route("/api/camera/frame")
def api_camera_frame():
    """카메라 프레임 — MJPEG/이미지 스트림 연동 예정"""
    return jsonify({"available": False, "message": "카메라 스트림 미연결"})


if __name__ == "__main__":
    _monitor()
    app.run(debug=True, host="0.0.0.0", port=5000)
