"""Snapshot tests for the filter's deterministic diagnostics.

These snapshots pin the SHA-256 layout within a major version. A deliberate
hash change is a major release; update the snapshot in that change and let the
diff be the review.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from probloom import BloomFilter

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


def test_filter_diagnostics_story(snapshot: SnapshotAssertion) -> None:
    bloom = BloomFilter(64, 0.01)
    story: list[dict[str, object]] = []

    for element in ("alice", "bob", "alice", "ghost"):
        bloom.add(element)
        story.append(
            {
                "operation": f"add {element}",
                "set_bits": bloom.set_bits,
                "contains_alice": bloom.contains("alice"),
                "contains_bob": bloom.contains("bob"),
            }
        )

    bloom.clear()
    story.append(
        {
            "operation": "clear",
            "set_bits": bloom.set_bits,
            "contains_alice": bloom.contains("alice"),
            "contains_bob": bloom.contains("bob"),
        }
    )

    assert story == snapshot
