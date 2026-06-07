from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

FaceBox = Tuple[int, int, int, int]


@dataclass(frozen=True)
class CameraAnalysisConfig:
    face_scale_factor: float = 1.08
    face_min_neighbors: int = 5
    face_min_size_ratio: float = 0.18  # 프레임 짧은 변 대비 최소 얼굴 크기

    eye_scale_factor: float = 1.08
    eye_min_neighbors: int = 8
    eye_min_size: Tuple[int, int] = (28, 28)

    left_right_ratio: float = 0.12
    down_ratio: float = 0.10

    gaze_left_thr: float = 0.38
    gaze_right_thr: float = 0.62
    gaze_up_thr: float = 0.38
    gaze_down_thr: float = 0.62


def _default_face_cascade() -> cv2.CascadeClassifier:
    return cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )


def _default_eye_cascade() -> cv2.CascadeClassifier:
    return cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_eye.xml"
    )


_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _preprocess_gray(gray: np.ndarray) -> np.ndarray:
    return _clahe.apply(gray)


def _detect_largest_face(
    gray: np.ndarray,
    *,
    config: CameraAnalysisConfig,
    face_cascade: cv2.CascadeClassifier,
) -> Optional[FaceBox]:
    frame_h, frame_w = gray.shape[:2]
    min_dim = min(frame_h, frame_w)
    min_size = max(80, int(min_dim * config.face_min_size_ratio))

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=config.face_scale_factor,
        minNeighbors=config.face_min_neighbors,
        minSize=(min_size, min_size),
    )
    if len(faces) == 0:
        return None

    return max(faces, key=lambda b: b[2] * b[3])


def _face_direction_from_box(
    box: FaceBox,
    frame_shape: Tuple[int, int],
    *,
    config: CameraAnalysisConfig,
) -> str:
    frame_h, frame_w = frame_shape
    x, y, w, h = box
    face_center_x = x + w // 2
    face_center_y = y + h // 2
    screen_center_x = frame_w // 2
    screen_center_y = frame_h // 2

    lr_thr = int(frame_w * config.left_right_ratio)
    down_thr = int(frame_h * config.down_ratio)

    direction = "CENTER"
    if face_center_x < screen_center_x - lr_thr:
        direction = "LEFT"
    elif face_center_x > screen_center_x + lr_thr:
        direction = "RIGHT"

    if face_center_y > screen_center_y + down_thr:
        direction = "DOWN"

    return direction


def _gaze_from_ratios(h_ratio: float, v_ratio: float, *, config: CameraAnalysisConfig) -> str:
    direction = "CENTER"
    if h_ratio < config.gaze_left_thr:
        direction = "LEFT"
    elif h_ratio > config.gaze_right_thr:
        direction = "RIGHT"

    if v_ratio < config.gaze_up_thr:
        direction = "UP"
    elif v_ratio > config.gaze_down_thr:
        direction = "DOWN"

    return direction


def _pupil_ratios(eye_gray: np.ndarray) -> Optional[Tuple[float, float]]:
    eye_h, eye_w = eye_gray.shape[:2]
    if eye_h < 8 or eye_w < 8:
        return None

    blur = cv2.GaussianBlur(eye_gray, (7, 7), 1.5)
    max_radius = max(4, min(eye_w, eye_h) // 4)
    min_radius = max(2, max_radius // 3)

    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(8, eye_w // 2),
        param1=50,
        param2=18,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None:
        return None

    circles = np.uint16(np.around(circles))
    cx, cy, _ = circles[0, 0]
    return float(cx) / float(max(1, eye_w)), float(cy) / float(max(1, eye_h))


def _gaze_direction_from_face(
    face_gray: np.ndarray,
    *,
    config: CameraAnalysisConfig,
    eye_cascade: cv2.CascadeClassifier,
) -> str:
    eyes = eye_cascade.detectMultiScale(
        face_gray,
        scaleFactor=config.eye_scale_factor,
        minNeighbors=config.eye_min_neighbors,
        minSize=config.eye_min_size,
    )
    if len(eyes) == 0:
        return "NO EYE"

    eyes = sorted(eyes, key=lambda b: b[0])[:2]
    ratios: list[Tuple[float, float]] = []

    for ex, ey, ew, eh in eyes:
        eye_gray = face_gray[ey : ey + eh, ex : ex + ew]
        ratio = _pupil_ratios(eye_gray)
        if ratio is not None:
            ratios.append(ratio)

    if not ratios:
        return "NO PUPIL"

    h_ratio = sum(r[0] for r in ratios) / len(ratios)
    v_ratio = sum(r[1] for r in ratios) / len(ratios)
    return _gaze_from_ratios(h_ratio, v_ratio, config=config)


def analyze_camera_frame(
    frame_bgr: np.ndarray,
    *,
    config: CameraAnalysisConfig = CameraAnalysisConfig(),
    face_cascade: Optional[cv2.CascadeClassifier] = None,
    eye_cascade: Optional[cv2.CascadeClassifier] = None,
    face_only: bool = False,
) -> Tuple[str, str, Optional[FaceBox]]:
    """얼굴 1회 검출 후 얼굴 방향·시선 방향을 함께 계산한다."""
    if frame_bgr is None or frame_bgr.size == 0:
        return "NO FACE", "NO FACE", None

    face_cascade = face_cascade or _default_face_cascade()
    eye_cascade = eye_cascade or _default_eye_cascade()

    gray = _preprocess_gray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY))
    box = _detect_largest_face(gray, config=config, face_cascade=face_cascade)
    if box is None:
        return "NO FACE", "NO FACE", None

    face_direction = _face_direction_from_box(box, gray.shape, config=config)
    if face_only:
        return face_direction, face_direction, box

    x, y, w, h = box
    face_gray = gray[y : y + h, x : x + w]
    gaze_direction = _gaze_direction_from_face(
        face_gray,
        config=config,
        eye_cascade=eye_cascade,
    )
    return face_direction, gaze_direction, box


class DetectionSmoother:
    """짧은 노이즈를 줄이기 위한 시간적 안정화."""

    def __init__(self, window: int = 5) -> None:
        self.window = window
        self._face_history: list[str] = []
        self._gaze_history: list[str] = []
        self._score_history: list[float] = []
        self._focused_confirm = 0
        self._distracted_confirm = 0
        self._stable_focused = False

    def reset(self) -> None:
        self._face_history.clear()
        self._gaze_history.clear()
        self._score_history.clear()
        self._focused_confirm = 0
        self._distracted_confirm = 0
        self._stable_focused = False

    def _mode(self, values: list[str]) -> str:
        if not values:
            return "NO FACE"
        return Counter(values).most_common(1)[0][0]

    def update(
        self,
        face_direction: str,
        gaze_direction: str,
        instant_ratio: float,
        *,
        focus_threshold: float,
    ) -> Tuple[str, str, float, bool]:
        self._face_history.append(face_direction)
        self._gaze_history.append(gaze_direction)
        self._score_history.append(instant_ratio)

        if len(self._face_history) > self.window:
            self._face_history.pop(0)
        if len(self._gaze_history) > self.window:
            self._gaze_history.pop(0)
        if len(self._score_history) > self.window:
            self._score_history.pop(0)

        stable_face = self._mode(self._face_history)
        stable_gaze = self._mode(self._gaze_history)
        stable_ratio = sum(self._score_history) / len(self._score_history)

        raw_focused = stable_ratio >= focus_threshold
        if raw_focused:
            self._focused_confirm += 1
            self._distracted_confirm = 0
        else:
            self._distracted_confirm += 1
            self._focused_confirm = 0

        if self._focused_confirm >= 2:
            self._stable_focused = True
        elif self._distracted_confirm >= 2:
            self._stable_focused = False

        return stable_face, stable_gaze, stable_ratio, self._stable_focused
