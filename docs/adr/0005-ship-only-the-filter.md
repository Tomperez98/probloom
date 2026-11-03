# Ship only the filter; keep the harness and spec under `tools/`

The published distribution used to include `probloom.cli` and declare
`argbuilder` as a runtime dependency. The CLI is an NDJSON process used only by
the C# Accordant binding and the repository's tests. A user installing a Bloom
filter should not install an argument parser or a test harness.

The published `probloom` package now contains only `probloom/__init__.py`,
`probloom/filter.py`, and `probloom/py.typed`, and declares no runtime
dependencies. The NDJSON harness, seeded bugs, concurrency runner, and C#
spec live under `tools/` and are development-only. `argbuilder` moved to the
dev dependency group.

`scripts/ci` builds the wheel and runs `scripts/check_wheel.py`, which fails if
the wheel declares any `Requires-Dist`, omits a core file, or contains
`probloom/cli.py`. This makes the packaging boundary a checked invariant rather
than a convention.

The consequences are deliberate: the harness runs from the repository with
`uv run python -m tools.harness.cli` and is not available to installed users;
`probloom.__version__` reads the installed package metadata, with a development
fallback for an uninstalled source checkout; and every future harness change
stays out of the release artifact unless the check is weakened in review.
