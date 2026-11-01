# Security policy

## Supported versions

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Do not open a public issue. Use the repository's **Security → Report a
vulnerability** flow (private vulnerability reporting). If that is unavailable,
contact the maintainer privately through the address in `pyproject.toml`.

Please include a minimal reproduction, the affected commit, and the impact.

## Scope

The filter is a library: the relevant issues are incorrect membership results,
data races, and inputs that cause unbounded memory or CPU use. The CLI harness
and the Accordant spec are development tooling.

## Response

The maintainer aims to acknowledge reports within 7 days and to publish a
coordinated advisory after a fix is available.
