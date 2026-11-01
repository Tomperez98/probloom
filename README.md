# Probloom

A small, thread-safe Bloom filter in Python, with an [Accordant](https://github.com/microsoft/accordant)
spec that judges the membership contract and a Python trace runner that
judges concurrency.

The point of the repository is not just the filter. It is the review workflow:
the spec is short enough to read as the contract, the seeded bugs show which
rule catches which failure, and the concurrency path shows a non-.NET system
being checked by `AllowsConcurrent`.

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/); the Accordant suite additionally needs the .NET SDK 10.

## Quick start

```bash
uv sync --dev
uv run python -c "
from probloom import BloomFilter
f = BloomFilter(capacity=1000, error_rate=0.01)
f.add('alice')
assert 'alice' in f
assert f.contains(b'alice')
f.clear()
assert 'alice' not in f
print('ok')
"
# prints: ok
```

## API

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

## Testing

The one command CI runs:

```bash
./scripts/ci
```

Individually:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check --error-on-warning src tests bugs concurrency
uv run pytest
dotnet test spec/Probloom.Spec.Tests/Probloom.Spec.Tests.csproj
```

The Python suite covers parameter validation, sizing, determinism, the
statistical false-positive rate, the thread-safe stress cases, and the CLI
protocol. The Accordant suite covers the generated sequential cases, the
seeded bugs, and the concurrent trace replay.

The harness's flag surface is built with
[argbuilder](https://pypi.org/project/argbuilder/). `tests/test_cli.py` calls
`cli().debug_assert()` and parses `--impl` through `try_get_matches_from`
without starting a process, so a broken CLI definition fails in the test rather
than in the binding.

## Reading the showcase

Start with [`docs/accordant.md`](docs/accordant.md). It walks through:

- the spec's outcome strings as the contract in words;
- why the spec models the abstract inserted-set and never the bit array;
- the manual clear-cycle case the built-in generator cannot reach;
- the three seeded bugs the spec rejects;
- `always_true`, the bug the spec must pass and the statistical test rejects;
- the generated concurrent cases, the two pinned races, and the
  `AllowsConcurrent` replay.

The contract itself lives in
[`spec/Probloom.Spec.Tests/ProbloomSpec.cs`](spec/Probloom.Spec.Tests/ProbloomSpec.cs).
If the walkthrough and the spec disagree, the spec is right.

## Repository map

```
src/probloom/filter.py              the filter
src/probloom/cli.py                 NDJSON harness for the Accordant binding
tests/                              Python unit, statistical, concurrency, CLI tests
spec/Probloom.Spec.Tests/           Accordant spec, binding, sequential and concurrency tests
concurrency/run_cases.py            executes generated concurrent cases, records traces
bugs/                               deliberately wrong filters (not shipped)
docs/accordant.md                   the reviewer walkthrough
docs/adr/                           decisions that are hard to reverse
GLOSSARY.md                         the canonical vocabulary
```

## Design notes

- [ADR-0001](docs/adr/0001-spec-judges-invariants-statistics-judge-rate.md):
  the spec judges membership invariants; a statistical test judges the rate.
- [ADR-0002](docs/adr/0002-sha256-double-hashing.md): SHA-256 double hashing.
- [ADR-0003](docs/adr/0003-thread-safe-filter.md): a per-instance lock.
- [ADR-0004](docs/adr/0004-concurrency-trace-validation.md): concurrency is
  validated by replaying Python traces.

## Scope

v1 deliberately omits `union`, `intersection`, serialization, persistence, and
a read-optimized lock-free path. The hash derivation is stable within a major
version; there is no wire format yet. Concurrency testing is positive-only:
the project chose not to ship an unsynchronized seeded filter, so the replay
proves the observed interleavings were linearizable, not that every possible
interleaving is safe.
