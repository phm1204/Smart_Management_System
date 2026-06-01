from __future__ import annotations

import threading
import time
from typing import Dict, Optional

import cv2

from src.monitor_base import BaseMonitor
from src.vision.camera_analysis_core import DetectionSmoother, analyze_camera_frame


class CameraFocusMonitor(BaseMonitor):
    """카메라 얼굴/시선으로 집중도를 측정한다."""

    def __init__(self, interval_sec: float = 0.4) -> None:
        self.interval_sec = interval_sec
        # 느슨한 판정값: 짧은 시선 흔들림을 덜 민감하게 반영
        self.focus_threshold = 0.5
        # 잠깐 미탐지(얼굴/눈 미검출) 유예 시간
        self.missing_grace_sec = 10.0
        self.gaze_grace_sec = 5.0

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._measurement_active = False

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
        self._missing_streak_sec = 0.0
        self._gaze_missing_streak_sec = 0.0
        self._last_good_gaze = "CENTER"
        self._smoother = DetectionSmoother(window=13)

    def is_running(self) -> bool:
        return self._measurement_active

    def start(self) -> None:
        self.ensure_preview()
        self._measurement_active = True

    def stop(self) -> None:
        # 하드 스톱(리소스 해제) - 학습 매체 변경/종료 시 호출
        self._measurement_active = False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def pause(self) -> None:
        # 미리보기는 유지하고 측정만 일시정지
        self._measurement_active = False

    def ensure_preview(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="CameraFocusMonitor",
            daemon=True,
        )
        self._thread.start()

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
                    "집중점수(실시간)=얼굴*0.45+시선*0.55, "
                    f"시선미검출 {int(self.gaze_grace_sec)}초 유예, "
                    f"미탐지 {int(self.missing_grace_sec)}초 유예"
                ),
            }

    def get_frame_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def stream_frames(self):
        while True:
            frame = self.get_frame_jpeg()
            if frame is None:
                time.sleep(0.1)
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

    def _ensure_camera(self) -> bool:
        if self._cap is not None and self._cap.isOpened():
            return True
        self._cap = cv2.VideoCapture(0)
        # 해상도를 낮춰 분석 지연을 줄인다.
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return self._cap.isOpened()

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
        # 눈 깜빡임/순간 미검출은 너무 낮게 깎지 않음
        if direction in {"NO PUPIL", "NO EYE"}:
            return 0.6
        return 0.0

    def _is_detection_missing(self, face_direction: str) -> bool:
        return face_direction == "NO FACE"

    def _compute_instant_ratio(self, face_direction: str, gaze_direction: str) -> float:
        face_score = self._direction_score_face(face_direction)
        gaze_for_score = gaze_direction

        if gaze_direction in {"NO EYE", "NO PUPIL", "NO FACE"}:
            self._gaze_missing_streak_sec += self.interval_sec
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
        if gaze_direction in {"NO EYE", "NO PUPIL", "NO FACE"} and (
            self._gaze_missing_streak_sec > self.gaze_grace_sec
        ):
            return 0.55 * face_score + 0.45 * gaze_score
        return 0.45 * face_score + 0.55 * gaze_score

    def _tick(self) -> None:
        if not self._ensure_camera():
            with self._lock:
                self.camera_available = False
                self.focused = False
                self.message = "카메라 연결 실패"
                self.active_window = "카메라 미연결"
                if self._measurement_active:
                    self.distract_time_sec += 1
            return

        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok:
            with self._lock:
                self.camera_available = False
                self.focused = False
                self.message = "카메라 프레임 수신 실패"
                self.active_window = "카메라 오류"
                if self._measurement_active:
                    self.distract_time_sec += 1
            return

        frame = cv2.flip(frame, 1)
        raw_face, raw_gaze, face_box = analyze_camera_frame(frame)

        raw_ratio = self._compute_instant_ratio(raw_face, raw_gaze)
        face_direction, gaze_direction, instant_ratio, focused = self._smoother.update(
            raw_face,
            raw_gaze,
            raw_ratio,
            focus_threshold=self.focus_threshold,
        )
        instant_score = round(instant_ratio * 100)
        detection_missing = self._is_detection_missing(face_direction)

        if face_box is not None:
            x, y, w, h = face_box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (59, 130, 246), 2)

        cv2.putText(
            frame,
            f"Face:{face_direction}  Gaze:{gaze_direction}  Score:{instant_score}",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0) if focused else (0, 120, 255),
            2,
        )
        ok_jpeg, jpeg = cv2.imencode(".jpg", frame)

        with self._lock:
            self.camera_available = True
            self.face_direction = face_direction
            self.gaze_direction = gaze_direction
            self.instant_focus_score = instant_score
            self.active_window = f"얼굴:{face_direction} | 시선:{gaze_direction}"

            if detection_missing:
                self._missing_streak_sec += self.interval_sec
                if self._missing_streak_sec <= self.missing_grace_sec:
                    # 유예 구간에서는 스코어 하락을 막고 직전 상태를 유지
                    self.message = (
                        f"탐지 유예 중 ({int(self._missing_streak_sec)}초) - "
                        "순간 미탐지 무시"
                    )
                    if self._measurement_active:
                        if self.focused:
                            self.focus_time_sec += 1
                        else:
                            self.distract_time_sec += 1
                else:
                    self.focused = False
                    self.message = "집중 이탈 (연속 미탐지)"
                    if self._measurement_active:
                        self.distract_time_sec += 1
            else:
                self._missing_streak_sec = 0.0
                self.focused = focused
                self.message = "집중 중" if focused else "집중 이탈 (카메라 판정)"
                if self._measurement_active and focused:
                    self.focus_time_sec += 1
                elif self._measurement_active:
                    self.distract_time_sec += 1

            if not self._measurement_active:
                self.message = "카메라 테스트 중 (측정 대기)"
            if ok_jpeg:
                self._latest_jpeg = jpeg.tobytes()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                with self._lock:
                    self.camera_available = False
                    self.focused = False
                    self.message = "카메라 분석 오류"
                    self.active_window = "카메라 분석 오류"
                    if self._measurement_active:
                        self.distract_time_sec += 1
            time.sleep(self.interval_sec)


_camera_monitor: Optional[CameraFocusMonitor] = None


def get_camera_monitor() -> CameraFocusMonitor:
    global _camera_monitor
    if _camera_monitor is None:
        _camera_monitor = CameraFocusMonitor()
    return _camera_monitor

