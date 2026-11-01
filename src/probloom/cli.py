"""Line-oriented JSON harness used by the Accordant binding.

One JSON request per line on stdin, one JSON response per line on stdout. The
filter is created by ``reset`` and then mutated by ``add``/``clear``.

The flag surface is built with argbuilder, so a broken CLI definition fails in
a test instead of in the binding's process.
"""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any

from argbuilder import Arg, ArgMatches, Command

from .filter import BloomFilter


def cli() -> Command:
    return (
        Command("probloom")
        .version("0.1.0")
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
    return command.get_matches_from(["probloom", *argv])


def _load_filter(impl: str | None, capacity: int, error_rate: float) -> Any:
    if impl is None:
        return BloomFilter(capacity, error_rate)
    module = importlib.import_module(impl)
    return module.BloomFilter(capacity, error_rate)


def _error(request_id: Any, exc: Exception) -> dict[str, Any]:
    return {
        "id": request_id,
        "ok": False,
        "error": {"type": type(exc).__name__, "message": str(exc)},
    }


def main(argv: list[str] | None = None) -> int:
    matches = _matches(argv)
    impl = matches.get_one("impl", str)

    current = None
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue

        request: dict[str, Any] = {}
        try:
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise TypeError("request must be a JSON object")
            request = loaded
            request_id = request.get("id")
            op = request["op"]

            if op == "reset":
                current = _load_filter(
                    impl,
                    int(request["capacity"]),
                    float(request["error_rate"]),
                )
                response: dict[str, Any] = {"id": request_id, "ok": True}
            elif current is None:
                raise RuntimeError("reset must be the first operation")
            elif op == "add":
                current.add(request["value"])
                response = {"id": request_id, "ok": True}
            elif op == "contains":
                response = {
                    "id": request_id,
                    "ok": True,
                    "value": current.contains(request["value"]),
                }
            elif op == "clear":
                current.clear()
                response = {"id": request_id, "ok": True}
            elif op == "stats":
                response = {
                    "id": request_id,
                    "ok": True,
                    "capacity": current.capacity,
                    "error_rate": current.error_rate,
                    "bit_count": current.bit_count,
                    "hash_count": current.hash_count,
                    "seed": current.seed,
                    "set_bits": current.set_bits,
                }
            else:
                raise ValueError(f"unknown operation: {op!r}")
        except Exception as exc:  # noqa: BLE001 - the harness reports every failure
            response = _error(request.get("id"), exc)

        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
