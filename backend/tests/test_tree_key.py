"""
Tests for TreeKey lexicographic comparison.

Uses the exact examples from Section 5 of the specification:
  Reference node key: (3, 5.2, 10)

  | Incoming key    | Direction | Reason                                    |
  |-----------------|-----------|-------------------------------------------|
  | (2, 5.8, 20)    | Left      | Priority 2 < 3, even though 5.8 > 5.2    |
  | (3, 6.1, 30)    | Right     | Same priority, magnitude 6.1 > 5.2       |
  | (3, 5.2, 5)     | Left      | Same P and M; ID 5 < 10                  |
  | (3, 5.2, 25)    | Right     | Same P and M; ID 25 > 10                 |
"""

import sys
import os

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from structures.tree_key import TreeKey


class TestTreeKeyComparison:
    """Verify the lexicographic ordering K = (P, M, I)."""

    def setup_method(self):
        """Reference key from specification example."""
        self.ref = TreeKey(priority=3, magnitude=5.2, event_id=10)

    def test_lower_priority_goes_left(self):
        """(2, 5.8, 20) < (3, 5.2, 10): priority 2 < 3."""
        incoming = TreeKey(priority=2, magnitude=5.8, event_id=20)
        assert incoming < self.ref
        assert not incoming > self.ref
        assert not incoming == self.ref

    def test_same_priority_higher_magnitude_goes_right(self):
        """(3, 6.1, 30) > (3, 5.2, 10): same P, magnitude 6.1 > 5.2."""
        incoming = TreeKey(priority=3, magnitude=6.1, event_id=30)
        assert incoming > self.ref
        assert not incoming < self.ref

    def test_same_priority_same_magnitude_lower_id_goes_left(self):
        """(3, 5.2, 5) < (3, 5.2, 10): same P and M, ID 5 < 10."""
        incoming = TreeKey(priority=3, magnitude=5.2, event_id=5)
        assert incoming < self.ref

    def test_same_priority_same_magnitude_higher_id_goes_right(self):
        """(3, 5.2, 25) > (3, 5.2, 10): same P and M, ID 25 > 10."""
        incoming = TreeKey(priority=3, magnitude=5.2, event_id=25)
        assert incoming > self.ref

    def test_equality_same_key(self):
        """Two keys with identical (P, M, I) are equal."""
        twin = TreeKey(priority=3, magnitude=5.2, event_id=10)
        assert twin == self.ref
        assert not twin != self.ref

    def test_no_two_different_events_equal(self):
        """Different IDs always produce different keys."""
        k1 = TreeKey(priority=1, magnitude=3.0, event_id=100)
        k2 = TreeKey(priority=1, magnitude=3.0, event_id=101)
        assert k1 != k2
        assert k1 < k2

    def test_magnitude_normalization(self):
        """Magnitude is rounded to 1 decimal place."""
        k = TreeKey(priority=2, magnitude=5.15, event_id=1)
        assert k.magnitude == 5.2  # rounds 5.15 -> 5.2

    def test_to_tuple(self):
        """to_tuple returns the (P, M, I) tuple."""
        assert self.ref.to_tuple() == (3, 5.2, 10)

    def test_serialization_roundtrip_dict(self):
        """to_dict -> from_dict produces an equal key."""
        restored = TreeKey.from_dict(self.ref.to_dict())
        assert restored == self.ref

    def test_serialization_roundtrip_list(self):
        """to_list -> from_list produces an equal key."""
        restored = TreeKey.from_list(self.ref.to_list())
        assert restored == self.ref

    def test_inorder_produces_ascending(self):
        """A sorted list of keys produces ascending order (inorder simulation)."""
        keys = [
            TreeKey(1, 2.0, 5),
            TreeKey(1, 3.5, 80),
            TreeKey(2, 4.5, 10),
            TreeKey(2, 5.2, 20),
            TreeKey(3, 6.0, 30),
            TreeKey(3, 6.0, 50),
        ]
        for i in range(len(keys) - 1):
            assert keys[i] < keys[i + 1], (
                f"Expected {keys[i]} < {keys[i+1]}"
            )
