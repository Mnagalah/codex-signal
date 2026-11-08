"""Bounded writes for nonblocking plugin-owned sockets and renderer pipes."""
from __future__ import annotations

import os
import select
import time


def write_all(fd: int, data: bytes, *, timeout: float) -> None:
    """Write one complete frame or fail; discard the channel after any failure."""
    remaining = memoryview(data)
    deadline = time.monotonic() + timeout
    while remaining:
        wait = deadline - time.monotonic()
        if wait <= 0 or not select.select([], [fd], [], wait)[1]:
            raise TimeoutError("Plugin channel write timed out")
        try:
            sent = os.write(fd, remaining)
        except (BlockingIOError, InterruptedError):
            continue
        if sent == 0:
            raise ConnectionError("Plugin channel write closed")
        remaining = remaining[sent:]
