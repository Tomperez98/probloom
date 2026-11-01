# Contributing to probloom

`main` is protected. Every change lands through a pull request that passes the
required `test` check and is squash-merged. Direct pushes, force-pushes, and
branch deletion are blocked.

## Before you write code

1. Open or find an issue with `gh issue create` / `gh issue list`.
2. Wait for a triage label. The five labels are `needs-triage`, `needs-info`,
   `ready-for-agent`, `ready-for-human`, `wontfix`.
3. Only start work on an issue labelled `ready-for-agent` or `ready-for-human`.
4. Claim it: `gh issue edit <n> --add-assignee @me`.

PRs are not a request surface. Unsolicited feature PRs may be closed and
redirected to an issue.

## Set up

Requires Python 3.14, [uv](https://docs.astral.sh/uv/), and the .NET SDK 10 for
the Accordant suite.

```bash
uv sync --dev
./scripts/ci
```

`./scripts/ci` runs `ruff check`, `ruff format --check`, `ty check`, `pytest`,
and the .NET Accordant suite. CI runs the same script, so a green local run is
the expected baseline.

## Branches and commits

- Branch from `main`: `feat/<issue>-<slug>`, `fix/<issue>-<slug>`,
  `docs/<slug>`, `chore/<slug>`.
- Keep PRs small and focused.
- Reference the issue in the PR body: `Closes #<n>`.

## Pull requests

- Target `main`. Direct pushes to `main` are blocked by a ruleset.
- The required check is `test`. A PR cannot merge until it passes.
- Merges are squash-only; the head branch is deleted on merge.
- Fill in the PR template, including the test plan and the checklist.
- Do not edit `.github/workflows/` or the repository ruleset unless the issue
  explicitly asks for it and the maintainer has approved.

## Agents

Agent contributors follow [`AGENTS.md`](AGENTS.md): issues live in GitHub and
are driven by the `gh` CLI, triage uses the five labels above, and the content
skills define what the output must obey. An agent must work on a branch and
open a PR; it must never push to `main` or change repository settings.

## Security

Do not open a public issue for a vulnerability. See [`SECURITY.md`](SECURITY.md).
