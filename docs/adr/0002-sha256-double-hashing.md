# Hash elements with SHA-256 and double hashing

Elements are UTF-8 bytes with no Unicode normalization. The filter hashes each element with SHA-256, splits the digest into two 64-bit integers, and derives the k indices as `(h1 + i*h2) % m` with a fixed seed of 0. Python's built-in `hash()` is randomized per process and would make bit patterns and traces irreproducible; a stable, dependency-free derivation is worth more than the speed of a faster digest. The derivation is documented as stable within a major version, not as a serialized wire format.
