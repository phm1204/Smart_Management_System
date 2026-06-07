"""컴퓨터 모드 집중 이탈 시 라즈베리파이 부저 신호 전송."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from src.device_config import pi_host
from src.pi_client import send_buzzer_signal


class ComputerBuzzerWatcher:
    def __init__(
        self,
        *,
        get_monitor_status: Callable[[], dict],
        is_computer_mode: Callable[[], bool],
        poll_interval: float = 1.0,
    ) -> None:
        self._get_monitor_status = get_monitor_status
        self._is_computer_mode = is_computer_mode
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._was_focused = True

    def start(self) -> None:
        if not pi_host():
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ComputerBuzzerWatcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._is_computer_mode():
                    status = self._get_monitor_status()
                    running = bool(status.get("running"))
                    focused = bool(status.get("focused"))
                    if running and self._was_focused and not focused:
                        send_buzzer_signal()
                    if running:
                        self._was_focused = focused
                    else:
                        self._was_focused = True
            except Exception:
                pass
            time.sleep(self._poll_interval)


_watcher: Optional[ComputerBuzzerWatcher] = None


def get_computer_buzzer_watcher(
    *,
    get_monitor_status: Callable[[], dict],
    is_computer_mode: Callable[[], bool],
) -> ComputerBuzzerWatcher:
    global _watcher
    if _watcher is None:
        _watcher = ComputerBuzzerWatcher(
            get_monitor_status=get_monitor_status,
            is_computer_mode=is_computer_mode,
        )
        _watcher.start()
    return _watcher
