from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class FaceDirectionConfig:
    # 화면 중앙 대비 이동량(threshold) 기반 간단 판정
    left_right_px: int = 100
    down_px: int = 80
    # HaarCascade 파라미터
    scale_factor: float = 1.1
    min_neighbors: int = 6
    min_size: Tuple[int, int] = (120, 120)


def _default_face_cascade() -> cv2.CascadeClassifier:
    return cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )


def detect_face_direction(
    frame_bgr: np.ndarray,
    *,
    config: FaceDirectionConfig = FaceDirectionConfig(),
    face_cascade: Optional[cv2.CascadeClassifier] = None,
) -> str:
    """프레임 1장으로 얼굴 방향을 추정한다.

    반환: "LEFT" | "RIGHT" | "DOWN" | "CENTER" | "NO FACE"
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return "NO FACE"

    face_cascade = face_cascade or _default_face_cascade()
    frame_h, frame_w = frame_bgr.shape[:2]
    screen_center_x = frame_w // 2
    screen_center_y = frame_h // 2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=config.scale_factor,
        minNeighbors=config.min_neighbors,
        minSize=config.min_size,
    )
    if len(faces) == 0:
        return "NO FACE"

    # 가장 큰 얼굴 1개만 사용
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    face_center_x = x + w // 2
    face_center_y = y + h // 2

    direction = "CENTER"
    if face_center_x < screen_center_x - config.left_right_px:
        direction = "LEFT"
    elif face_center_x > screen_center_x + config.left_right_px:
        direction = "RIGHT"

    # 책 보기(고개 숙임) 간단 추정
    if face_center_y > screen_center_y + config.down_px:
        direction = "DOWN"

    return direction

