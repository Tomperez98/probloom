"""An insertion that records nothing; the spec must reject a later query."""

from __future__ import annotations

from probloom import BloomFilter as _BloomFilter, Element


class BloomFilter(_BloomFilter):
    def add(self, value: Element) -> None:  # noqa: ARG002
        return None
