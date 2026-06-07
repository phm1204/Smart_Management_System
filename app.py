"""
Smart Focus Management System — Flask GUI 진입점 (PC)
"""
import atexit
import sys
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template, request, redirect, url_for, session

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.camera_focus_monitor import get_camera_monitor
from src.computer_buzzer_watcher import get_computer_buzzer_watcher
from src.detect_active_window import SPECIAL_DISTRACT_OPTIONS, get_default_monitor
from src.device_config import use_pi_for_book
from src.pi_client import PiClientError, merge_buzzer_status, pi_available, pi_get, pi_post, pi_stream

app = Flask(__name__)
app.secret_key = "smart_focus_secret_key_2026"

STUDY_METHODS = {
    "pomodoro": {"name": "뽀모도로 기법", "duration": 25, "break_duration": 5, "description": "25분 공부 + 5분 휴식"},
    "short": {"name": "짧은 집중", "duration": 15, "break_duration": 3, "description": "15분 공부 + 3분 휴식"},
    "long": {"name": "긴 집중", "duration": 50, "break_duration": 10, "description": "50분 공부 + 10분 휴식"},
    "free": {"name": "자유형", "duration": None, "break_duration": None, "description": "시간 제한 없음"},
}


def _learning_type() -> str:
    return session.get("learning_type", "computer")


def _book_on_pi() -> bool:
    return _learning_type() == "book" and use_pi_for_book()


def _monitor_for_learning_type(learning_type: str):
    if learning_type == "book" and not use_pi_for_book():
        return get_camera_monitor()
    return get_default_monitor()


def _session_monitor():
    return _monitor_for_learning_type(_learning_type())


def _get_user_prefs():
    return {
        "messenger_mode": session.get("messenger_mode", "focus"),
        "special_distract_options": session.get("special_distract_options", []),
    }


def _apply_focus_preferences():
    prefs = _get_user_prefs()
    monitor = get_default_monitor()
    monitor.configure_preferences(
        messenger_mode=prefs["messenger_mode"],
        special_options=prefs["special_distract_options"],
    )


def _local_monitor_status(monitor) -> dict:
    status = monitor.get_status()
    status["learning_type"] = _learning_type()
    return merge_buzzer_status(status)


def _fetch_session_status() -> dict:
    if _book_on_pi():
        status = pi_get("/api/status")
        status["learning_type"] = "book"
        return status

    _apply_focus_preferences()
    monitor = _session_monitor()
    return _local_monitor_status(monitor)


def _control_session_monitor(action: str) -> dict:
    if _book_on_pi():
        if action == "pause":
            _append_study_record("일시정지")
        elif action == "reset":
            _append_study_record("초기화")
        return pi_post(f"/api/monitor/{action}")

    monitor = _session_monitor()
    if action == "start":
        if not monitor.is_running():
            monitor.start()
    elif action == "pause":
        _append_study_record("일시정지")
        if hasattr(monitor, "pause"):
            monitor.pause()
        else:
            monitor.stop()
    elif action == "reset":
        _append_study_record("초기화")
        if hasattr(monitor, "pause"):
            monitor.pause()
        else:
            monitor.stop()
        monitor.reset()
    return _local_monitor_status(monitor)


def _reset_pi_monitor() -> None:
    if not pi_available():
        return
    try:
        pi_post("/api/monitor/reset")
    except PiClientError:
        pass


def _append_study_record(reason: str):
    try:
        status = _fetch_session_status()
    except PiClientError:
        return

    total = int(status.get("focus_time_sec", 0)) + int(status.get("distract_time_sec", 0))
    if total <= 0:
        return

    records = session.get("study_records", [])
    records.insert(
        0,
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "learning_type": _learning_type(),
            "study_method": session.get("study_method", "pomodoro"),
            "focus_time_sec": int(status.get("focus_time_sec", 0)),
            "distract_time_sec": int(status.get("distract_time_sec", 0)),
            "focus_score": int(status.get("focus_score", 0)),
            "reason": reason,
        },
    )
    session["study_records"] = records[:30]


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


def _computer_monitor_status() -> dict:
    _apply_focus_preferences()
    return get_default_monitor().get_status()


get_computer_buzzer_watcher(
    get_monitor_status=_computer_monitor_status,
    is_computer_mode=lambda: True,
)


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    study_method = session.get("study_method", "pomodoro")
    method_info = STUDY_METHODS.get(study_method, STUDY_METHODS["pomodoro"])
    learning_type = _learning_type()
    _apply_focus_preferences()

    return render_template(
        "index.html",
        page_title="대시보드",
        method_info=method_info,
        study_method=study_method,
        learning_type=learning_type,
        pi_connected=pi_available(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:
            session["user_id"] = username
            return redirect(url_for("select_learning_type"))

    return render_template("login.html")


@app.route("/select-learning-type", methods=["GET", "POST"])
def select_learning_type():
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
            _reset_pi_monitor()
            return redirect(url_for("select_study_method"))

    return render_template("select_learning_type.html", page_title="학습 매체 선택")


@app.route("/select-study-method", methods=["GET", "POST"])
def select_study_method():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        method = request.form.get("method", "pomodoro")
        if method in STUDY_METHODS:
            session["study_method"] = method
            if _book_on_pi():
                _reset_pi_monitor()
            else:
                monitor = _session_monitor()
                monitor.stop()
                monitor.reset()
            return redirect(url_for("index"))

    learning_type = _learning_type()
    learning_type_name = "책" if learning_type == "book" else "컴퓨터"

    return render_template(
        "study_method.html",
        page_title="공부법 선택",
        methods=STUDY_METHODS,
        learning_type=learning_type,
        learning_type_name=learning_type_name,
    )


@app.route("/camera")
def camera():
    if "user_id" not in session:
        return redirect(url_for("login"))

    study_method = session.get("study_method", "pomodoro")
    method_info = STUDY_METHODS.get(study_method, STUDY_METHODS["pomodoro"])

    return render_template(
        "camera.html",
        page_title="카메라 모니터",
        method_info=method_info,
        study_method=study_method,
    )


@app.route("/mypage", methods=["GET", "POST"])
def mypage():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        messenger_mode = request.form.get("messenger_mode", "focus")
        if messenger_mode not in ["focus", "distract"]:
            messenger_mode = "focus"
        selected_options = request.form.getlist("special_distract_options")
        selected_options = [k for k in selected_options if k in SPECIAL_DISTRACT_OPTIONS]

        session["messenger_mode"] = messenger_mode
        session["special_distract_options"] = selected_options
        _apply_focus_preferences()
        return redirect(url_for("mypage"))

    prefs = _get_user_prefs()
    records = session.get("study_records", [])
    return render_template(
        "mypage.html",
        page_title="내 페이지",
        prefs=prefs,
        records=records,
        special_options=SPECIAL_DISTRACT_OPTIONS,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/status")
def api_status():
    try:
        return jsonify(_fetch_session_status())
    except PiClientError as exc:
        return jsonify({"error": str(exc), "pi_connected": False}), 503


@app.route("/api/monitor/start", methods=["POST"])
def api_monitor_start():
    try:
        return jsonify(_control_session_monitor("start"))
    except PiClientError as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/monitor/pause", methods=["POST"])
def api_monitor_pause():
    try:
        return jsonify(_control_session_monitor("pause"))
    except PiClientError as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/monitor/reset", methods=["POST"])
def api_monitor_reset():
    try:
        return jsonify(_control_session_monitor("reset"))
    except PiClientError as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/camera/frame")
def api_camera_frame():
    if _book_on_pi():
        try:
            upstream = pi_stream("/api/camera/frame")

            def generate():
                with upstream as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=4096):
                        if chunk:
                            yield chunk

            return Response(
                generate(),
                mimetype="multipart/x-mixed-replace; boundary=frame",
            )
        except (PiClientError, requests.RequestException) as exc:
            return Response(f"Pi camera error: {exc}", status=503)

    monitor = get_camera_monitor()
    monitor.ensure_preview()
    return Response(
        monitor.stream_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
