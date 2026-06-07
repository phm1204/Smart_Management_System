"""PC Flask에서 라즈베리파이 API 호출."""
from __future__ import annotations

import socket
from typing import Any, Dict, Optional, Tuple

import requests

from src.device_config import pi_base_url, pi_buzzer_udp_port, pi_host, use_pi_for_book


class PiClientError(Exception):
    pass


def pi_available() -> bool:
    return use_pi_for_book()


def pi_get(path: str, timeout: float = 2.0) -> Dict[str, Any]:
    url = f"{pi_base_url()}{path}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise PiClientError(f"Pi GET 실패 ({url}): {exc}") from exc


def pi_post(path: str, timeout: float = 2.0) -> Dict[str, Any]:
    url = f"{pi_base_url()}{path}"
    try:
        response = requests.post(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise PiClientError(f"Pi POST 실패 ({url}): {exc}") from exc


def pi_stream(path: str, timeout: float = 10.0):
    url = f"{pi_base_url()}{path}"
    return requests.get(url, stream=True, timeout=timeout)


def send_buzzer_signal(host: Optional[str] = None, port: Optional[int] = None) -> bool:
    target_host = host or pi_host()
    if not target_host:
        return False
    target_port = port if port is not None else pi_buzzer_udp_port()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"BUZZ", (target_host, target_port))
        sock.close()
        return True
    except OSError:
        return False


def merge_buzzer_status(status: Dict[str, Any]) -> Dict[str, Any]:
    if not pi_available():
        status.setdefault("buzzer_active", False)
        status.setdefault("buzzer_simulated", True)
        return status
    try:
        buzzer = pi_get("/api/buzzer/status", timeout=1.0)
        status.update(buzzer)
    except PiClientError:
        status.setdefault("buzzer_active", False)
    return status
