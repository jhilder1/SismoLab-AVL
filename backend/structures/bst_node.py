from __future__ import annotations
from typing import Optional
from .tree_key import TreeKey

class BSTNode:
    def __init__(self, key: TreeKey):
        self.key = key
        self.event_id = key.event_id
        
        self.left: Optional[BSTNode] = None
        self.right: Optional[BSTNode] = None
