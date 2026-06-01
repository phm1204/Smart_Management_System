"""
Smart Focus Management System — Flask GUI 진입점
"""
import atexit
import sys
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, redirect, url_for, session

# src 패키지 import 경로
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.camera_focus_monitor import get_camera_monitor
from src.detect_active_window import get_default_monitor

app = Flask(__name__)
app.secret_key = "smart_focus_secret_key_2026"

# 공부법 정의
STUDY_METHODS = {
    "pomodoro": {"name": "뽀모도로 기법", "duration": 25, "break_duration": 5, "description": "25분 공부 + 5분 휴식"},
    "short": {"name": "짧은 집중", "duration": 15, "break_duration": 3, "description": "15분 공부 + 3분 휴식"},
    "long": {"name": "긴 집중", "duration": 50, "break_duration": 10, "description": "50분 공부 + 10분 휴식"},
    "free": {"name": "자유형", "duration": None, "break_duration": None, "description": "시간 제한 없음"},
}


def _monitor_for_learning_type(learning_type: str):
    if learning_type == "book":
        return get_camera_monitor()
    return get_default_monitor()


def _session_monitor():
    learning_type = session.get("learning_type", "computer")
    return _monitor_for_learning_type(learning_type)


@atexit.register
def _stop_monitor():
    try:
        get_default_monitor().stop()
    except Exception:
        pass
    try:
        get_camera_monitor().stop()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """대시보드 — 집중도 요약 (로그인 필요)"""
    if "user_id" not in session:
        return redirect(url_for("login"))

    study_method = session.get("study_method", "pomodoro")
    method_info = STUDY_METHODS.get(study_method, STUDY_METHODS["pomodoro"])
    learning_type = session.get("learning_type", "computer")

    return render_template(
        "index.html",
        page_title="대시보드",
        method_info=method_info,
        study_method=study_method,
        learning_type=learning_type,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """로그인 페이지"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:
            session["user_id"] = username
            return redirect(url_for("select_learning_type"))
    
    return render_template("login.html")


@app.route("/select-learning-type", methods=["GET", "POST"])
def select_learning_type():
    """학습 매체 선택 페이지 (책 또는 컴퓨터)"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        learning_type = request.form.get("learning_type", "computer")
        if learning_type in ["book", "computer"]:
            session["learning_type"] = learning_type
            get_default_monitor().stop()
            get_default_monitor().reset()
            get_camera_monitor().stop()
            get_camera_monitor().reset()
            return redirect(url_for("select_study_method"))
    
    return render_template("select_learning_type.html", page_title="학습 매체 선택")


@app.route("/select-study-method", methods=["GET", "POST"])
def select_study_method():
    """공부법 선택 페이지"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        method = request.form.get("method", "pomodoro")
        if method in STUDY_METHODS:
            session["study_method"] = method
            monitor = _session_monitor()
            monitor.stop()
            monitor.reset()
            return redirect(url_for("index"))
    
    learning_type = session.get("learning_type", "computer")
    learning_type_name = "책" if learning_type == "book" else "컴퓨터"
    
    return render_template("study_method.html", page_title="공부법 선택", methods=STUDY_METHODS, learning_type=learning_type, learning_type_name=learning_type_name)


@app.route("/camera")
def camera():
    """카메라 — 시선·얼굴 방향 모니터링 (로그인 필요)"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    study_method = session.get("study_method", "pomodoro")
    method_info = STUDY_METHODS.get(study_method, STUDY_METHODS["pomodoro"])
    
    return render_template("camera.html", page_title="카메라 모니터", method_info=method_info, study_method=study_method)


@app.route("/logout")
def logout():
    """로그아웃"""
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    """학습 매체별 집중도 상태"""
    learning_type = session.get("learning_type", "computer")
    monitor = _monitor_for_learning_type(learning_type)
    status = monitor.get_status()
    status["learning_type"] = learning_type
    return jsonify(status)


@app.route("/api/monitor/start", methods=["POST"])
def api_monitor_start():
    """집중도 측정 시작"""
    monitor = _session_monitor()
    if not monitor.is_running():
        monitor.start()
    return jsonify(monitor.get_status())


@app.route("/api/monitor/pause", methods=["POST"])
def api_monitor_pause():
    """집중도 측정 일시정지"""
    monitor = _session_monitor()
    if hasattr(monitor, "pause"):
        monitor.pause()
    else:
        monitor.stop()
    return jsonify(monitor.get_status())


@app.route("/api/monitor/reset", methods=["POST"])
def api_monitor_reset():
    """집중도 측정값 초기화"""
    monitor = _session_monitor()
    if hasattr(monitor, "pause"):
        monitor.pause()
    else:
        monitor.stop()
    monitor.reset()
    return jsonify(monitor.get_status())


@app.route("/api/camera/frame")
def api_camera_frame():
    """카메라 프레임 MJPEG 스트림"""
    monitor = get_camera_monitor()
    monitor.ensure_preview()
    return Response(
        monitor.stream_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
