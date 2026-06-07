from __future__ import annotations

import threading
import time
from typing import Dict, Optional

import cv2

from src.device_config import (
    camera_analyze_interval,
    camera_face_only,
    camera_height,
    camera_jpeg_quality,
    camera_preview_interval,
    camera_stream_interval,
    camera_width,
)
from src.monitor_base import BaseMonitor
from src.vision.camera_analysis_core import DetectionSmoother, analyze_camera_frame


class CameraFocusMonitor(BaseMonitor):
    """카메라 얼굴/시선으로 집중도를 측정한다."""

    def __init__(self, interval_sec: float = 0.4) -> None:
        self.interval_sec = interval_sec
        self.focus_threshold = 0.5
        self.missing_grace_sec = 10.0
        self.gaze_grace_sec = 5.0

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._preview_thread: Optional[threading.Thread] = None
        self._analysis_thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._measurement_active = False
        self._analyze_interval = camera_analyze_interval()
        self._face_only = camera_face_only()

        self.focused = False
        self.focus_time_sec = 0
        self.distract_time_sec = 0
        self.active_window = ""
        self.message = "카메라 대기 중"

        self.face_direction = "NO FACE"
        self.gaze_direction = "NO FACE"
        self.instant_focus_score = 0
        self.camera_available = False
        self._latest_jpeg: Optional[bytes] = None
        self._latest_frame = None
        self._missing_streak_sec = 0.0
        self._gaze_missing_streak_sec = 0.0
        self._last_good_gaze = "CENTER"
        self._smoother = DetectionSmoother(window=5)

    def is_running(self) -> bool:
        return self._measurement_active

    def start(self) -> None:
        self.ensure_preview()
        self._measurement_active = True

    def stop(self) -> None:
        self._measurement_active = False
        self._stop.set()
        for thread in (self._preview_thread, self._analysis_thread):
            if thread is not None:
                thread.join(timeout=2.0)
        self._preview_thread = None
        self._analysis_thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def pause(self) -> None:
        self._measurement_active = False

    def ensure_preview(self) -> None:
        if (
            self._preview_thread is not None
            and self._preview_thread.is_alive()
            and self._analysis_thread is not None
            and self._analysis_thread.is_alive()
        ):
            return
        self._stop.clear()
        self._preview_thread = threading.Thread(
            target=self._preview_loop,
            name="CameraPreview",
            daemon=True,
        )
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop,
            name="CameraAnalysis",
            daemon=True,
        )
        self._preview_thread.start()
        self._analysis_thread.start()

    def reset(self) -> None:
        with self._lock:
            self.focused = False
            self.focus_time_sec = 0
            self.distract_time_sec = 0
            self.active_window = ""
            self.message = "카메라 대기 중"
            self.face_direction = "NO FACE"
            self.gaze_direction = "NO FACE"
            self.instant_focus_score = 0
            self.camera_available = False
            self._latest_jpeg = None
            self._missing_streak_sec = 0.0
            self._gaze_missing_streak_sec = 0.0
            self._last_good_gaze = "CENTER"
            self._measurement_active = False
            self._smoother.reset()

    def get_status(self) -> Dict[str, object]:
        with self._lock:
            total = self.focus_time_sec + self.distract_time_sec
            focus_score = round(100 * self.focus_time_sec / total) if total > 0 else 100
            mode = "얼굴만(경량)" if self._face_only else "얼굴+시선"
            return {
                "running": self.is_running(),
                "focused": self.focused,
                "focus_score": focus_score,
                "focus_time_sec": self.focus_time_sec,
                "distract_time_sec": self.distract_time_sec,
                "active_window": self.active_window,
                "message": self.message,
                "monitor_type": "camera",
                "camera_available": self.camera_available,
                "face_direction": self.face_direction,
                "gaze_direction": self.gaze_direction,
                "instant_focus_score": self.instant_focus_score,
                "focus_formula": (
                    f"집중점수({mode}) · 분석 {self._analyze_interval:.1f}초 간격"
                ),
            }

    def get_frame_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def stream_frames(self):
        min_interval = camera_stream_interval()
        last_sent = 0.0
        while True:
            frame = self.get_frame_jpeg()
            now = time.time()
            if frame is None or (now - last_sent) < min_interval:
                time.sleep(0.03)
                continue
            last_sent = now
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

    def _ensure_camera(self) -> bool:
        if self._cap is not None and self._cap.isOpened():
            return True
        self._cap = cv2.VideoCapture(0)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width())
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height())
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, 15)
        return self._cap.isOpened()

    def _read_frame(self):
        if not self._ensure_camera():
            return None
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok:
            return None
        return cv2.flip(frame, 1)

    def _encode_jpeg(self, frame) -> Optional[bytes]:
        ok_jpeg, jpeg = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), camera_jpeg_quality()],
        )
        return jpeg.tobytes() if ok_jpeg else None

    def _preview_loop(self) -> None:
        interval = camera_preview_interval()
        while not self._stop.is_set():
            try:
                frame = self._read_frame()
                if frame is None:
                    with self._lock:
                        self.camera_available = False
                        self._latest_frame = None
                    time.sleep(interval)
                    continue
                jpeg = self._encode_jpeg(frame)
                with self._lock:
                    self.camera_available = True
                    self._latest_frame = frame
                    if jpeg:
                        self._latest_jpeg = jpeg
            except Exception:
                with self._lock:
                    self.camera_available = False
                    self._latest_frame = None
            time.sleep(interval)

    def _direction_score_face(self, direction: str) -> float:
        if direction == "DOWN":
            return 1.0
        if direction == "CENTER":
            return 0.8
        if direction in {"LEFT", "RIGHT"}:
            return 0.3
        return 0.0

    def _direction_score_gaze(self, direction: str) -> float:
        if direction in {"CENTER", "DOWN"}:
            return 1.0
        if direction == "UP":
            return 0.5
        if direction in {"LEFT", "RIGHT"}:
            return 0.4
        if direction in {"NO PUPIL", "NO EYE"}:
            return 0.6
        return 0.0

    def _is_detection_missing(self, face_direction: str) -> bool:
        return face_direction == "NO FACE"

    def _compute_instant_ratio(self, face_direction: str, gaze_direction: str) -> float:
        face_score = self._direction_score_face(face_direction)
        if self._face_only:
            return face_score

        gaze_for_score = gaze_direction
        if gaze_direction in {"NO EYE", "NO PUPIL", "NO FACE"}:
            self._gaze_missing_streak_sec += self._analyze_interval
            if self._gaze_missing_streak_sec <= self.gaze_grace_sec:
                gaze_for_score = self._last_good_gaze
            else:
                gaze_for_score = gaze_direction
        else:
            self._gaze_missing_streak_sec = 0.0
            self._last_good_gaze = gaze_direction
            gaze_for_score = gaze_direction

        gaze_score = self._direction_score_gaze(gaze_for_score)
        if face_direction == "NO FACE":
            return 0.0
        return 0.45 * face_score + 0.55 * gaze_score

    def _apply_detection(
        self,
        *,
        face_direction: str,
        gaze_direction: str,
        instant_ratio: float,
        focused: bool,
    ) -> None:
        instant_score = round(instant_ratio * 100)
        detection_missing = self._is_detection_missing(face_direction)

        with self._lock:
            self.face_direction = face_direction
            self.gaze_direction = gaze_direction
            self.instant_focus_score = instant_score
            self.active_window = f"얼굴:{face_direction} | 시선:{gaze_direction}"

            if detection_missing:
                self._missing_streak_sec += self._analyze_interval
                if self._missing_streak_sec <= self.missing_grace_sec:
                    self.message = (
                        f"탐지 유예 중 ({int(self._missing_streak_sec)}초)"
                    )
                    if self._measurement_active:
                        if self.focused:
                            self.focus_time_sec += int(self._analyze_interval)
                        else:
                            self.distract_time_sec += int(self._analyze_interval)
                else:
                    self.focused = False
                    self.message = "집중 이탈 (연속 미탐지)"
                    if self._measurement_active:
                        self.distract_time_sec += int(self._analyze_interval)
            else:
                self._missing_streak_sec = 0.0
                self.focused = focused
                self.message = "집중 중" if focused else "집중 이탈 (카메라 판정)"
                if self._measurement_active and focused:
                    self.focus_time_sec += int(self._analyze_interval)
                elif self._measurement_active:
                    self.distract_time_sec += int(self._analyze_interval)

            if not self._measurement_active:
                self.message = "카메라 테스트 중 (측정 대기)"

    def _analysis_loop(self) -> None:
        while not self._stop.is_set():
            try:
                with self._lock:
                    frame = None if self._latest_frame is None else self._latest_frame.copy()
                if frame is None:
                    with self._lock:
                        self.camera_available = False
                        self.focused = False
                        self.message = "카메라 연결 실패"
                        self.active_window = "카메라 미연결"
                    time.sleep(self._analyze_interval)
                    continue

                analysis_frame = cv2.resize(
                    frame,
                    (max(120, camera_width() // 2), max(90, camera_height() // 2)),
                )
                raw_face, raw_gaze, _face_box = analyze_camera_frame(
                    analysis_frame,
                    face_only=self._face_only,
                )
                raw_ratio = self._compute_instant_ratio(raw_face, raw_gaze)
                face_direction, gaze_direction, instant_ratio, focused = self._smoother.update(
                    raw_face,
                    raw_gaze,
                    raw_ratio,
                    focus_threshold=self.focus_threshold,
                )
                self._apply_detection(
                    face_direction=face_direction,
                    gaze_direction=gaze_direction,
                    instant_ratio=instant_ratio,
                    focused=focused,
                )
            except Exception:
                with self._lock:
                    self.camera_available = False
                    self.focused = False
                    self.message = "카메라 분석 오류"
                    self.active_window = "카메라 분석 오류"
            time.sleep(self._analyze_interval)


_camera_monitor: Optional[CameraFocusMonitor] = None


def get_camera_monitor() -> CameraFocusMonitor:
    global _camera_monitor
    if _camera_monitor is None:
        _camera_monitor = CameraFocusMonitor()
    return _camera_monitor
