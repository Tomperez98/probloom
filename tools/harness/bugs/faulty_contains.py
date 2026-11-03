"""A query that loses one inserted element; the spec must reject the false negative."""

from __future__ import annotations

from probloom import BloomFilter as _BloomFilter, Element


class BloomFilter(_BloomFilter):
    def contains(self, value: Element) -> bool:
        if value == "alice":
            return False
        return super().contains(value)
