"""
Linear structures: the undo stack and the FIFO report queue.
"""

from collections import deque


class UndoStack:
    """Stack of undoable actions with a configurable maximum size."""

    def __init__(self, max_size: int = 100):
        self._stack = []
        self._max_size = max_size

    def push(self, action: dict):
        if len(self._stack) >= self._max_size:
            self._stack.pop(0)
        self._stack.append(action)

    def pop(self) -> dict:
        if self.is_empty():
            raise IndexError("pop from empty UndoStack")
        return self._stack.pop()

    def peek(self) -> dict:
        if self.is_empty():
            raise IndexError("peek from empty UndoStack")
        return self._stack[-1]

    def is_empty(self) -> bool:
        return len(self._stack) == 0

    def size(self) -> int:
        return len(self._stack)

    def clear(self):
        self._stack.clear()


class ReportQueue:
    """FIFO queue of seismic station reports."""

    def __init__(self):
        self._queue = deque()
        self.total_enqueued = 0

    def enqueue(self, report):
        self._queue.append(report)
        self.total_enqueued += 1

    def dequeue(self):
        if self.is_empty():
            raise IndexError("dequeue from empty ReportQueue")
        return self._queue.popleft()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty ReportQueue")
        return self._queue[0]

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def size(self) -> int:
        return len(self._queue)

    def get_all(self) -> list:
        return list(self._queue)

    def clear(self):
        self._queue.clear()
