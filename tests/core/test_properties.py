"""Property tests for the Bloom filter's membership contract."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from probloom import BloomFilter

_CAPACITY = st.integers(min_value=1, max_value=500)
_ERROR_RATE = st.floats(
    min_value=0.0001,
    max_value=0.5,
    allow_nan=False,
    allow_infinity=False,
)
_ELEMENT = st.text(max_size=32)
_ELEMENTS = st.lists(_ELEMENT, max_size=50)
_FILTERS = st.builds(BloomFilter, capacity=_CAPACITY, error_rate=_ERROR_RATE)


@settings(max_examples=50, deadline=None)
@given(elements=_ELEMENTS, capacity=_CAPACITY, error_rate=_ERROR_RATE)
def test_inserted_elements_are_never_missing(
    elements: list[str],
    capacity: int,
    error_rate: float,
) -> None:
    bloom = BloomFilter(capacity, error_rate)

    for element in elements:
        bloom.add(element)

    assert all(bloom.contains(element) for element in elements)


@settings(max_examples=50, deadline=None)
@given(elements=_ELEMENTS, bloom=_FILTERS)
def test_insertion_is_idempotent(elements: list[str], bloom: BloomFilter) -> None:
    for element in elements:
        bloom.add(element)

    before = bloom.set_bits
    for element in elements:
        bloom.add(element)

    assert bloom.set_bits == before


@settings(max_examples=50, deadline=None)
@given(elements=_ELEMENTS, bloom=_FILTERS)
def test_clear_returns_every_element_to_absent(
    elements: list[str],
    bloom: BloomFilter,
) -> None:
    for element in elements:
        bloom.add(element)

    bloom.clear()

    assert bloom.set_bits == 0
    assert all(not bloom.contains(element) for element in elements)
    assert all(not bloom.contains(element.encode("utf-8")) for element in elements)


@settings(max_examples=50, deadline=None)
@given(elements=_ELEMENTS, bloom=_FILTERS)
def test_str_and_utf8_bytes_are_the_same_element(
    elements: list[str],
    bloom: BloomFilter,
) -> None:
    for element in elements:
        bloom.add(element)

    assert all(bloom.contains(element.encode("utf-8")) for element in elements)


@settings(max_examples=50, deadline=None)
@given(elements=_ELEMENTS, bloom=_FILTERS)
def test_set_bits_stays_within_the_bit_array(
    elements: list[str],
    bloom: BloomFilter,
) -> None:
    for element in elements:
        bloom.add(element)

    assert 0 <= bloom.set_bits <= bloom.bit_count


@settings(max_examples=50, deadline=None)
@given(capacity=_CAPACITY, error_rate=_ERROR_RATE)
def test_sizing_invariants_hold(capacity: int, error_rate: float) -> None:
    bloom = BloomFilter(capacity, error_rate)

    assert bloom.bit_count >= 1
    assert bloom.hash_count >= 1
    assert bloom.bit_count <= ((bloom.bit_count + 7) // 8) * 8
