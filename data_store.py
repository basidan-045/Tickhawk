# =============================================================================
# data_store.py — Thread-safe in-memory storage for tick data.
#
# WHY threading.Lock? The websocket callback runs on one thread and the
# auto-save background thread reads the same list concurrently. Without a
# lock, you risk reading a partially-written list and corrupting the Excel
# backup. Lock acquisition is microseconds — it does not affect tick capture.
# =============================================================================

import logging
import threading
from datetime import datetime
from typing import TypedDict

import pytz

import config

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


class Tick(TypedDict):
    """Single price update record."""
    time: str    # HH:MM:SS.mmm in IST
    price: float


class TickStore:
    """
    Thread-safe in-memory store for tick data.

    All methods that read or write the tick list acquire the lock first.
    The store is the single source of truth — both the exporter and grapher
    read from here.
    """

    def __init__(self) -> None:
        """Initialize an empty tick store with a reentrant lock."""
        self._ticks: list[Tick] = []
        self._lock = threading.Lock()
        self._total_ticks: int = 0

    def add_tick(self, price: float) -> int:
        """
        Append a new tick with the current IST timestamp.

        Args:
            price: Last traded price as a float.

        Returns:
            Total tick count after this addition.
        """
        # Capture time immediately — any delay after receiving the tick
        # degrades timestamp accuracy, so do this before acquiring the lock.
        now_ist = datetime.now(IST)
        time_str = now_ist.strftime("%H:%M:%S.") + f"{now_ist.microsecond // 1000:03d}"

        tick: Tick = {"time": time_str, "price": round(price, 2)}

        with self._lock:
            self._ticks.append(tick)
            self._total_ticks += 1
            count = self._total_ticks

        return count

    def get_all_ticks(self) -> list[Tick]:
        """
        Return a snapshot copy of all ticks collected so far.

        Returns a copy so callers can iterate without holding the lock.

        Returns:
            List of Tick dicts.
        """
        with self._lock:
            return list(self._ticks)

    def tick_count(self) -> int:
        """
        Return the current total number of ticks captured.

        Returns:
            Integer tick count.
        """
        with self._lock:
            return self._total_ticks

    def is_empty(self) -> bool:
        """
        Check whether any ticks have been captured yet.

        Returns:
            True if no ticks have been recorded.
        """
        with self._lock:
            return len(self._ticks) == 0
