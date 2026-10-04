"""
compare_trees — inserts the same key sequence into an AVL and a BST and
compares them (Sections 11 and 15).
"""

from __future__ import annotations

from core.avl_tree import AVLTree
from core.bst_tree import BSTTree
from core.tree_key import TreeKey


class _DummyEvent:
    """Minimal event the AVL can index when only the key is known."""

    def __init__(self, key: TreeKey):
        self.key = key
        self.event_id = key.event_id
        self.priority = key.priority
        self.magnitude = key.magnitude

    def build_key(self) -> TreeKey:
        return self.key


def _tree_summary(tree, comparisons: list[int]) -> dict:
    total_keys = len(comparisons)
    average = (sum(comparisons) / total_keys) if total_keys > 0 else 0.0
    return {
        "root": str(tree.root.key) if tree.root else None,
        "height": tree.height,
        "leaves": tree.count_leaves(),
        "total_comparisons": sum(comparisons),
        "avg_comparisons": round(average, 2),
        "tree": tree.to_dict(),
    }


def compare_trees(keys: list[TreeKey]) -> dict:
    """
    Inserts exactly the same key sequence into an AVL and into a BST.
    Compares roots, heights, leaf counts and search comparisons.
    """
    avl = AVLTree()
    bst = BSTTree()

    for k in keys:
        avl.insert(_DummyEvent(k))
        bst.insert(k)

    # Compare the search of every key
    avl_comps = [avl.search(k)[1] for k in keys]
    bst_comps = [bst.search(k)[1] for k in keys]

    return {
        "size": len(keys),
        "avl": _tree_summary(avl, avl_comps),
        "bst": _tree_summary(bst, bst_comps),
    }
