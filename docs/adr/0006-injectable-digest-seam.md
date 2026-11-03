# An optional digest callable is the test seam for bit positions

The filter's bit positions come from a private derivation over a hash digest.
Tests need to pin those positions or force collisions without guessing SHA-256
fixtures or reaching into the private bit array. Hard-coding `hashlib.sha256`
made the collision behavior effectively untestable.

`BloomFilter(capacity, error_rate, *, digest=_sha256_digest)` now accepts an
optional keyword-only callable from UTF-8 element bytes to at least 16 digest
bytes. The default keeps the stable SHA-256 double-hashing contract. A digest
shorter than 16 bytes raises `ValueError`.

The seam is intentionally small and opt-in: production callers leave the
default alone, and the reproducible bit-pattern promise applies to that default
only. Tests can record the exact bytes crossing the boundary, force every
element onto the same positions, and assert the public outcomes without
exposing the bit array.
