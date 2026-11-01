# The spec judges membership invariants; a statistical test judges the false-positive rate

A Bloom filter's per-call contract is asymmetric: inserted elements must query `true`, while absent elements may query either way. The spec models the abstract inserted-set and accepts both answers for absent elements; it does not simulate bits or hashes. A seeded Python test measures the observed false-positive rate against the configured error rate, because exact bit simulation would turn the spec into a second implementation and leave the probabilistic promise unmeasured.
