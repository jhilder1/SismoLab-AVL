import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from structures.tree_key import TreeKey
from structures.avl_tree import AVLTree

def test_avl_insert_and_balance():
    tree = AVLTree()
    tree.insert(TreeKey(3, 6.0, 10))
    tree.insert(TreeKey(2, 5.0, 20))
    tree.insert(TreeKey(1, 4.0, 30))
    
    assert tree.root.key.priority == 2
    assert tree.root.left.key.priority == 1
    assert tree.root.right.key.priority == 3
    
def test_avl_stress_mode():
    tree = AVLTree()
    tree.stress_mode = True
    
    tree.insert(TreeKey(3, 6.0, 10))
    tree.insert(TreeKey(2, 5.0, 20))
    tree.insert(TreeKey(1, 4.0, 30))
    
    assert tree.root.key.priority == 3
    assert tree.root.left.key.priority == 2
    assert tree.root.left.left.key.priority == 1
    
    tree.recover_balance()
    assert tree.stress_mode == False
    assert tree.root.key.priority == 2
    assert tree.root.left.key.priority == 1
    assert tree.root.right.key.priority == 3

def test_avl_delete():
    tree = AVLTree()
    tree.insert(TreeKey(3, 6.0, 10))
    tree.insert(TreeKey(2, 5.0, 20))
    tree.insert(TreeKey(1, 4.0, 30))
    
    tree.delete(TreeKey(2, 5.0, 20))
    assert tree.size == 2
    assert tree.root.key.priority == 3
    assert tree.root.left.key.priority == 1

def test_avl_inorder():
    tree = AVLTree()
    tree.insert(TreeKey(2, 5.0, 20))
    tree.insert(TreeKey(1, 3.0, 10))
    tree.insert(TreeKey(3, 7.0, 30))
    
    keys = tree.inorder()
    assert len(keys) == 3
    assert keys[0] < keys[1] < keys[2]

def test_avl_search():
    tree = AVLTree()
    k = TreeKey(2, 5.0, 20)
    tree.insert(k)
    
    found = tree.search(k)
    assert found is not None
    assert found.key == k
    
    not_found = tree.search(TreeKey(1, 1.0, 999))
    assert not_found is None

def test_avl_is_balanced():
    tree = AVLTree()
    tree.insert(TreeKey(1, 1.0, 1))
    tree.insert(TreeKey(2, 2.0, 2))
    tree.insert(TreeKey(3, 3.0, 3))
    assert tree.is_balanced()
