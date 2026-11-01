"""Execute Accordant's serialized concurrent cases and record traces.

Accordant generates the cases and judges the traces with ``AllowsConcurrent``.
This runner only executes each segment: a one-call segment runs alone, a
multi-call segment runs on a barrier so the calls actually overlap.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from probloom import BloomFilter


def execute(bloom: BloomFilter, operation: str, request: Any) -> bool:
    if operation == "Add":
        bloom.add(request)
        return True
    if operation == "Contains":
        return bloom.contains(request)
    if operation == "Clear":
        bloom.clear()
        return True
    raise ValueError(f"unknown operation: {operation!r}")


def execute_group(bloom: BloomFilter, calls: list[dict[str, Any]]) -> list[bool]:
    barrier = threading.Barrier(len(calls))
    results: list[bool | None] = [None] * len(calls)

    def run(index: int) -> None:
        call = calls[index]
        operation = call["Input"]["OperationName"]
        request = json.loads(call["Input"]["SerializedRequest"])
        barrier.wait()
        results[index] = execute(bloom, operation, request)

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(run, index) for index in range(len(calls))]
        for future in futures:
            future.result()

    return [bool(result) for result in results]


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute Accordant concurrent cases")
    parser.add_argument("cases", type=Path)
    parser.add_argument("traces", type=Path)
    parser.add_argument("--capacity", type=int, default=64)
    parser.add_argument("--error-rate", type=float, default=0.01)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text())
    traces: list[dict[str, Any]] = []
    groups = 0

    for case in cases:
        bloom = BloomFilter(args.capacity, args.error_rate)
        trace_segments: list[list[dict[str, Any]]] = []

        for segment in case["Segments"]:
            calls = segment["OperationCalls"]
            if len(calls) == 1:
                call = calls[0]
                operation = call["Input"]["OperationName"]
                request = json.loads(call["Input"]["SerializedRequest"])
                response = execute(bloom, operation, request)
                trace_segments.append(
                    [{"operation": operation, "request": request, "response": response}]
                )
            else:
                groups += 1
                responses = execute_group(bloom, calls)
                entries = []
                for call, response in zip(calls, responses, strict=True):
                    entries.append(
                        {
                            "operation": call["Input"]["OperationName"],
                            "request": json.loads(call["Input"]["SerializedRequest"]),
                            "response": response,
                        }
                    )
                trace_segments.append(entries)

        traces.append({"description": case.get("Description"), "segments": trace_segments})

    args.traces.write_text(json.dumps({"cases": traces}, indent=2))
    sys.stdout.write(f"ran {len(traces)} cases with {groups} concurrent groups\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
