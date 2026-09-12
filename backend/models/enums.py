"""
Enumerations for the SismoLab domain model.

These enums define the fixed categories used across the system:
priority levels, attention states, and event lifecycle statuses.
"""

from enum import IntEnum, Enum


class Priority(IntEnum):
    """
    Seismic event priority level, derived from magnitude, depth,
    and populated zone membership. Never set manually.

    Comparison: LOW < MEDIUM < HIGH (1 < 2 < 3).
    Used as the first component of the AVL key K = (P, M, I).
    """
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class AttentionState(str, Enum):
    """
    Whether an active event has been reviewed by an operator.

    - PENDING: default on creation and after any accepted correction.
    - REVIEWED: set explicitly by user action.

    Does NOT affect the AVL key K = (P, M, I).
    """
    PENDING = "pending"
    REVIEWED = "reviewed"


class EventStatus(str, Enum):
    """
    Lifecycle status of a seismic event.

    - ACTIVE: present in the AVL catalog.
    - ARCHIVED: moved to historical storage (still available for
      associations and queries, but not in the active AVL).
    - DELETED: identifier permanently retired; no new reports accepted
      unless the deletion is undone or a version is restored.
    """
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
