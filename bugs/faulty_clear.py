"""A clear that forgets to clear; the spec must reject the empty-filter rule."""

from __future__ import annotations

from probloom import BloomFilter as _BloomFilter


class BloomFilter(_BloomFilter):
    def clear(self) -> None:
        return None
