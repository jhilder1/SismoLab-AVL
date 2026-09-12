class UndoStack:
    def __init__(self, max_size: int = 100):
        self._stack = []
        self._max_size = max_size

    def push(self, action: dict):
        if len(self._stack) >= self._max_size:
            self._stack.pop(0) # Eliminar el más antiguo
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
