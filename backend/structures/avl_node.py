from __future__ import annotations
from typing import Optional
from .tree_key import TreeKey

class AVLNode:
    def __init__(self, key: TreeKey):
        self.key = key
        # Referencia por identidad al evento
        self.event_id = key.event_id
        
        self.left: Optional[AVLNode] = None
        self.right: Optional[AVLNode] = None
        self.height: int = 0
    
    @property
    def balance_factor(self) -> int:
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        return left_h - right_h
    
    def update_height(self):
        left_h = self.left.height if self.left else -1
        right_h = self.right.height if self.right else -1
        self.height = 1 + max(left_h, right_h)
