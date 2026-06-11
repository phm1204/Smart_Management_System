"""PC·라즈베리파이 연동 설정 (환경 변수)."""
from __future__ import annotations

import os
from urllib.parse import urlparse


def pi_base_url() -> str:
    return os.environ.get("PI_BASE_URL", "").rstrip("/")


def use_pi_for_book() -> bool:
    return bool(pi_base_url())


def pi_host() -> str:
    url = pi_base_url()
    if not url:
        return os.environ.get("PI_HOST", "")
    return urlparse(url).hostname or ""


def pi_buzzer_udp_port() -> int:
    return int(os.environ.get("PI_BUZZER_UDP_PORT", "9999"))


def buzzer_serial_port() -> str:
    return os.environ.get("BUZZER_SERIAL_PORT", "")


def buzzer_serial_baud() -> int:
    return int(os.environ.get("BUZZER_SERIAL_BAUD", "9600"))


def pi_service_port() -> int:
    return int(os.environ.get("PI_SERVICE_PORT", "5001"))


def camera_width() -> int:
    return int(os.environ.get("CAMERA_WIDTH", "640"))


def camera_height() -> int:
    return int(os.environ.get("CAMERA_HEIGHT", "480"))


def camera_device_index() -> int:
    return int(os.environ.get("CAMERA_DEVICE_INDEX", "0"))


def camera_jpeg_quality() -> int:
    return int(os.environ.get("CAMERA_JPEG_QUALITY", "55"))


def camera_stream_interval() -> float:
    return float(os.environ.get("CAMERA_STREAM_INTERVAL", "0.25"))


def camera_preview_interval() -> float:
    return float(os.environ.get("CAMERA_PREVIEW_INTERVAL", "0.2"))


def camera_analyze_interval() -> float:
    return float(os.environ.get("CAMERA_ANALYZE_INTERVAL", "1.0"))


def camera_face_only() -> bool:
    return os.environ.get("CAMERA_FACE_ONLY", "1").lower() in {"1", "true", "yes"}
