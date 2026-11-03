"""Tests for the NDJSON harness API and its argbuilder definition."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from argbuilder import ArgMatches

from probloom import BloomFilter
from tools.harness.cli import Harness, cli, main, serve

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

REPO_ROOT = Path(__file__).resolve().parents[2]


def encode(requests: list[dict[str, Any]]) -> list[str]:
    return [json.dumps(request) for request in requests]


def run_in_process(
    requests: list[dict[str, Any]],
    *,
    harness: Harness | None = None,
) -> list[dict[str, Any]]:
    output = io.StringIO()
    serve(encode(requests), output, Harness() if harness is None else harness)
    return [json.loads(line) for line in output.getvalue().splitlines()]


def run_subprocess(
    requests: list[dict[str, Any]],
    *args: str,
) -> list[dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.harness.cli", *args],
        input="\n".join(encode(requests)) + "\n",
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return [json.loads(line) for line in completed.stdout.splitlines()]


def test_cli_definition_is_legal_and_parsing_is_pure() -> None:
    command = cli()
    command.debug_assert()

    matches = command.try_get_matches_from(
        ["probloom-harness", "--impl", "tools.harness.bugs.faulty_add"]
    )

    assert isinstance(matches, ArgMatches)
    assert matches.get_one("impl", str) == "tools.harness.bugs.faulty_add"


def test_harness_round_trip() -> None:
    responses = run_in_process(
        [
            {"id": 1, "op": "reset", "capacity": 1000, "error_rate": 0.01},
            {"id": 2, "op": "add", "value": "alice"},
            {"id": 3, "op": "contains", "value": "alice"},
            {"id": 4, "op": "contains", "value": "bob"},
            {"id": 5, "op": "clear"},
            {"id": 6, "op": "contains", "value": "alice"},
            {"id": 7, "op": "stats"},
        ]
    )

    assert responses[0] == {"id": 1, "ok": True}
    assert responses[2]["value"] is True
    assert responses[3]["value"] is False
    assert responses[5]["value"] is False
    assert responses[6]["bit_count"] == 9586
    assert responses[6]["hash_count"] == 7
    assert responses[6]["seed"] == 0
    assert responses[6]["set_bits"] == 0


def test_harness_reports_errors_with_the_request_id() -> None:
    responses = run_in_process([{"id": 1, "op": "reset", "capacity": 0, "error_rate": 0.01}])

    assert responses[0]["id"] == 1
    assert responses[0]["ok"] is False
    assert responses[0]["error"]["type"] == "ValueError"


def test_harness_rejects_non_object_json() -> None:
    output = io.StringIO()
    serve(["[]"], output, Harness())
    response = json.loads(output.getvalue())

    assert response["ok"] is False
    assert "JSON object" in response["error"]["message"]


def test_harness_reports_malformed_json() -> None:
    output = io.StringIO()
    serve(["{not json"], output, Harness())
    response = json.loads(output.getvalue())

    assert response["ok"] is False
    assert response["error"]["type"] == "JSONDecodeError"


def test_harness_skips_blank_lines() -> None:
    output = io.StringIO()
    serve(
        ["", "  ", '{"id": 1, "op": "reset", "capacity": 10, "error_rate": 0.1}', ""],
        output,
        Harness(),
    )

    assert output.getvalue() == '{"id":1,"ok":true}\n'


def test_harness_requires_reset() -> None:
    responses = run_in_process([{"id": 1, "op": "add", "value": "alice"}])

    assert responses[0]["ok"] is False
    assert "reset" in responses[0]["error"]["message"]


def test_harness_uses_the_injected_factory() -> None:
    calls: list[tuple[int, float]] = []

    def factory(capacity: int, error_rate: float) -> BloomFilter:
        calls.append((capacity, error_rate))
        return BloomFilter(capacity, error_rate)

    response = Harness(factory).handle(
        {"id": 1, "op": "reset", "capacity": 1000, "error_rate": 0.01}
    )

    assert response == {"id": 1, "ok": True}
    assert calls == [(1000, 0.01)]


def test_main_accepts_injected_streams() -> None:
    output = io.StringIO()

    exit_code = main(
        [],
        lines=['{"id": 1, "op": "reset", "capacity": 10, "error_rate": 0.1}'],
        output=output,
    )

    assert exit_code == 0
    assert json.loads(output.getvalue()) == {"id": 1, "ok": True}


def test_module_entrypoint_round_trip() -> None:
    responses = run_subprocess(
        [
            {"id": 1, "op": "reset", "capacity": 1000, "error_rate": 0.01},
            {"id": 2, "op": "add", "value": "alice"},
            {"id": 3, "op": "contains", "value": "alice"},
        ]
    )

    assert responses[2]["value"] is True


def test_harness_transcript_snapshot(snapshot: SnapshotAssertion) -> None:
    responses = run_in_process(
        [
            {"id": 1, "op": "reset", "capacity": 64, "error_rate": 0.01},
            {"id": 2, "op": "add", "value": "alice"},
            {"id": 3, "op": "add", "value": "bob"},
            {"id": 4, "op": "contains", "value": "alice"},
            {"id": 5, "op": "contains", "value": "ghost"},
            {"id": 6, "op": "stats"},
            {"id": 7, "op": "clear"},
            {"id": 8, "op": "stats"},
        ]
    )

    assert responses == snapshot


def test_harness_error_snapshot(snapshot: SnapshotAssertion) -> None:
    responses = run_in_process(
        [
            {"id": 1, "op": "add", "value": "alice"},
            {"id": 2, "op": "reset", "capacity": 0, "error_rate": 0.01},
            {"id": 3, "op": "reset", "capacity": 10, "error_rate": 0.01},
            {"id": 4, "op": "unknown"},
        ]
    )

    assert responses == snapshot


def test_module_entrypoint_supports_faulty_implementations() -> None:
    responses = run_subprocess(
        [
            {"id": 1, "op": "reset", "capacity": 1000, "error_rate": 0.01},
            {"id": 2, "op": "add", "value": "alice"},
            {"id": 3, "op": "contains", "value": "alice"},
        ],
        "--impl",
        "tools.harness.bugs.faulty_contains",
    )

    assert responses[2]["value"] is False
