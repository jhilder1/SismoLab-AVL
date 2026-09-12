from collections import deque
from backend.models.report import Report

class ReportQueue:
    def __init__(self):
        self._queue = deque()
        self.total_enqueued = 0

    def enqueue(self, report: Report):
        self._queue.append(report)
        self.total_enqueued += 1

    def dequeue(self) -> Report:
        if self.is_empty():
            raise IndexError("dequeue from empty ReportQueue")
        return self._queue.popleft()

    def peek(self) -> Report:
        if self.is_empty():
            raise IndexError("peek from empty ReportQueue")
        return self._queue[0]
        
    def restore_at_front(self, report: Report):
        self._queue.appendleft(report)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def size(self) -> int:
        return len(self._queue)

    def get_all(self) -> list[Report]:
        return list(self._queue)
        
    def clear(self):
        self._queue.clear()
