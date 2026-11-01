"""Tests for the Bloom filter's deterministic contract."""

from __future__ import annotations

import math
import subprocess
import sys

import pytest

from probloom import BloomFilter

_DETERMINISM_CODE = """
from probloom import BloomFilter
f = BloomFilter(128, 0.05)
for i in range(100):
    f.add(f"element-{i}")
print(f.bit_count, f.hash_count, f.set_bits)
"""


def test_parameter_validation() -> None:
    with pytest.raises(ValueError, match="capacity must be at least 1"):
        BloomFilter(0, 0.01)
    with pytest.raises(ValueError, match="capacity must be at least 1"):
        BloomFilter(-1, 0.01)
    with pytest.raises(ValueError, match="error_rate must be between 0 and 1"):
        BloomFilter(10, 0.0)
    with pytest.raises(ValueError, match="error_rate must be between 0 and 1"):
        BloomFilter(10, 1.0)
    with pytest.raises(TypeError, match="capacity must be an int"):
        BloomFilter(1.5, 0.01)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="capacity must be an int"):
        BloomFilter(True, 0.01)
    with pytest.raises(TypeError, match="error_rate must be a float"):
        BloomFilter(10, "0.01")  # ty: ignore[invalid-argument-type]


def test_sizing_matches_the_textbook_formula() -> None:
    f = BloomFilter(1000, 0.01)
    expected_m = math.ceil(-1000 * math.log(0.01) / (math.log(2) ** 2))
    expected_k = round((expected_m / 1000) * math.log(2))

    assert f.bit_count == expected_m == 9586
    assert f.hash_count == expected_k == 7
    assert f.capacity == 1000
    assert f.error_rate == 0.01
    assert f.seed == 0
    assert f.bit_count >= 1
    assert f.hash_count >= 1


def test_empty_filter_answers_false() -> None:
    f = BloomFilter(100, 0.01)

    assert f.contains("anything") is False
    assert f.set_bits == 0


def test_inserted_elements_never_disappear() -> None:
    f = BloomFilter(1000, 0.01)
    elements = [f"element-{i}" for i in range(1000)]

    for element in elements:
        f.add(element)

    assert all(f.contains(element) for element in elements)


def test_insertion_is_idempotent() -> None:
    f = BloomFilter(1000, 0.01)
    f.add("alice")
    before = f.set_bits

    f.add("alice")

    assert f.set_bits == before
    assert f.contains("alice")


def test_clear_returns_to_empty() -> None:
    f = BloomFilter(1000, 0.01)
    for element in ("alice", "bob", "ghost"):
        f.add(element)

    f.clear()

    assert f.set_bits == 0
    assert all(not f.contains(element) for element in ("alice", "bob", "ghost", "absent"))


def test_str_and_bytes_are_the_same_element() -> None:
    f = BloomFilter(1000, 0.01)

    f.add("alice")
    assert f.contains(b"alice")

    f.add(b"bob")
    assert f.contains("bob")


def test_no_unicode_normalization() -> None:
    f = BloomFilter(1000, 0.000001)
    composed = "\u00e9"
    decomposed = "e\u0301"

    f.add(composed)

    assert f.contains(composed)
    assert f.contains(composed.encode("utf-8"))
    assert not f.contains(decomposed)


def test_set_bits_stays_within_the_bit_array() -> None:
    f = BloomFilter(1000, 0.01)
    for i in range(2000):
        f.add(f"element-{i}")

    assert 0 <= f.set_bits <= f.bit_count


def test_contains_does_not_mutate() -> None:
    f = BloomFilter(1000, 0.01)
    f.add("alice")
    before = f.set_bits

    f.contains("bob")

    assert f.set_bits == before


def test_membership_operator() -> None:
    f = BloomFilter(1000, 0.01)
    f.add("alice")

    assert "alice" in f
    assert "bob" not in f


def test_invalid_element_type() -> None:
    f = BloomFilter(1000, 0.01)

    with pytest.raises(TypeError, match="element must be str or bytes"):
        f.add(123)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="element must be str or bytes"):
        f.contains(None)  # ty: ignore[invalid-argument-type]


def test_repr() -> None:
    assert repr(BloomFilter(10, 0.5)) == "BloomFilter(capacity=10, error_rate=0.5)"


def test_hashing_is_deterministic_across_processes() -> None:
    def run() -> str:
        return subprocess.check_output(
            [sys.executable, "-c", _DETERMINISM_CODE],
            text=True,
        ).strip()

    assert run() == run()
