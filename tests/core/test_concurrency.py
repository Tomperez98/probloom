"""Threaded stress tests for the per-instance lock."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from probloom import BloomFilter

_WORKERS = 8
_ROUNDS = 10


def test_concurrent_inserts_do_not_lose_bits() -> None:
    for _ in range(_ROUNDS):
        f = BloomFilter(4096, 0.01)
        elements = [f"element-{i}" for i in range(200)]
        chunks = [elements[i::_WORKERS] for i in range(_WORKERS)]
        barrier = threading.Barrier(_WORKERS)

        def insert(
            chunk: list[str],
            bloom: BloomFilter = f,
            gate: threading.Barrier = barrier,
        ) -> None:
            gate.wait()
            for element in chunk:
                bloom.add(element)

        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            list(pool.map(insert, chunks))

        missing = [element for element in elements if not f.contains(element)]
        assert missing == [], f"lost {len(missing)} insertions"


def test_concurrent_reads_are_safe() -> None:
    f = BloomFilter(4096, 0.01)
    for i in range(100):
        f.add(f"element-{i}")
    barrier = threading.Barrier(_WORKERS)

    def read(_: int) -> bool:
        barrier.wait()
        return all(f.contains(f"element-{i}") for i in range(100))

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        results = list(pool.map(read, range(_WORKERS)))

    assert all(results)


def test_concurrent_inserts_and_reads_never_lose_inserted_elements() -> None:
    f = BloomFilter(4096, 0.01)
    inserted = [f"inserted-{i}" for i in range(100)]
    readers_see: list[bool] = []

    def insert() -> None:
        for element in inserted:
            f.add(element)
        readers_see.append(all(f.contains(element) for element in inserted))

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(insert)
        pool.submit(lambda: [f.contains(f"probe-{i}") for i in range(1000)])
        writer.result()

    assert readers_see == [True]
