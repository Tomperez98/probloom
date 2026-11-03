# Releasing probloom

The release process is a checklist, not a memory exercise. Publishing is a
one-way door: once a version is on PyPI, fix forward with a new version rather
than replacing its bytes.

## Version and changelog

The version lives in one place: `[project].version` in `pyproject.toml`.
`probloom.__version__` reads it from installed package metadata, and the
harness's `--version` uses the same value. Do not repeat the number elsewhere.

1. Move the `Unreleased` entries in [`CHANGELOG.md`](../CHANGELOG.md) under the
   new version and date. Put breaking changes first with migration steps.
2. Bump `[project].version` in the same pull request. Use SemVer; the package
   has no wire format, so the public contract is the Python API and the stable
   SHA-256 bit pattern.
3. Merge through a pull request. `main` is protected and requires the `test`
   check.

## Verify the frozen commit

Resolve the commit from remote `main`, check it out, and run the full gate:

```bash
./scripts/ci
```

That command runs `ruff`, `ty`, the Python suite, the .NET Accordant suite,
builds the wheel, and verifies the wheel has zero runtime dependencies and no
harness files. The build is the artifact you will publish; do not rebuild after
this point.

Inspect what the user will receive from the build `./scripts/ci` already
produced:

```bash
uv run python scripts/check_wheel.py
python -m zipfile -l dist/probloom-<version>-py3-none-any.whl
```

The wheel must contain only `probloom/` plus `*.dist-info/`, and the metadata
must have no `Requires-Dist` entries.

## Publish

Publishing is a deliberate stop: confirm the frozen commit, the version, and the
changelog entry, then upload. Prefer PyPI trusted publishing over a long-lived
token. Configure the PyPI project's trusted publisher for this repository and
the release environment; keep the upload job separate from build and test and
grant it only `id-token: write`.

```bash
uv publish dist/probloom-<version>-py3-none-any.whl dist/probloom-<version>.tar.gz
```

If a token is the only option, use a project-scoped token with an expiry and
keep it out of logs.

## Verify from the outside

After publishing, install the release into a clean environment and run the
README example:

```bash
uv venv --python 3.13 /tmp/probloom-smoke
source /tmp/probloom-smoke/bin/activate
uv pip install probloom==<version>
python -c "from probloom import BloomFilter; f = BloomFilter(1000, 0.01); f.add('alice'); assert 'alice' in f"
```

Then confirm the PyPI page shows the expected version, license, and project
links.

## If a release fails

- **Build or check fails before upload:** fix the cause, bump nothing, and rerun.
  No version was burned.
- **Upload stops partway:** rerun the upload for the missing files. A version
  that already holds different bytes is taken; bump the version.
- **A published release is wrong:** publish a new version with the fix through
  this checklist. If the release is dangerous to keep available, yank it on
  PyPI and tell users how to move off it.
- **The validation itself is wrong:** fix the validation on `main` and run it
  against the released tag; do not cut a release to fix the checker.
