# Probloom

A Python Bloom filter library whose correctness is judged by a C# Accordant spec. This glossary covers the filter's contract and the testing vocabulary that names it.

## The filter

**Bloom filter**:
A probabilistic set that answers membership queries with "definitely absent" or "maybe present". "Filter" is the shorthand used in this glossary.
_Avoid_: set, cache, index

**Element**:
A byte string inserted into or queried against a filter. A `str` is encoded as UTF-8 at the boundary, with no Unicode normalization.
_Avoid_: key, item, value

**Insertion**:
The act of making an element a member of a filter. Insertion is idempotent.
_Avoid_: add (as the domain term; `add` is the API name), write

**Membership query**:
The act of asking whether an element may be a member. `true` means "maybe present"; `false` means "definitely absent".
_Avoid_: lookup, test, check

**False positive**:
A membership query that returns `true` for an element that was never inserted. Allowed.
_Avoid_: collision

**False negative**:
A membership query that returns `false` for an element that was inserted. Forbidden; this is the filter's core correctness rule.
_Avoid_: miss

**Empty filter**:
A filter with no insertions. It answers every membership query with `false`.
_Avoid_: new filter

**Clear**:
The library operation that returns a filter to the empty state. After a clear, every membership query returns `false`.
_Avoid_: reset, wipe, flush

**Reset**:
The harness command that discards the filter and constructs a fresh one before a generated case. Reset is not a library operation.
_Avoid_: clear

**Capacity**:
The number of distinct elements a filter is designed to hold. Inserting beyond capacity is allowed and degrades the error rate.
_Avoid_: size, limit

**Error rate**:
The configured target false-positive rate at capacity. It is not a per-query guarantee.
_Avoid_: precision, accuracy

**Thread-safe**:
A filter instance may be used by multiple threads without external synchronization; `add`, `contains`, and `clear` are linearizable.
_Avoid_: concurrent (as a synonym), synchronized (that is an implementation detail)

**Abstract inserted-set**:
The set of elements the spec remembers as inserted. It is the spec's state, not the filter's bit array; the spec never models bits or hashes.
_Avoid_: bit state, model state

## The spec and its tests

**Spec**:
The C# Accordant contract: a minimal state plus one `Apply` per operation, which says which responses are correct and how the state moves.
_Avoid_: model, mock, oracle (when naming the spec itself)

**Outcome**:
One response the spec allows for a request in a state, with its state step. Its explanation reads `"<situation> → <outcome>"` and is the contract in words.
_Avoid_: assertion, expected value

**Invariant**:
A property that must hold before and after every state transition. The spec checks it with `Invariant.Assert` inside `ThenState`.
_Avoid_: assertion, property

**Binding**:
The code that turns an operation into a call on the Python library. Only the binding changes between transports.
_Avoid_: client, adapter

**Profile**:
The set of states the system could be in, threaded from one `Allows` call to the next. Not the Bloom filter's occupancy.
_Avoid_: state, when more than one state is possible

**Generated case**:
One sequence of operation calls produced by exploring the spec's state graph from a starting state.
_Avoid_: test, scenario (when naming the generated artifact)

**Concurrent case**:
A generated case with a sequential prefix followed by a **concurrent group**.
_Avoid_: race test, stress test

**Concurrent group**:
The calls in a concurrent case that overlap in time. The spec accepts the group when one sequential order explains every response.
_Avoid_: batch, parallel calls

**Linearizability**:
The concurrency criterion: concurrent results are correct when some sequential order of the same calls explains them.
_Avoid_: atomicity (when naming the whole criterion), serializability

**Statistical acceptance test**:
A seeded Python test that inserts to capacity, queries many absent elements, and compares the observed false-positive rate with the configured error rate. It owns the probabilistic promise; the spec does not.
_Avoid_: benchmark, fuzz test

**Seeded bug**:
A deliberately wrong filter used to demonstrate that the spec or the statistical test rejects it. Not shipped.
_Avoid_: mutant, bug injection
