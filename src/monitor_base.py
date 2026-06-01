from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseMonitor(ABC):
    """공통 모니터 인터페이스.

    - 구현체는 내부에서 스레드/루프를 돌릴 수 있지만, 외부(Flask)는 동일한 API만 호출한다.
    - start/stop/reset/get_status 형태로 통일해 백엔드/라즈베리/카메라 구현 교체가 쉬워진다.
    """

    @abstractmethod
    def start(self, *args: Any, **kwargs: Any) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def get_status(self) -> Dict[str, Any]: ...

