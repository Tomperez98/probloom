"""Probloom: a small, thread-safe Bloom filter."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .filter import BloomFilter, DigestFunction, Element

try:
    __version__ = version("probloom")
except PackageNotFoundError:  # pragma: no cover - uninstalled source checkout
    __version__ = "0.0.0.dev0"

__all__ = ["BloomFilter", "DigestFunction", "Element", "__version__"]
