# Reading Probloom's Accordant spec

This is a reviewer's walkthrough, not a second contract. The contract is
[`spec/Probloom.Spec.Tests/ProbloomSpec.cs`](../spec/Probloom.Spec.Tests/ProbloomSpec.cs).
If this page and the spec disagree, the spec is right.

## The spec is the contract

The spec has three operations over one small state:

```csharp
[State]
public partial class FilterState
{
    public Dictionary<string, bool> Inserted { get; set; } = new();
}
```

`Inserted` is the abstract set of elements the spec remembers. It is not the
filter's bit array. The spec never computes a hash or sets a bit; it only says
which responses are correct and how the abstract set moves.

The `Apply` methods are short enough to check by reading. The key branch is
`Contains`:

```csharp
if (state.Inserted.ContainsKey(element))
{
    return Expect.That<bool>(
            r => r,
            $"'{element}' was inserted → contains must be true")
        .SameState();
}

if (state.Inserted.Count == 0)
{
    return Expect.That<bool>(
            r => !r,
            $"filter is empty → contains('{element}') must be false")
        .SameState();
}

return Expect.That<bool>(
        r => true,
        $"'{element}' was never inserted and the filter is not empty → contains may be true or false")
    .SameState();
```

Read the outcome strings in order and you have the contract in words:

- `Add` ends in `"Insert 'alice' → accepted"` and moves the abstract set to
  `Inserted ∪ {alice}`.
- `Contains` on an inserted element is `"…was inserted → contains must be true"`.
- `Contains` on an empty filter is `"filter is empty → contains('alice') must be false"`.
- `Contains` on an absent element in a non-empty filter is `"…may be true or false"`.
- `Clear` ends in `"Clear → accepted; every membership query now returns false"`
  and moves the abstract set to empty.

The last branch is the important one. A Bloom filter may return `true` for an
element it never inserted, so pinning that answer would fail the first correct
implementation. The spec accepts both answers. A diff of these strings between
two versions of the spec is the contract diff a reviewer should read first.

### What the spec deliberately does not do

It does not simulate the bit array or the hash. Doing that would turn the spec
into a second implementation, pin today's hash strategy, and agree with the
implementation's bugs. The no-false-negative rule is the per-call contract;
the false-positive rate is a probabilistic promise, tested separately in
[`tests/test_statistics.py`](../tests/test_statistics.py). See
[ADR-0001](adr/0001-spec-judges-invariants-statistics-judge-rate.md).

This split has a visible boundary: `bugs/always_true.py` answers `false` only
while empty and `true` after any insertion. It satisfies every per-call rule,
so the spec passes it. The statistical test measures a 100% false-positive rate
and rejects it. The showcase is more convincing because it admits that boundary.

## How the sequential suite is generated

The inputs are `Add alice`, `Add bob`, `Add ghost`, `Contains alice`,
`Contains bob`, `Contains ghost`, and `Clear`. Only three elements can enter,
so the reachable abstract states are the eight subsets of `{alice, bob, ghost}`.
The suite sets `MaxDepth = -1`, an explicit `StateConstraint`, and
`SequentialTestCaseAlgorithms.StateCoverage`; the space is finite, so depth is
not the bound.

One sequence is missing from the generated graph: `Add alice → Clear →
Contains alice` returns to the empty state, and Accordant's built-in algorithms
do not walk cycles. The test adds that case by hand:

```csharp
tests.Add(TestCaseGenerator.CreateManualSequentialTestCase(
    context, inputs, "Add alice", "Clear", "Contains alice"));
```

That manual case is what catches `faulty_clear`. It is the concrete lesson of
`COVERAGE.md` rule 2: a green generated suite is not proof that a cycle ran.

## How the binding works

The spec never imports Python. `CliRunner` starts one long-lived process:

```text
uv run python -m probloom.cli
```

and writes one JSON request per line: `reset`, `add`, `contains`, `clear`, or
`stats`. The test's `BeforeEach` sends `reset`, so every generated case starts
from the spec's empty state. `Add` and `Clear` map to `true`; `Contains`
returns the observed boolean. Only the binding changes if the transport
changes.

The harness's flags are built with [argbuilder](https://pypi.org/project/argbuilder/).
`tests/test_cli.py` calls `cli().debug_assert()` and parses `--impl` through
`try_get_matches_from` without starting a process; a broken definition fails in
the test rather than in the binding.

## What the seeded bugs prove

The `bugs/` package is not shipped. Each test runs the same sequential suite
against one faulty filter and asserts the spec rejects it for the expected
reason:

| Seeded bug | What it does | Expected verdict |
| --- | --- | --- |
| `faulty_add` | `add` records nothing | Spec rejects `Contains alice` after `Add alice`; the message says `was inserted → contains must be true`. |
| `faulty_clear` | `clear` does nothing | Spec rejects the manual `Add alice → Clear → Contains alice` case; the message says `filter is empty → contains('alice') must be false`. |
| `faulty_contains` | returns `false` for `alice` | Spec rejects a query for an inserted element; the message says `was inserted → contains must be true`. |
| `always_true` | `false` while empty, `true` afterwards | Spec **passes**; the statistical test rejects the 100% false-positive rate. |

Run them individually:

```bash
dotnet test spec/Probloom.Spec.Tests/Probloom.Spec.Tests.csproj \
  --filter FullyQualifiedName~Faulty_add
```

## How concurrency is checked

`ProbloomSpec` is unchanged. `ConcurrencySpecTests` generates concurrent cases
with a sequential prefix and a group of two or three calls, then appends a
read of every element after the group. It also pins the two races that matter
for this filter:

- `Add alice || Add bob`, then read both;
- `Add alice || Clear`, then read both.

The suite has 346 cases (344 generated plus the two pinned races) and 346
concurrent groups in this checkout.
The test serializes the cases with `TestCaseGenerator.SerializeConcurrentTestCases`,
then runs [`concurrency/run_cases.py`](../concurrency/run_cases.py). The Python
runner executes one-call segments alone and multi-call segments on a
`threading.Barrier` with a thread pool, so the calls actually overlap. It records
each observed `(operation, request, response)` and writes a trace.

The C# side replays each trace with the spec:

```csharp
var (ok, message, next) = spec.Allows(operation, request, response, profile);
// or, for a group:
var (ok, message, next) = spec.AllowsConcurrent(profile, calls);
```

`AllowsConcurrent` accepts a group when some sequential order of the same calls
explains every response. That is the linearizability check: the spec does not
need separate concurrent assertions. A failure message names the calls that
ran together and says no order explains them.

The filter's per-instance lock is what makes `add`, `contains`, and `clear`
linearizable; see [ADR-0003](adr/0003-thread-safe-filter.md). The concurrent
CLI protocol is deliberately absent; see
[ADR-0004](adr/0004-concurrency-trace-validation.md).

### The concurrency limitation

This path is positive-only. The project chose not to ship an unsynchronized
seeded filter, so a green replay proves that the observed interleavings were
linearizable, not that every possible interleaving is safe. The Python suite
[`tests/test_concurrency.py`](../tests/test_concurrency.py) adds threaded
add/add and add/read stress rounds; it also samples rather than exhausts the
schedule. A controlled scheduler would be the next step if this were a
production service.

## Reviewing a change

1. Read the spec diff first. The outcome strings are the contract in words; a
   changed string is a changed promise. If a branch was added, add an input
   that reaches it.
2. Run `./scripts/ci` (or `uv run pytest` and
   `dotnet test spec/Probloom.Spec.Tests/Probloom.Spec.Tests.csproj` individually).
3. If a seeded-bug test starts passing, the suite has lost its teeth. Fix the
   test or the spec before trusting the green run.
4. If a concurrency replay fails, first look for an `Inner Exception` under
   the message: that means the spec itself threw, which is a spec bug. Otherwise
   read the group and replay the orders against the spec. The bug is usually in
   the implementation (a missing lock or a lost update), not in the spec.
5. Do not add a second contract document. Change the spec and let this page
   follow it.

## Commands

```bash
./scripts/ci
```

That runs `uv sync --dev`, `uv run ruff check .`, `uv run pytest`, and
`dotnet test spec/Probloom.Spec.Tests/Probloom.Spec.Tests.csproj`.

The concurrency test invokes `concurrency/run_cases.py` itself; you do not need
to run the executor by hand unless you are debugging the trace format.
