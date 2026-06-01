from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class EyeTrackingConfig:
    # HaarCascade 파라미터
    face_scale_factor: float = 1.1
    face_min_neighbors: int = 6
    face_min_size: Tuple[int, int] = (120, 120)

    eye_scale_factor: float = 1.1
    eye_min_neighbors: int = 12
    eye_min_size: Tuple[int, int] = (40, 40)
    eye_max_size: Tuple[int, int] = (120, 120)

    # 동공 검출(HoughCircles) 파라미터 (기존 코드 유지)
    blur_kernel: Tuple[int, int] = (9, 9)
    blur_sigma: float = 2.0
    hough_dp: float = 1.0
    hough_min_dist: float = 20.0
    hough_param1: float = 50.0
    hough_param2: float = 15.0
    hough_min_radius: int = 5
    hough_max_radius: int = 25

    # 방향 판정 비율 기준
    left_thr: float = 0.35
    right_thr: float = 0.65
    up_thr: float = 0.35
    down_thr: float = 0.65


def _default_face_cascade() -> cv2.CascadeClassifier:
    return cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )


def _default_eye_cascade() -> cv2.CascadeClassifier:
    return cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_eye.xml"
    )


def _direction_from_ratios(
    horizontal_ratio: float,
    vertical_ratio: float,
    *,
    config: EyeTrackingConfig,
) -> str:
    direction = "CENTER"
    if horizontal_ratio < config.left_thr:
        direction = "LEFT"
    elif horizontal_ratio > config.right_thr:
        direction = "RIGHT"

    if vertical_ratio < config.up_thr:
        direction = "UP"
    elif vertical_ratio > config.down_thr:
        direction = "DOWN"

    return direction


def detect_gaze_direction(
    frame_bgr: np.ndarray,
    *,
    config: EyeTrackingConfig = EyeTrackingConfig(),
    face_cascade: Optional[cv2.CascadeClassifier] = None,
    eye_cascade: Optional[cv2.CascadeClassifier] = None,
) -> str:
    """프레임 1장으로 시선 방향을 아주 단순하게 추정한다.

    반환: "LEFT" | "RIGHT" | "UP" | "DOWN" | "CENTER" | "NO FACE" | "NO EYE" | "NO PUPIL"
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return "NO FACE"

    face_cascade = face_cascade or _default_face_cascade()
    eye_cascade = eye_cascade or _default_eye_cascade()

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=config.face_scale_factor,
        minNeighbors=config.face_min_neighbors,
        minSize=config.face_min_size,
    )
    if len(faces) == 0:
        return "NO FACE"

    # 가장 큰 얼굴 1개만 사용
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    face_gray = gray[y : y + h, x : x + w]

    eyes = eye_cascade.detectMultiScale(
        face_gray,
        scaleFactor=config.eye_scale_factor,
        minNeighbors=config.eye_min_neighbors,
        minSize=config.eye_min_size,
        maxSize=config.eye_max_size,
    )
    if len(eyes) == 0:
        return "NO EYE"

    # 첫 번째 눈 1개만 사용(가벼움)
    ex, ey, ew, eh = eyes[0]
    eye_gray = face_gray[ey : ey + eh, ex : ex + ew]

    blur = cv2.GaussianBlur(eye_gray, config.blur_kernel, config.blur_sigma)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=config.hough_dp,
        minDist=config.hough_min_dist,
        param1=config.hough_param1,
        param2=config.hough_param2,
        minRadius=config.hough_min_radius,
        maxRadius=config.hough_max_radius,
    )

    eye_h, eye_w = eye_gray.shape[:2]
    if circles is None:
        return "NO PUPIL"

    circles = np.uint16(np.around(circles))
    cx, cy, _radius = circles[0, 0]

    horizontal_ratio = float(cx) / float(max(1, eye_w))
    vertical_ratio = float(cy) / float(max(1, eye_h))
    return _direction_from_ratios(horizontal_ratio, vertical_ratio, config=config)

