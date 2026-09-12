import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from structures.tree_key import TreeKey
from structures.avl_tree import AVLTree

def test_avl_insert_and_balance():
    tree = AVLTree()
    # Insertar en orden descendente para forzar rotaciones
    tree.insert(TreeKey(3, 6.0, 10))
    tree.insert(TreeKey(2, 5.0, 20))
    tree.insert(TreeKey(1, 4.0, 30))
    
    # La raíz debería ser el elemento del medio tras balancear (LL imbalance)
    assert tree.root.key.priority == 2
    assert tree.root.left.key.priority == 1
    assert tree.root.right.key.priority == 3
    
def test_avl_stress_mode():
    tree = AVLTree()
    tree.stress_mode = True
    
    tree.insert(TreeKey(3, 6.0, 10))
    tree.insert(TreeKey(2, 5.0, 20))
    tree.insert(TreeKey(1, 4.0, 30))
    
    # En modo estrés no se balancea, así que es un palo hacia la izquierda
    assert tree.root.key.priority == 3
    assert tree.root.left.key.priority == 2
    assert tree.root.left.left.key.priority == 1
    
    # Recuperar balance
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
