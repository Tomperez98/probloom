"""Line-oriented JSON harness used by the Accordant binding.

The harness is development tooling, not part of the published package. It has
two seams so tests can drive it without a subprocess: ``Harness`` owns request
handling and accepts an injectable filter factory, and ``serve`` owns the line
protocol and accepts arbitrary text streams.

The flag surface is built with argbuilder, so a broken CLI definition fails in
a test instead of in the binding's process.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol, TextIO, cast

from argbuilder import Arg, ArgMatches, Command

from probloom import BloomFilter, __version__


class Filter(Protocol):
    """The small filter surface the harness relies on."""

    @property
    def capacity(self) -> int: ...

    @property
    def error_rate(self) -> float: ...

    @property
    def bit_count(self) -> int: ...

    @property
    def hash_count(self) -> int: ...

    @property
    def seed(self) -> int: ...

    @property
    def set_bits(self) -> int: ...

    def add(self, value: str) -> None: ...

    def contains(self, value: str) -> bool: ...

    def clear(self) -> None: ...


type FilterFactory = Callable[[int, float], Filter]


def _default_factory(capacity: int, error_rate: float) -> Filter:
    return BloomFilter(capacity, error_rate)


def cli() -> Command:
    return (
        Command("probloom-harness")
        .version(__version__)
        .about("Line-oriented JSON harness used by the Accordant binding.")
        .arg(
            Arg("impl")
            .long("impl")
            .help("import path of an alternative BloomFilter (seeded test faults)")
        )
    )


def _matches(argv: list[str] | None) -> ArgMatches:
    command = cli()
    if argv is None:
        return command.get_matches()
    return command.get_matches_from(["probloom-harness", *argv])


def _load_factory(impl: str | None) -> FilterFactory:
    if impl is None:
        return _default_factory
    module = importlib.import_module(impl)
    return cast("FilterFactory", module.BloomFilter)


def _error(request_id: object, exc: Exception) -> dict[str, Any]:
    return {
        "id": request_id,
        "ok": False,
        "error": {"type": type(exc).__name__, "message": str(exc)},
    }


class Harness:
    """Own one filter and turn one request into one response."""

    def __init__(self, factory: FilterFactory = _default_factory) -> None:
        self._factory = factory
        self._filter: Filter | None = None

    def handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Handle a parsed request. Failures become an ``ok: false`` response."""
        request_id = request.get("id")
        try:
            payload = self._dispatch(request)
        except Exception as exc:  # noqa: BLE001 - the harness reports every failure
            return _error(request_id, exc)
        return {"id": request_id, "ok": True, **payload}

    def _dispatch(self, request: Mapping[str, Any]) -> dict[str, Any]:
        op = request["op"]
        if op == "reset":
            self._filter = self._factory(
                int(request["capacity"]),
                float(request["error_rate"]),
            )
            return {}
        current = self._require_filter()
        if op == "add":
            current.add(request["value"])
            return {}
        if op == "contains":
            return {"value": current.contains(request["value"])}
        if op == "clear":
            current.clear()
            return {}
        if op == "stats":
            return {
                "capacity": current.capacity,
                "error_rate": current.error_rate,
                "bit_count": current.bit_count,
                "hash_count": current.hash_count,
                "seed": current.seed,
                "set_bits": current.set_bits,
            }
        raise ValueError(f"unknown operation: {op!r}")

    def _require_filter(self) -> Filter:
        if self._filter is None:
            raise RuntimeError("reset must be the first operation")
        return self._filter


def _handle_line(raw: str, harness: Harness) -> dict[str, Any]:
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _error(None, exc)
    if not isinstance(loaded, dict):
        return _error(None, TypeError("request must be a JSON object"))
    return harness.handle(loaded)


def serve(
    lines: Iterable[str],
    output: TextIO,
    harness: Harness,
) -> None:
    """Read one request per line, write one response per line."""
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        response = _handle_line(raw, harness)
        output.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        output.flush()


def main(
    argv: list[str] | None = None,
    *,
    lines: Iterable[str] | None = None,
    output: TextIO | None = None,
) -> int:
    matches = _matches(argv)
    impl = matches.get_one("impl", str)
    harness = Harness(_load_factory(impl))
    serve(
        sys.stdin if lines is None else lines,
        sys.stdout if output is None else output,
        harness,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
