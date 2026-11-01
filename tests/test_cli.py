"""Tests for the NDJSON CLI and its argbuilder definition."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from argbuilder import ArgMatches

from probloom.cli import cli

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cli_definition_is_legal_and_parsing_is_pure() -> None:
    command = cli()
    command.debug_assert()

    matches = command.try_get_matches_from(["probloom", "--impl", "bugs.faulty_add"])

    assert isinstance(matches, ArgMatches)
    assert matches.get_one("impl", str) == "bugs.faulty_add"


def run_cli(requests: list[dict[str, Any]], *, impl: str | None = None) -> list[dict[str, Any]]:
    args = [sys.executable, "-m", "probloom.cli"]
    if impl is not None:
        args.extend(["--impl", impl])

    completed = subprocess.run(
        args,
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return [json.loads(line) for line in completed.stdout.splitlines()]


def test_cli_round_trip() -> None:
    responses = run_cli(
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


def test_cli_reports_errors() -> None:
    responses = run_cli([{"id": 1, "op": "reset", "capacity": 0, "error_rate": 0.01}])

    assert responses[0]["ok"] is False
    assert responses[0]["error"]["type"] == "ValueError"


def test_cli_rejects_non_object_json() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "probloom.cli"],
        input="[]\n",
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    response = json.loads(completed.stdout)

    assert response["ok"] is False
    assert "JSON object" in response["error"]["message"]


def test_cli_requires_reset() -> None:
    responses = run_cli([{"id": 1, "op": "add", "value": "alice"}])

    assert responses[0]["ok"] is False
    assert "reset" in responses[0]["error"]["message"]


def test_cli_supports_faulty_implementations() -> None:
    responses = run_cli(
        [
            {"id": 1, "op": "reset", "capacity": 1000, "error_rate": 0.01},
            {"id": 2, "op": "add", "value": "alice"},
            {"id": 3, "op": "contains", "value": "alice"},
        ],
        impl="bugs.faulty_contains",
    )

    assert responses[2]["value"] is False
