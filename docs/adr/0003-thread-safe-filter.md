# A filter instance is thread-safe under a per-instance lock

`add`, `contains`, and `clear` are linearizable; each takes a `threading.Lock` around the bit-array read-modify-write. A Bloom filter's bit updates are read-modify-write, so without a lock two concurrent insertions can lose a bit and turn a later query into a false negative. The lock serializes every call, including reads, which is a real cost; the no-false-negative promise wins in v1, and a read-optimized lock-free design can be a later, separately measured change.
