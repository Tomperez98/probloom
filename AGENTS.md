# probloom

## Engineering skills — mandatory when applicable

The four skills installed from [`Tomperez98/skills`](https://github.com/Tomperez98/skills)
— `code`, `docs`, `ship`, `accordant` — are this repo's **content layer**: they
define what the output must obey. They are not advisory. When a task matches a
skill's trigger, load its `SKILL.md`, then the branch guide for the situation,
and follow the numbered rules in order.

If a skill is missing from the environment, install it first —
`npx skills add Tomperez98/skills` — and do not fall back on general knowledge.

The **process layer** (`triage`, `to-spec`, `to-tickets`, `domain-modeling`)
owns the loop: when to triage, spec, plan, and claim a ticket. The content
skill applies *inside* each step and never replaces the process.

| Task | Process layer decides | Content skill applies |
| --- | --- | --- |
| Triage or shape incoming work | `triage`, `to-spec`, `to-tickets` | — |
| Write a feature | brainstorm, then plan | `code` → `WRITE.md` |
| Write tests | your TDD loop | `code` → `TEST.md` |
| Fix a bug | find the cause first | `code` → the fix; `TEST.md` for the regression |
| Reshape code, name things | — | `code` → `SHAPE.md` |
| Make a hot path faster | — | `code` → `PERFORMANCE.md` |
| Write docs | timing | `docs` → `README.md` / `API.md` / `TUTORIAL.md` / `CHANGELOG.md` |
| Ship a release | when it is allowed | `ship` → `RELEASE.md` |
| Model a stateful system | — | `accordant` → `SPEC.md` |

Branch guides — read the matching one before writing anything:

- `code/` — WRITE · STATE · SHAPE · HTTP_API · LOGIC · PERFORMANCE · REFACTOR · TEST · CRASHONLY · CRASH_TESTS · DEPENDENCIES
- `docs/` — README · API · TUTORIAL · CHANGELOG · LANDING · DOCS_MARKETING
- `ship/` — CI · MONITOR · RELEASE · PUBLISH · COMPAT · ROLLOUT · REVIEW
- `accordant/` — SPEC · GENERATE · SUITES · COVERAGE · ORACLE · CONCURRENCY · ASYNC · FAULTS · BASELINE · TRACES · DEBUG

Each `SKILL.md` ends with a **Hand off** section naming the skill that picks up
next; follow it when work crosses into another skill's territory.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `Tomperez98/probloom`, driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles mapped 1:1 to their label strings: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.
