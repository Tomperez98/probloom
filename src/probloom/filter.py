"""A textbook Bloom filter with deterministic hashing and a small surface."""

from __future__ import annotations

import hashlib
import math
import threading

type Element = str | bytes

_SEED = 0


def _as_bytes(value: Element) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, bytes):
        return value
    raise TypeError(f"element must be str or bytes, got {type(value).__name__}")


class BloomFilter:
    """A probabilistic set with no false negatives.

    A filter instance is thread-safe: ``add``, ``contains``, and ``clear`` are
    linearizable. The configured ``error_rate`` is a target at ``capacity``,
    not a per-query guarantee.
    """

    def __init__(self, capacity: int, error_rate: float) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an int")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if isinstance(error_rate, bool) or not isinstance(error_rate, (int, float)):
            raise TypeError("error_rate must be a float")
        if not 0.0 < float(error_rate) < 1.0:
            raise ValueError("error_rate must be between 0 and 1, exclusive")

        self._capacity = capacity
        self._error_rate = float(error_rate)
        self._seed = _SEED
        self._bit_count = max(
            1, math.ceil(-capacity * math.log(self._error_rate) / (math.log(2) ** 2))
        )
        self._hash_count = max(1, round((self._bit_count / capacity) * math.log(2)))
        self._byte_count = (self._bit_count + 7) // 8
        self._bits = bytearray(self._byte_count)
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def error_rate(self) -> float:
        return self._error_rate

    @property
    def bit_count(self) -> int:
        """The number of bits in the filter (m)."""
        return self._bit_count

    @property
    def hash_count(self) -> int:
        """The number of hash positions per element (k)."""
        return self._hash_count

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def set_bits(self) -> int:
        """The number of bits currently set. Useful for diagnostics."""
        with self._lock:
            return sum(byte.bit_count() for byte in self._bits)

    def _indices(self, data: bytes) -> tuple[int, ...]:
        digest = hashlib.sha256(data).digest()
        h1 = int.from_bytes(digest[:8], "big") ^ self._seed
        h2 = (int.from_bytes(digest[8:16], "big") ^ self._seed) or 1
        return tuple((h1 + i * h2) % self._bit_count for i in range(self._hash_count))

    def add(self, value: Element) -> None:
        """Insert an element. Insertion is idempotent."""
        indices = self._indices(_as_bytes(value))
        with self._lock:
            bits = self._bits
            for index in indices:
                bits[index >> 3] |= 1 << (index & 7)

    def contains(self, value: Element) -> bool:
        """Return false only when the element was definitely not inserted."""
        indices = self._indices(_as_bytes(value))
        with self._lock:
            bits = self._bits
            return all(bits[index >> 3] & (1 << (index & 7)) for index in indices)

    def clear(self) -> None:
        """Return the filter to the empty state."""
        with self._lock:
            self._bits = bytearray(self._byte_count)

    def __contains__(self, value: Element) -> bool:
        """Support ``value in filter`` as a membership query."""
        return self.contains(value)

    def __repr__(self) -> str:
        """Return a short constructor-style representation."""
        return f"BloomFilter(capacity={self._capacity}, error_rate={self._error_rate!r})"
