# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The published wheel now contains only the core filter and declares no
  runtime dependencies. The NDJSON harness, seeded bugs, concurrency runner,
  and Accordant spec moved under `tools/` and are development-only.
- `argbuilder` moved from a runtime dependency to the dev dependency group.
- The supported Python floor is now 3.13.
- The package uses Apache-2.0 and ships full PyPI metadata.
- CI builds the wheel and verifies it contains the core package only, with no
  `Requires-Dist` entries and no harness files.

### Added

- `BloomFilter` accepts an optional keyword-only `digest` callable as a test
  seam for forcing collisions or pinning bit positions.
- Property-based tests using Hypothesis.
- Snapshot tests using Syrupy for deterministic filter diagnostics and harness
  transcripts.
- An in-process harness API (`Harness` and `serve`) so most harness tests do
  not start a subprocess.
- `docs/releasing.md`, a release checklist.

## [0.1.0] - 2026-10-31

### Added

- Initial Bloom filter with SHA-256 double hashing and a per-instance lock.
- NDJSON harness and an Accordant spec for sequential and concurrent traces.
- Seeded bugs and a statistical false-positive acceptance test.
