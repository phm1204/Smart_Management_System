"""아두이노 부저 제어 — 버튼 확인 전까지 울림 유지."""
from __future__ import annotations

import socket
import threading
import time
from typing import Optional

from src.device_config import (
    buzzer_serial_baud,
    buzzer_serial_port,
    pi_buzzer_udp_port,
)


class BuzzerController:
    """시리얼(B)로 부저 시작, 버튼 확인(A) 또는 UDP로 해제 대기."""

    def __init__(
        self,
        *,
        serial_port: Optional[str] = None,
        serial_baud: Optional[int] = None,
        udp_port: Optional[int] = None,
        simulate: bool = False,
    ) -> None:
        self.serial_port = serial_port if serial_port is not None else buzzer_serial_port()
        self.serial_baud = serial_baud if serial_baud is not None else buzzer_serial_baud()
        self.udp_port = udp_port if udp_port is not None else pi_buzzer_udp_port()
        self.simulate = simulate or not self.serial_port

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._serial = None
        self._threads: list[threading.Thread] = []
        self.buzzer_active = False

    def start(self) -> None:
        if self._threads:
            return

        if not self.simulate:
            self._open_serial()

        self._threads = [
            threading.Thread(target=self._serial_listener, name="BuzzerSerial", daemon=True),
            threading.Thread(target=self._udp_listener, name="BuzzerUDP", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self._write_serial(b"S")
            self.buzzer_active = False
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None

    def trigger(self) -> bool:
        """부저가 꺼져 있을 때만 시작. 이미 울리면 False."""
        with self._lock:
            if self.buzzer_active:
                return False
            self._write_serial(b"B")
            self.buzzer_active = True
            return True

    def acknowledge(self) -> None:
        with self._lock:
            self.buzzer_active = False

    def get_status(self) -> dict[str, object]:
        with self._lock:
            return {
                "buzzer_active": self.buzzer_active,
                "buzzer_simulated": self.simulate,
            }

    def _open_serial(self) -> None:
        try:
            import serial

            self._serial = serial.Serial(self.serial_port, self.serial_baud, timeout=0.1)
            # 아두이노는 시리얼 열릴 때 리셋됨 — 준비될 때까지 대기
            time.sleep(2.0)
            print(f"[Buzzer] 시리얼 연결됨: {self.serial_port}")
        except Exception as exc:
            print(f"[Buzzer] 시리얼 연결 실패 ({self.serial_port}): {exc}")
            self.simulate = True
            self._serial = None

    def _write_serial(self, payload: bytes) -> None:
        if self.simulate:
            print(f"[Buzzer] simulate write: {payload!r}")
            return
        if self._serial is None:
            return
        try:
            self._serial.write(payload)
        except Exception as exc:
            print(f"[Buzzer] 시리얼 전송 실패: {exc}")

    def _serial_listener(self) -> None:
        while not self._stop.is_set():
            if self.simulate or self._serial is None:
                time.sleep(0.2)
                continue
            try:
                raw = self._serial.read(1)
            except Exception:
                time.sleep(0.2)
                continue
            if raw in (b"A", b"a"):
                self.acknowledge()

    def _udp_listener(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", self.udp_port))
        except OSError as exc:
            print(f"[Buzzer] UDP 바인드 실패 (:{self.udp_port}): {exc}")
            return

        sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                data, _addr = sock.recvfrom(256)
            except (TimeoutError, OSError):
                if self._stop.is_set():
                    break
                continue
            if data.strip().upper() in {b"BUZZ", b"B"}:
                self.trigger()
        sock.close()


_buzzer_controller: Optional[BuzzerController] = None


def get_buzzer_controller() -> BuzzerController:
    global _buzzer_controller
    if _buzzer_controller is None:
        _buzzer_controller = BuzzerController()
        _buzzer_controller.start()
    return _buzzer_controller
