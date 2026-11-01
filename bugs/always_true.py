"""A filter that passes the spec and fails the statistical test.

It is correct with respect to the deterministic invariants: empty answers false,
inserted elements answer true, and absent elements may answer true. Its
false-positive rate is 100%, which only the statistical acceptance test sees.
"""

from __future__ import annotations


class BloomFilter:
    def __init__(self, capacity: int, error_rate: float) -> None:
        self._capacity = capacity
        self._error_rate = float(error_rate)
        self._has_any = False

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def error_rate(self) -> float:
        return self._error_rate

    @property
    def bit_count(self) -> int:
        return 1

    @property
    def hash_count(self) -> int:
        return 1

    @property
    def seed(self) -> int:
        return 0

    @property
    def set_bits(self) -> int:
        return 1 if self._has_any else 0

    def add(self, _value: str) -> None:
        self._has_any = True

    def contains(self, _value: str) -> bool:
        return self._has_any

    def clear(self) -> None:
        self._has_any = False
