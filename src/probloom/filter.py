"""A textbook Bloom filter with deterministic hashing and a small surface."""

from __future__ import annotations

import hashlib
import math
import struct
import threading
from collections.abc import Callable

type Element = str | bytes
type DigestFunction = Callable[[bytes], bytes]

_SEED = 0
_MIN_DIGEST_BYTES = 16
# Two big-endian unsigned 64-bit words: the same halves as digest[:8] and
# digest[8:16], without the intermediate slices.
_UNPACK_DIGEST = struct.Struct(">QQ").unpack_from


def _sha256_digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


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

    ``digest`` is an advanced seam for tests: it must turn the UTF-8 element
    bytes into at least 16 bytes and be safe to call concurrently. The default
    is SHA-256. A different digest changes the bit pattern, so the
    reproducibility promise only covers the default; production callers should
    leave it alone.
    """

    def __init__(
        self,
        capacity: int,
        error_rate: float,
        *,
        digest: DigestFunction = _sha256_digest,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an int")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if isinstance(error_rate, bool) or not isinstance(error_rate, (int, float)):
            raise TypeError("error_rate must be a float")
        if not 0.0 < float(error_rate) < 1.0:
            raise ValueError("error_rate must be between 0 and 1, exclusive")
        if not callable(digest):
            raise TypeError("digest must be callable")

        self._capacity = capacity
        self._error_rate = float(error_rate)
        self._seed = _SEED
        self._digest = digest
        self._bit_count = max(
            1, math.ceil(-capacity * math.log(self._error_rate) / (math.log(2) ** 2))
        )
        self._hash_count = max(1, round((self._bit_count / capacity) * math.log(2)))
        self._byte_count = (self._bit_count + 7) // 8
        assert self._bit_count >= 1, "bit_count must be positive"
        assert self._hash_count >= 1, "hash_count must be positive"
        assert (self._byte_count - 1) * 8 < self._bit_count <= self._byte_count * 8, (
            "byte_count must exactly cover the bit array"
        )
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
            count = int.from_bytes(self._bits, "big").bit_count()
        assert 0 <= count <= self._bit_count, "set_bits must stay within the bit array"
        return count

    def _start_and_stride(self, data: bytes) -> tuple[int, int]:
        """Return the first index and the stride between the k positions.

        This is the incremental form of the documented ``(h1 + i*h2) % m``
        derivation: start at ``h1 % m`` and add ``h2 % m``, subtracting ``m``
        when the index wraps. It produces the same positions without a big-int
        multiply and modulo per position.
        """
        digest = self._digest(data)
        if len(digest) < _MIN_DIGEST_BYTES:
            raise ValueError(
                f"digest must return at least {_MIN_DIGEST_BYTES} bytes, got {len(digest)}"
            )
        h1, h2 = _UNPACK_DIGEST(digest)
        h1 ^= self._seed
        h2 = (h2 ^ self._seed) or 1
        bit_count = self._bit_count
        return h1 % bit_count, h2 % bit_count

    def add(self, value: Element) -> None:
        """Insert an element. Insertion is idempotent."""
        index, stride = self._start_and_stride(_as_bytes(value))
        bit_count = self._bit_count
        with self._lock:
            bits = self._bits
            for _ in range(self._hash_count):
                bits[index >> 3] |= 1 << (index & 7)
                index += stride
                if index >= bit_count:
                    index -= bit_count

    def contains(self, value: Element) -> bool:
        """Return false only when the element was definitely not inserted."""
        index, stride = self._start_and_stride(_as_bytes(value))
        bit_count = self._bit_count
        with self._lock:
            bits = self._bits
            for _ in range(self._hash_count):
                if not bits[index >> 3] & (1 << (index & 7)):
                    return False
                index += stride
                if index >= bit_count:
                    index -= bit_count
            return True

    def clear(self) -> None:
        """Return the filter to the empty state."""
        empty = bytearray(self._byte_count)
        with self._lock:
            self._bits = empty

    def __contains__(self, value: Element) -> bool:
        """Support ``value in filter`` as a membership query."""
        return self.contains(value)

    def __repr__(self) -> str:
        """Return a short constructor-style representation."""
        return f"BloomFilter(capacity={self._capacity}, error_rate={self._error_rate!r})"
