import threading
import time

import win32gui

from src.monitor_base import BaseMonitor

DEFAULT_DISTRACT_KEYWORDS = [
    "instagram",
    "youtube",
    "netflix",
    "tiktok",
    "facebook",
    "league of legends",
    "lol",
    "game",
    "discord",
]


class FocusMonitor(BaseMonitor):
    """활성 창 제목으로 집중/비집중 시간을 측정한다."""

    def __init__(self, distract_keywords=None, interval_sec=1.0):
        self.distract_keywords = list(
            distract_keywords or DEFAULT_DISTRACT_KEYWORDS
        )
        self.interval_sec = interval_sec
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._verbose = False

        self.active_window = ""
        self.focused = True
        self.focus_time_sec = 0
        self.distract_time_sec = 0
        self.last_title = ""

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, verbose=False):
        if self.is_running():
            return
        self._verbose = verbose
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="FocusMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def reset(self):
        with self._lock:
            self.active_window = ""
            self.focused = True
            self.focus_time_sec = 0
            self.distract_time_sec = 0
            self.last_title = ""

    def get_status(self):
        with self._lock:
            total = self.focus_time_sec + self.distract_time_sec
            if total > 0:
                focus_score = round(
                    100 * self.focus_time_sec / total
                )
            else:
                focus_score = 100

            return {
                "running": self.is_running(),
                "focused": self.focused,
                "focus_score": focus_score,
                "focus_time_sec": self.focus_time_sec,
                "distract_time_sec": self.distract_time_sec,
                "active_window": self.active_window,
                "message": (
                    "집중 중" if self.focused else "집중 이탈 (비집중 앱 감지)"
                ),
            }

    def _is_focused(self, title_lower):
        for word in self.distract_keywords:
            if word in title_lower:
                return False
        return True

    def _tick(self):
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
        title_lower = title.lower()
        focused = self._is_focused(title_lower)

        with self._lock:
            self.active_window = title
            self.focused = focused

            if focused:
                self.focus_time_sec += 1
            else:
                self.distract_time_sec += 1

            if self._verbose and title != self.last_title:
                print("\n" + "=" * 60)
                print(f"새로 감지된 창: {title}")
                print(
                    "현재 상태: 집중 중"
                    if focused
                    else "현재 상태: 집중 이탈"
                )
                print("=" * 60)
                self.last_title = title

            if self._verbose:
                print(
                    f"집중 시간: {self.focus_time_sec}초 | "
                    f"이탈 시간: {self.distract_time_sec}초",
                    end="\r",
                )

    def _run_loop(self):
        if self._verbose:
            print("실시간 집중도 분석 시작...\n")

        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                with self._lock:
                    self.active_window = ""
                if self._verbose:
                    print(f"\n모니터 오류: {exc}")
            time.sleep(self.interval_sec)


_default_monitor = None


def get_default_monitor():
    """Flask 앱에서 공유하는 싱글톤 모니터."""
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = FocusMonitor()
    return _default_monitor


def ensure_monitor_started():
    monitor = get_default_monitor()
    if not monitor.is_running():
        monitor.start()
    return monitor


if __name__ == "__main__":
    m = FocusMonitor()
    m.start(verbose=True)
    try:
        while m.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        m.stop()
        print("\n종료")
