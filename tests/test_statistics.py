"""Tests for the statistical false-positive promise."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from bugs.always_true import BloomFilter as AlwaysTrue
from probloom import BloomFilter

if TYPE_CHECKING:
    from collections.abc import Callable


class Filter(Protocol):
    def add(self, value: str, /) -> None: ...

    def contains(self, value: str, /) -> bool: ...


def measure_false_positive_rate(
    make_filter: Callable[[], Filter],
    *,
    inserted: int = 1000,
    queries: int = 20_000,
) -> float:
    f = make_filter()
    for i in range(inserted):
        f.add(f"present-{i}")

    hits = sum(f.contains(f"absent-{i}") for i in range(queries))
    return hits / queries


def test_false_positive_rate_is_near_the_configured_rate() -> None:
    rate = measure_false_positive_rate(lambda: BloomFilter(1000, 0.01))

    assert rate <= 0.02, f"observed false-positive rate {rate:.4f} > 0.02"


def test_always_true_violates_the_rate() -> None:
    rate = measure_false_positive_rate(lambda: AlwaysTrue(1000, 0.01))

    assert rate == 1.0
    assert rate > 0.02
