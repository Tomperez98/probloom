# Concurrency is validated by replaying Python traces

The sequential suite drives the library through the NDJSON CLI, but the concurrent suite executes Accordant-generated cases in Python and replays their traces through `AllowsConcurrent`. A single-line CLI cannot overlap two calls without a second concurrent protocol whose semantics we would also have to test, and the trace path exercises the same spec without it. The cost is that a Python runner executes the generated concurrent cases instead of Accordant's runner; the spec still generates the cases and judges every response.
