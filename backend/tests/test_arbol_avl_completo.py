"""
Pruebas integrales del arbol AVL: rotaciones, comparacion de claves,
eliminacion, modo estres y recuperacion global, identidad del evento en el
nodo, busqueda con costo de acceso y giros elementales.

Este es el UNICO archivo de pruebas en espanol del proyecto; el resto de
comentarios del codigo va en ingles (seccion 17 del enunciado).

Referencias al enunciado:
  - Seccion 5:  regla de insercion, orden del AVL, identidad y cambios de clave.
  - Seccion 8:  cola de reportes y modo estres (balanceo diferido y recuperacion).
  - Seccion 9:  profundidad del nodo y presupuesto de acceso.
  - Seccion 14: auditoria e indicadores (giros simples, casos LL/RR/LR/RL).
  - Seccion 16: casos minimos de rotaciones y recuperacion con desbalances
    mayores que 2.
"""

import math
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structures.avl_tree import AVLTree
from structures.tree_key import TreeKey


class EventoDePrueba:
    """
    Doble de prueba minimo para no depender de SeismicEvent.

    Expone unicamente lo que AVLNode y AVLTree necesitan: event_id,
    priority, magnitude, revision y build_key(). Al ser un objeto mutable
    comun (no __slots__ con validacion), permite simular correcciones sin
    pasar por las reglas de negocio, que se prueban aparte en
    test_priority.py.
    """

    def __init__(self, event_id: int, priority: int, magnitude: float, revision: int = 1) -> None:
        self.event_id = event_id
        self.priority = priority
        self.magnitude = magnitude
        self.revision = revision

    def build_key(self) -> TreeKey:
        """Construye K = (P, M, I) igual que SeismicEvent.build_key()."""
        return TreeKey(priority=self.priority, magnitude=self.magnitude, event_id=self.event_id)

    def __repr__(self) -> str:
        return f"EventoDePrueba(id={self.event_id}, P={self.priority}, M={self.magnitude})"


# ----------------------------------------------------------------------
# Helpers de construccion
# ----------------------------------------------------------------------

def crear_evento(valor: int, prioridad: int = 2) -> EventoDePrueba:
    """
    Crea un evento de prueba cuyo orden depende solo de `valor`: misma
    prioridad para todos y magnitud igual al valor, de modo que la
    posicion en el AVL queda determinada unicamente por el identificador.
    """
    return EventoDePrueba(event_id=valor, priority=prioridad, magnitude=float(valor))


def clave_de(valor: int, prioridad: int = 2) -> TreeKey:
    """Clave que corresponde exactamente al evento de crear_evento(valor)."""
    return TreeKey(priority=prioridad, magnitude=float(valor), event_id=valor)


def construir(ids, estres: bool = False) -> AVLTree:
    """Inserta un evento por cada id de `ids`, en el orden dado."""
    arbol = AVLTree()
    arbol.stress_mode = estres
    for i in ids:
        arbol.insert(crear_evento(i))
    return arbol


# ----------------------------------------------------------------------
# Helpers de auditoria (independientes del estado cacheado del arbol)
# ----------------------------------------------------------------------

def auditar(nodo):
    """
    Recalcula la altura de cada nodo DESDE CERO (sin confiar en
    node.height) y reporta los nodos cuyo factor de balance excede lo
    permitido.

    Devuelve (altura_real_del_subarbol, lista_de_desbalances), donde cada
    desbalance es la tupla (clave, factor_balance) de un nodo con
    |factor_balance| > 1.
    """
    desbalances = []

    def _altura(n):
        if n is None:
            return -1
        h_izq = _altura(n.left)
        h_der = _altura(n.right)
        fb = h_izq - h_der
        if abs(fb) > 1:
            desbalances.append((n.key, fb))
        return 1 + max(h_izq, h_der)

    altura_real = _altura(nodo)
    return altura_real, desbalances


def orden_bst_global(nodo, minimo=None, maximo=None) -> bool:
    """
    Verifica que TODO el subarbol respete el orden BST global: cada clave
    debe estar estrictamente entre las cotas heredadas de sus ancestros,
    no solo ser mayor o menor que su padre inmediato.

    Seccion 14: "No basta con comprobar que cada hijo inmediato este en
    el lado correcto."
    """
    if nodo is None:
        return True
    if minimo is not None and not (nodo.key > minimo):
        return False
    if maximo is not None and not (nodo.key < maximo):
        return False
    return (
        orden_bst_global(nodo.left, minimo, nodo.key)
        and orden_bst_global(nodo.right, nodo.key, maximo)
    )


def claves_inorden(nodo):
    """Recorrido inorden: debe producir claves ascendentes (seccion 5)."""
    if nodo is None:
        return []
    return claves_inorden(nodo.left) + [nodo.key] + claves_inorden(nodo.right)


def contar_nodos(nodo) -> int:
    if nodo is None:
        return 0
    return 1 + contar_nodos(nodo.left) + contar_nodos(nodo.right)


def alturas_almacenadas_son_correctas(nodo) -> bool:
    """Compara node.height (valor cacheado) contra la altura de sus hijos."""
    if nodo is None:
        return True
    h_izq = nodo.left.height if nodo.left else -1
    h_der = nodo.right.height if nodo.right else -1
    if nodo.height != 1 + max(h_izq, h_der):
        return False
    return (
        alturas_almacenadas_son_correctas(nodo.left)
        and alturas_almacenadas_son_correctas(nodo.right)
    )


def identidades_por_id(nodo) -> dict:
    """Mapa event_id -> identidad de python (id()) del objeto evento."""
    resultado = {}

    def _recorrer(n):
        if n is None:
            return
        resultado[n.event_id] = id(n.event)
        _recorrer(n.left)
        _recorrer(n.right)

    _recorrer(nodo)
    return resultado


def cota_altura_avl(n: int) -> int:
    """
    Cota superior clasica de la altura de un AVL con n nodos (formula de
    Adelson-Velskii y Landis, tambien citada por Knuth): un AVL nunca es
    mas alto que aproximadamente 1.44 * log2(n).
    """
    if n <= 0:
        return -1
    return math.floor(1.4405 * math.log2(n + 2) - 0.3277)


# ----------------------------------------------------------------------
# Grupo 1 — los 4 casos de rotacion, con verificacion del contador
# ----------------------------------------------------------------------

class TestCasosDeRotacion:
    """Seccion 14: "Casos LL, RR, LR y RL atendidos, junto con giros simples"."""

    def test_caso_ll_rota_a_la_derecha(self):
        """Insercion descendente [3, 2, 1] desbalancea izquierda-izquierda."""
        arbol = construir([3, 2, 1])
        assert arbol.root.event_id == 2
        assert arbol.root.left.event_id == 1
        assert arbol.root.right.event_id == 3
        assert arbol.rotations_ll == 1
        assert (arbol.rotations_rr, arbol.rotations_lr, arbol.rotations_rl) == (0, 0, 0)
        assert arbol.simple_turns_right == 1
        assert arbol.simple_turns_left == 0

    def test_caso_rr_rota_a_la_izquierda(self):
        """Insercion ascendente [1, 2, 3] desbalancea derecha-derecha."""
        arbol = construir([1, 2, 3])
        assert arbol.root.event_id == 2
        assert arbol.root.left.event_id == 1
        assert arbol.root.right.event_id == 3
        assert arbol.rotations_rr == 1
        assert (arbol.rotations_ll, arbol.rotations_lr, arbol.rotations_rl) == (0, 0, 0)
        assert arbol.simple_turns_left == 1
        assert arbol.simple_turns_right == 0

    def test_caso_lr_gira_izquierda_y_luego_derecha(self):
        """[3, 1, 2]: el hijo izquierdo (1) queda pesado a la derecha."""
        arbol = construir([3, 1, 2])
        assert arbol.root.event_id == 2
        assert arbol.root.left.event_id == 1
        assert arbol.root.right.event_id == 3
        assert arbol.rotations_lr == 1
        assert (arbol.rotations_ll, arbol.rotations_rr, arbol.rotations_rl) == (0, 0, 0)
        assert arbol.simple_turns_left == 1
        assert arbol.simple_turns_right == 1

    def test_caso_rl_gira_derecha_y_luego_izquierda(self):
        """[1, 3, 2]: el hijo derecho (3) queda pesado a la izquierda."""
        arbol = construir([1, 3, 2])
        assert arbol.root.event_id == 2
        assert arbol.root.left.event_id == 1
        assert arbol.root.right.event_id == 3
        assert arbol.rotations_rl == 1
        assert (arbol.rotations_ll, arbol.rotations_rr, arbol.rotations_lr) == (0, 0, 0)
        assert arbol.simple_turns_left == 1
        assert arbol.simple_turns_right == 1


# ----------------------------------------------------------------------
# Grupo 2 — direccion segun la comparacion de claves (tabla de la seccion 5)
# ----------------------------------------------------------------------

class TestDireccionSegunClave:
    """
    Replica la tabla de ejemplo de la seccion 5: frente a un nodo raiz con
    clave (3, 5.2, 10), verifica hacia que lado desciende cada clave
    entrante.
    """

    @pytest.mark.parametrize(
        "prioridad, magnitud, identificador, lado_esperado",
        [
            (2, 5.8, 20, "izquierda"),  # prioridad 2 < 3, aunque 5.8 > 5.2
            (3, 6.1, 30, "derecha"),    # empatan prioridad; 6.1 > 5.2
            (3, 5.2, 5, "izquierda"),   # empatan prioridad y magnitud; 5 < 10
            (3, 5.2, 25, "derecha"),    # empatan prioridad y magnitud; 25 > 10
        ],
    )
    def test_direccion_frente_a_clave_referencia(self, prioridad, magnitud, identificador, lado_esperado):
        arbol = AVLTree()
        arbol.insert(EventoDePrueba(event_id=10, priority=3, magnitude=5.2))
        arbol.insert(EventoDePrueba(event_id=identificador, priority=prioridad, magnitude=magnitud))

        if lado_esperado == "izquierda":
            assert arbol.root.left is not None and arbol.root.left.event_id == identificador
            assert arbol.root.right is None
        else:
            assert arbol.root.right is not None and arbol.root.right.event_id == identificador
            assert arbol.root.left is None


# ----------------------------------------------------------------------
# Grupo 3 — eliminacion con 0, 1 y 2 hijos, raiz, clave inexistente, vaciado
# ----------------------------------------------------------------------

class TestEliminacion:
    def test_eliminar_hoja_sin_hijos(self):
        arbol = construir([2, 1, 3])  # ya balanceado: raiz=2, hijos 1 y 3
        arbol.delete(clave_de(1))
        assert arbol.size == 2
        assert contar_nodos(arbol.root) == 2
        assert claves_inorden(arbol.root) == [clave_de(2), clave_de(3)]

    def test_eliminar_nodo_con_un_solo_hijo(self):
        """
        ids [2, 1, 4, 3]: en modo normal el nodo 4 termina con un unico
        hijo (el 3). Al eliminar 4 debe quedar 3 ocupando directamente su
        lugar.
        """
        arbol = construir([2, 1, 4, 3])
        arbol.delete(clave_de(4))
        assert arbol.size == 3
        assert claves_inorden(arbol.root) == [clave_de(1), clave_de(2), clave_de(3)]
        _, desbalances = auditar(arbol.root)
        assert desbalances == []

    def test_eliminar_raiz_con_dos_hijos_usa_el_sucesor_inorden(self):
        arbol = construir([2, 1, 3])
        evento_sucesor = arbol.root.right.event  # sucesor inorden de la raiz (3)
        arbol.delete(clave_de(2))
        assert arbol.size == 2
        assert arbol.root.event_id == 3
        assert arbol.root.event is evento_sucesor
        assert claves_inorden(arbol.root) == [clave_de(1), clave_de(3)]

    def test_eliminar_clave_inexistente_no_modifica_el_arbol(self):
        arbol = construir([2, 1, 3])
        tamano_antes = arbol.size
        claves_antes = claves_inorden(arbol.root)
        arbol.delete(clave_de(99))
        assert arbol.size == tamano_antes
        assert claves_inorden(arbol.root) == claves_antes

    def test_eliminar_todos_los_nodos_hasta_vaciar(self):
        ids = list(range(1, 11))
        arbol = construir(ids)
        orden_borrado = list(ids)
        random.Random(0).shuffle(orden_borrado)
        for i in orden_borrado:
            arbol.delete(clave_de(i))
            _, desbalances = auditar(arbol.root)
            assert desbalances == []
            assert orden_bst_global(arbol.root)
        assert arbol.root is None
        assert arbol.size == 0
        assert arbol.height == -1


# ----------------------------------------------------------------------
# Grupo 4 — modo estres: aplaza rotaciones, conserva orden BST, |FB| > 2
# ----------------------------------------------------------------------

class TestModoEstres:
    def test_estres_aplaza_todas_las_rotaciones(self):
        arbol = construir(range(1, 11), estres=True)
        assert (arbol.rotations_ll, arbol.rotations_rr, arbol.rotations_lr, arbol.rotations_rl) == (0, 0, 0, 0)
        assert (arbol.simple_turns_left, arbol.simple_turns_right) == (0, 0)

    def test_estres_conserva_el_orden_bst(self):
        arbol = construir(range(1, 11), estres=True)
        assert orden_bst_global(arbol.root)
        assert claves_inorden(arbol.root) == [clave_de(i) for i in range(1, 11)]

    def test_estres_produce_desbalances_mayores_que_dos(self):
        """Una cadena degenerada de 10 nodos debe tener |FB| > 2 en algun nodo."""
        arbol = construir(range(1, 11), estres=True)
        _, desbalances = auditar(arbol.root)
        assert desbalances
        assert any(abs(fb) > 2 for _, fb in desbalances)


# ----------------------------------------------------------------------
# Grupo 5 — recuperacion global
# ----------------------------------------------------------------------

class TestRecuperacionGlobal:
    def test_recupera_desde_un_arbol_degenerado(self):
        arbol = construir(range(1, 32), estres=True)  # cadena de 31 nodos
        arbol.recover_balance()
        _, desbalances = auditar(arbol.root)
        assert desbalances == []

    def test_altura_final_es_logaritmica(self):
        n = 63
        arbol = construir(range(1, n + 1), estres=True)
        arbol.recover_balance()
        assert arbol.height <= cota_altura_avl(n)
        assert arbol.height < n - 1  # muy por debajo de la cadena original

    def test_preserva_el_orden_inorden(self):
        n = 40
        ids = list(range(1, n + 1))
        random.Random(7).shuffle(ids)
        arbol = construir(ids, estres=True)
        arbol.recover_balance()
        assert claves_inorden(arbol.root) == [clave_de(i) for i in range(1, n + 1)]

    def test_preserva_las_identidades_de_los_eventos(self):
        ids = list(range(1, 21))
        arbol = construir(ids, estres=True)
        identidades_antes = identidades_por_id(arbol.root)
        arbol.recover_balance()
        identidades_despues = identidades_por_id(arbol.root)
        assert identidades_antes == identidades_despues

    def test_las_alturas_quedan_consistentes(self):
        arbol = construir(range(1, 25), estres=True)
        arbol.recover_balance()
        assert alturas_almacenadas_son_correctas(arbol.root)

    def test_arbol_vacio_no_falla(self):
        arbol = AVLTree()
        arbol.stress_mode = True
        costo = arbol.recover_balance()
        assert arbol.root is None
        assert arbol.height == -1
        assert arbol.stress_mode is False
        assert costo["ll"] == costo["rr"] == costo["lr"] == costo["rl"] == 0
        assert costo["final_height"] == -1

    def test_arbol_ya_balanceado_no_produce_rotaciones(self):
        arbol = construir([2, 1, 3])  # insertado en modo normal: ya balanceado
        arbol.stress_mode = True      # se activa el modo pero no se inserta nada mas
        costo = arbol.recover_balance()
        assert costo["ll"] == costo["rr"] == costo["lr"] == costo["rl"] == 0
        assert arbol.stress_mode is False


# ----------------------------------------------------------------------
# Grupo 6 — pruebas aleatorias parametrizadas (25 semillas cada una)
# ----------------------------------------------------------------------

class TestAleatorios:
    N = 40

    @pytest.mark.parametrize("semilla", range(25))
    def test_insercion_aleatoria_mantiene_invariantes(self, semilla):
        ids = list(range(1, self.N + 1))
        random.Random(semilla).shuffle(ids)
        arbol = construir(ids)

        assert orden_bst_global(arbol.root)
        _, desbalances = auditar(arbol.root)
        assert desbalances == []
        assert alturas_almacenadas_son_correctas(arbol.root)
        assert contar_nodos(arbol.root) == self.N
        assert arbol.size == self.N

    @pytest.mark.parametrize("semilla", range(25))
    def test_eliminacion_aleatoria_mantiene_invariantes(self, semilla):
        ids_insercion = list(range(1, self.N + 1))
        random.Random(semilla).shuffle(ids_insercion)
        arbol = construir(ids_insercion)

        ids_eliminacion = list(ids_insercion)
        random.Random(semilla + 1000).shuffle(ids_eliminacion)

        mitad = self.N // 2
        for i in ids_eliminacion[:mitad]:
            arbol.delete(clave_de(i))

        # invariantes a mitad de camino, no solo al final
        assert orden_bst_global(arbol.root)
        _, desbalances = auditar(arbol.root)
        assert desbalances == []

        for i in ids_eliminacion[mitad:]:
            arbol.delete(clave_de(i))

        assert arbol.root is None
        assert arbol.size == 0

    @pytest.mark.parametrize("semilla", range(25))
    def test_estres_y_recuperacion_con_orden_aleatorio(self, semilla):
        ids = list(range(1, self.N + 1))
        if semilla % 3 == 0:
            # una de cada tres semillas usa orden ascendente: el peor caso
            # para el modo estres, la cadena mas larga posible.
            pass
        else:
            random.Random(semilla).shuffle(ids)

        arbol = construir(ids, estres=True)
        arbol.recover_balance()

        assert orden_bst_global(arbol.root)
        _, desbalances = auditar(arbol.root)
        assert desbalances == []
        assert alturas_almacenadas_son_correctas(arbol.root)
        assert claves_inorden(arbol.root) == [clave_de(i) for i in range(1, self.N + 1)]
        assert arbol.stress_mode is False


# ----------------------------------------------------------------------
# Grupo 7 — TreeKey: hasheable, normaliza magnitud a 1 decimal
# ----------------------------------------------------------------------

class TestTreeKeyPropiedades:
    def test_es_hasheable_y_sirve_como_llave_de_diccionario(self):
        clave = TreeKey(priority=2, magnitude=5.0, event_id=1)
        mapa = {clave: "evento uno"}
        assert mapa[TreeKey(priority=2, magnitude=5.0, event_id=1)] == "evento uno"

    def test_claves_iguales_producen_el_mismo_hash(self):
        a = TreeKey(priority=1, magnitude=3.3, event_id=7)
        b = TreeKey(priority=1, magnitude=3.3, event_id=7)
        assert a == b
        assert hash(a) == hash(b)

    def test_conjunto_de_claves_deduplica_por_igualdad(self):
        claves = {TreeKey(1, 3.0, 5), TreeKey(1, 3.0, 5), TreeKey(1, 3.0, 6)}
        assert len(claves) == 2

    def test_magnitud_se_normaliza_a_un_decimal(self):
        clave = TreeKey(priority=2, magnitude=5.15, event_id=1)
        assert clave.magnitude == 5.2


# ----------------------------------------------------------------------
# Grupo 8 — el nodo lleva el evento completo, no solo la clave
# ----------------------------------------------------------------------

class TestNodoConservaElEvento:
    def test_el_nodo_guarda_una_referencia_no_una_copia(self):
        evento = crear_evento(1)
        arbol = AVLTree()
        arbol.insert(evento)
        assert arbol.root.event is evento

    def test_los_cambios_en_el_evento_son_visibles_desde_el_nodo(self):
        evento = crear_evento(1)
        arbol = AVLTree()
        arbol.insert(evento)
        evento.magnitude = 9.9
        assert arbol.root.event.magnitude == 9.9

    def test_la_clave_del_nodo_no_cambia_sola(self):
        """
        Seccion 5: la clave es una foto congelada tomada al insertar. Si
        el evento cambia de prioridad despues, el nodo sigue comparando
        con la clave vieja hasta que alguien lo retire y lo reinserte.
        """
        evento = crear_evento(1, prioridad=1)
        arbol = AVLTree()
        arbol.insert(evento)
        clave_original = arbol.root.key

        evento.priority = 3  # simula una correccion que cambiaria P
        evento.revision += 1

        assert arbol.root.key is clave_original
        assert arbol.root.key.priority == 1  # la clave del nodo no se movio

    def test_eliminacion_con_dos_hijos_preserva_la_identidad_del_sucesor(self):
        arbol = construir([2, 1, 3])
        evento_sucesor = arbol.root.right.event  # sucesor inorden de la raiz
        arbol.delete(clave_de(2))
        assert arbol.root.event is evento_sucesor


# ----------------------------------------------------------------------
# Grupo 9 — busqueda: nodos visitados y profundidad
# ----------------------------------------------------------------------

class TestBusqueda:
    def test_devuelve_el_nodo_y_la_cantidad_de_nodos_visitados(self):
        arbol = construir(range(1, 8))  # arbol perfectamente balanceado
        nodo, visitados = arbol.search(clave_de(arbol.root.event_id))
        assert nodo is arbol.root
        assert visitados == 1

    def test_la_raiz_se_visita_con_un_solo_nodo(self):
        arbol = construir([10])
        _, visitados = arbol.search(clave_de(10))
        assert visitados == 1

    def test_clave_inexistente_devuelve_none_y_cuenta_el_camino_recorrido(self):
        arbol = construir(range(1, 8))
        nodo, visitados = arbol.search(clave_de(999))
        assert nodo is None
        assert visitados > 0

    def test_costo_de_busqueda_es_profundidad_mas_uno(self):
        arbol = construir(range(1, 8))
        for i in range(1, 8):
            _, visitados = arbol.search(clave_de(i))
            assert visitados == arbol.get_depth(clave_de(i)) + 1

    def test_profundidad_de_la_raiz_es_cero(self):
        arbol = construir(range(1, 8))
        assert arbol.get_depth(arbol.root.key) == 0

    def test_altura_del_arbol_vacio_es_menos_uno(self):
        assert AVLTree().height == -1


# ----------------------------------------------------------------------
# Grupo 10 — giros elementales: caso simple = 1 giro, caso doble = 2 giros
# ----------------------------------------------------------------------

class TestGirosSimples:
    def test_caso_simple_cuenta_un_solo_giro(self):
        arbol = construir([3, 2, 1])  # LL
        assert arbol.simple_turns_left + arbol.simple_turns_right == 1

    def test_caso_doble_cuenta_dos_giros(self):
        arbol = construir([3, 1, 2])  # LR
        assert arbol.simple_turns_left + arbol.simple_turns_right == 2


# ----------------------------------------------------------------------
# Grupo 11 — recover_balance devuelve el costo y apaga el modo estres
# ----------------------------------------------------------------------

class TestCostoDeRecuperacion:
    def test_recover_balance_devuelve_el_costo_y_apaga_el_modo_estres(self):
        arbol = construir(range(1, 16), estres=True)  # cadena de 15 nodos
        assert arbol.stress_mode is True

        costo = arbol.recover_balance()

        claves_esperadas = ("ll", "rr", "lr", "rl", "simple_turns_left", "simple_turns_right", "final_height")
        for clave_costo in claves_esperadas:
            assert clave_costo in costo
        assert all(costo[k] >= 0 for k in claves_esperadas)
        assert costo["final_height"] == arbol.height
        assert arbol.stress_mode is False

        # Un caso simple aporta un giro elemental; un caso doble aporta dos.
        total_giros = costo["simple_turns_left"] + costo["simple_turns_right"]
        giros_esperados = costo["ll"] + costo["rr"] + 2 * (costo["lr"] + costo["rl"])
        assert total_giros == giros_esperados
