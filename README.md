# Probloom

A small, thread-safe Bloom filter in Python with **no runtime dependencies**.

```python
from probloom import BloomFilter

f = BloomFilter(capacity=1000, error_rate=0.01)
f.add("alice")
assert "alice" in f
assert f.contains(b"alice")
f.clear()
assert "alice" not in f
```

Probloom stores membership in a fixed bit array: `false` means definitely
absent, `true` means maybe present. It accepts `str` (UTF-8) and `bytes`,
hashes with SHA-256 double hashing, and is thread-safe: `add`, `contains`, and
`clear` are linearizable.

## Install

Requires Python 3.13 or newer.

```bash
pip install probloom
# or
uv add probloom
```

The published wheel contains only the filter and its type marker. It declares
no runtime dependencies.

## Use

```python
from probloom import BloomFilter

f = BloomFilter(capacity=1000, error_rate=0.01)
f.add("alice")  # idempotent; accepts str or bytes
f.contains("alice")  # True
"alice" in f  # same as contains
f.clear()  # back to the empty filter

f.bit_count  # m, the number of bits
f.hash_count  # k, the number of positions per element
f.set_bits  # diagnostic: bits currently set
f.seed  # 0 in v1
```

Elements are UTF-8 bytes with no Unicode normalization. Hashing is SHA-256
double hashing with a fixed seed, so bit patterns are reproducible across
processes. A filter instance is thread-safe: `add`, `contains`, and `clear`
are linearizable.

Insertion beyond `capacity` is allowed; the false-positive rate degrades. The
configured `error_rate` is a target at capacity, not a per-query guarantee.

### Test seam

`BloomFilter` accepts an optional keyword-only `digest` callable. The default
is SHA-256; tests can inject a digest to force collisions or pin bit positions
without copying private state:

```python
def fixed_digest(_data: bytes) -> bytes:
    return bytes(32)


f = BloomFilter(1000, 0.01, digest=fixed_digest)
f.add("alice")
assert f.contains("bob")  # every element hashes to the same positions
```

A digest must return at least 16 bytes. Production callers should leave the
default alone: the reproducible bit-pattern promise applies to SHA-256.
See [ADR-0006](docs/adr/0006-injectable-digest-seam.md).

## Testing

The one command CI runs:

```bash
./scripts/ci
```

It syncs the dev environment, lints, type-checks, runs the Python suite,
builds the wheel, verifies the wheel has zero runtime dependencies and does not
contain the harness, then runs the .NET Accordant suite.

Individually:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check --error-on-warning src tests tools scripts
uv run pytest
uv build --out-dir dist
uv run python scripts/check_wheel.py
dotnet test tools/spec/Probloom.Spec.Tests/Probloom.Spec.Tests.csproj
```

The Python suite covers unit and property tests, the statistical false-positive
rate, thread-safe stress cases, and the harness. Snapshot tests use
[Syrupy](https://github.com/syrupy-project/syrupy) for deterministic filter
diagnostics and harness transcripts. After an intentional output change, update
and review the snapshots:

```bash
uv run pytest --snapshot-update -m syrupy_snapshot
```

The harness is split into `Harness` (request handling with an injectable filter
factory) and `serve` (the line protocol with injectable text streams), so most
harness tests run in-process; one subprocess test covers the module entrypoint.
The Accordant suite covers generated sequential cases, the seeded bugs, and the
concurrent trace replay.

The harness's flag surface is built with
[argbuilder](https://pypi.org/project/argbuilder/), a dev-only dependency.
`tests/harness/test_cli.py` calls `cli().debug_assert()` and parses `--impl`
through `try_get_matches_from` without starting a process, so a broken CLI
definition fails in the test rather than in the binding.

## Reading the showcase

Start with [`docs/accordant.md`](docs/accordant.md). It walks through:

- the spec's outcome strings as the contract in words;
- the invariant map: what the spec asserts, what tests check, and what is
  deliberately not an invariant;
- why the spec models the abstract inserted-set and never the bit array;
- the manual clear-cycle case the built-in generator cannot reach;
- the seeded bugs the spec rejects;
- `always_true`, the bug the spec must pass and the statistical test rejects;
- the generated concurrent cases, the two pinned races, and the
  `AllowsConcurrent` replay.

The contract itself lives in
[`tools/spec/Probloom.Spec.Tests/ProbloomSpec.cs`](tools/spec/Probloom.Spec.Tests/ProbloomSpec.cs).
If the walkthrough and the spec disagree, the spec is right.

## Repository map

```
src/probloom/filter.py              the published filter
src/probloom/__init__.py            public exports and metadata version
tests/core/                         unit, property, statistical, concurrency tests
tests/harness/                      in-process harness and entrypoint tests
tools/harness/cli.py                NDJSON harness for the Accordant binding (not shipped)
tools/harness/bugs/                 deliberately wrong filters (not shipped)
tools/harness/concurrency.py        executes generated concurrent cases (not shipped)
tools/spec/                         Accordant spec, binding, sequential and concurrency tests
docs/accordant.md                   the reviewer walkthrough
docs/releasing.md                   release checklist
docs/adr/                           decisions that are hard to reverse
GLOSSARY.md                         the canonical vocabulary
```

The published distribution is only `src/probloom/`. Everything under `tools/`
is development tooling and stays out of the wheel.

## Design notes

- [ADR-0001](docs/adr/0001-spec-judges-invariants-statistics-judge-rate.md):
  the spec judges membership invariants; a statistical test judges the rate.
- [ADR-0002](docs/adr/0002-sha256-double-hashing.md): SHA-256 double hashing.
- [ADR-0003](docs/adr/0003-thread-safe-filter.md): a per-instance lock.
- [ADR-0004](docs/adr/0004-concurrency-trace-validation.md): concurrency is
  validated by replaying Python traces.
- [ADR-0005](docs/adr/0005-ship-only-the-filter.md): ship the filter only; keep
  the harness and spec under `tools/`.
- [ADR-0006](docs/adr/0006-injectable-digest-seam.md): an optional digest
  callable is the test seam for bit positions.

## Scope

v1 deliberately omits `union`, `intersection`, serialization, persistence, and
a read-optimized lock-free path. The hash derivation is stable within a major
version; there is no wire format yet. Concurrency testing is positive-only:
the project chose not to ship an unsynchronized seeded filter, so the replay
proves the observed interleavings were linearizable, not that every possible
interleaving is safe.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
