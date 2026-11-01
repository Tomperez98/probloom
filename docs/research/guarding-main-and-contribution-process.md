# Guarding `main` and the contribution process in `Tomperez98/probloom`

**Date:** 2026-10-31
**Repository:** [`Tomperez98/probloom`](https://github.com/Tomperez98/probloom) (public, user-owned, default branch `main`)
**Scope:** Branch protection / repository rulesets, required status checks, plan availability, agent-safe contribution flow, security guardrails, merge strategy, and the honest tradeoffs for a solo maintainer. Recommendations are limited to what one maintainer can operate without a second human approver.
**Method:** Read-only inspection of the local clone and the live GitHub API (`gh`, authenticated as `Tomperez98`, `ADMIN`), plus GitHub Docs, GitHub Changelog, GitHub REST API docs, PyPI docs, and the OpenSSF Scorecard action repository. The research pass made no write API calls; the later application is recorded in §8.

---

## TL;DR

1. **`main` is completely unprotected today.** There are no rulesets (`[]`), legacy branch protection returns 404, and `gh ruleset check main` reports `0 rules apply`. The repo is public and the authenticated user is `ADMIN`, so this is a configuration gap, not a permissions gap.
2. **Use a repository ruleset, not classic branch protection.** A single active ruleset targeting `~DEFAULT_BRANCH` can require a PR, require the `test` check, require conversation resolution, block force-push/deletion, block direct pushes, and allow squash-only merges — with **0 required approvals**, which is the only workable setting for one human.
3. **The required check name is `test`, not `ci / test`.** For a workflow job, the check context is the **job name**; the live check run on `main` is named `test`. This is the single most common misconfiguration.
4. **Merge queue is not available to this repository.** On GitHub.com, merge queue is limited to **organization-owned public repositories** (or org-owned private repos on Enterprise Cloud). `Tomperez98/probloom` is user-owned, so a merge-queue rule would be a dead end. It is also overkill for one required check.
5. **The highest-leverage agent guardrail is token scope, not another workflow.** Give agents a fine-grained token or GitHub App installation with `Contents: write`, `Pull requests: write`, `Issues: write`, `Metadata: read` — **no `Administration`, no `Workflows`**. Then an agent cannot edit the ruleset or `.github/workflows/` even if it goes wrong. The ruleset stops direct pushes; the token stops privilege escalation.
6. **`GITHUB_TOKEN` already defaults to read-only here** (`default_workflow_permissions: "read"`, `can_approve_pull_request_reviews: false`), but the CI workflow should state `permissions: contents: read` explicitly so a future settings change cannot silently widen it.
7. **Fix the CI trigger duplication now:** `on: push` (all branches) plus `on: pull_request` runs CI twice for every branch push that has an open PR. Use `push: branches: [main]` plus `pull_request: branches: [main]`, and keep a post-merge run on `main`.
8. **Free security features are already half-on:** secret scanning and push protection are enabled; Dependabot alerts, Dependabot security updates, private vulnerability reporting, and CodeQL default setup are all off. All four are available for this public repository (CodeQL is documented as free for public repos; Dependabot is available on all plans; private vulnerability reporting is documented for public repositories).
9. **Do not require 1 approval or code-owner review.** GitHub does not let a PR author approve their own PR, and there is only one collaborator. A ruleset with `required_approving_review_count: 1` or `require_code_owner_review: true` would deadlock every PR.
10. **`evaluate` enforcement is Enterprise-only.** The reflex "start in evaluate mode" does not work on this plan. Create the ruleset as `disabled`, inspect it, then flip it to `active`; document `disabled` as the break-glass path.

---

## 1. Observed current state

All commands were run inside `/Users/tomperez98/Personal/probloom` on 2026-10-31. Outputs are quoted or paraphrased exactly where they matter.

| # | Fact | Evidence (exact command) | Observed value / implication |
|---|---|---|---|
| O1 | Repository is public, user-owned, default branch `main` | `gh repo view --json nameWithOwner,visibility,isPrivate,viewerPermission,viewerCanAdminister,defaultBranchRef,hasIssuesEnabled` | `{"nameWithOwner":"Tomperez98/probloom","visibility":"PUBLIC","isPrivate":false,"viewerPermission":"ADMIN","viewerCanAdminister":true,"defaultBranchRef":{"name":"main"},"hasIssuesEnabled":true}` |
| O2 | No repository rulesets | `gh api repos/Tomperez98/probloom/rulesets` | `[]` |
| O3 | No legacy branch protection | `gh api repos/Tomperez98/probloom/branches/main/protection` | HTTP 404 `{"message":"Branch not protected"}` |
| O4 | Branch object says unprotected | `gh api repos/Tomperez98/probloom/branches/main --jq '{name,protected}'` | `{"name":"main","protected":false}` |
| O5 | No rules apply to `main` | `gh ruleset check main` | `0 rules apply to branch main in repo Tomperez98/probloom` |
| O6 | Only one collaborator, the owner | `gh api repos/Tomperez98/probloom/collaborators --jq 'map({login,role_name,permissions})'` | `[{"login":"Tomperez98","role_name":"admin","permissions":{"admin":true,"maintain":true,"push":true,"triage":true,"pull":true}}]` |
| O7 | Plan is not exposed by the token | `gh api /user --jq '{login,plan}'` | `{"login":"Tomperez98","plan":null}` — plan tier cannot be confirmed from the API with this token. The repo is public, so the relevant branch-protection/ruleset features are available regardless. |
| O8 | CI workflow shape | `.github/workflows/ci.yml` (local) | `name: ci`; `on: push` (all branches) + `on: pull_request`; one job `test`; all three actions pinned to full 40-char SHAs; runs `./scripts/ci`. |
| O9 | CI script shape | `scripts/ci` (local) | `uv sync --dev --frozen`; `ruff check .`; `ruff format --check .`; `ty check --error-on-warning src tests bugs concurrency`; `pytest`; `dotnet test spec/Probloom.Spec.Tests/Probloom.Spec.Tests.csproj`. |
| O10 | The CI check on `main` is named `test` and succeeded | `gh api repos/Tomperez98/probloom/commits/main/check-runs --jq '.check_runs[]'` | `{"name":"test","status":"completed","conclusion":"success","app":"github-actions"}` |
| O11 | Only two CI runs exist, both `push` on `main` | `gh run list --limit 10` | Two `push` runs on `main`, both `success`, 24s and 25s. No PR runs yet because there are no PRs. |
| O12 | Five non-Actions check suites are queued on the current `main` commit | `gh api repos/Tomperez98/probloom/commits/main/check-suites --jq '.check_suites[]'` | `sonarqubecloud`, `netlify`, `vercel`, `railway-app`, `mintlify` all `queued`; `github-actions` `completed/success`. These are app installations, not CI. They add noise to the checks surface; confirm whether they are intentional. |
| O13 | Default `GITHUB_TOKEN` permissions are read-only | `gh api repos/Tomperez98/probloom/actions/permissions/workflow` | `{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}` |
| O14 | Actions are enabled, all actions allowed, SHA pinning is **not** enforced | `gh api repos/Tomperez98/probloom/actions/permissions` | `{"enabled":true,"allowed_actions":"all","sha_pinning_required":false}` |
| O15 | Fork PR workflow approval policy is first-time contributors | `gh api repos/Tomperez98/probloom/actions/permissions/fork-pr-contributor-approval` | `{"approval_policy":"first_time_contributors"}` |
| O16 | Secret scanning + push protection are on; non-provider patterns and validity checks are off; Dependabot security updates are off | `gh api repos/Tomperez98/probloom --jq '.security_and_analysis'` | `secret_scanning: enabled`; `secret_scanning_push_protection: enabled`; `secret_scanning_non_provider_patterns: disabled`; `secret_scanning_validity_checks: disabled`; `dependabot_security_updates: disabled` |
| O17 | Dependabot alerts are disabled | `gh api repos/Tomperez98/probloom/vulnerability-alerts` | HTTP 404 `{"message":"Vulnerability alerts are disabled."}` |
| O18 | Dependabot security updates are disabled | `gh api repos/Tomperez98/probloom/automated-security-fixes` | `{"enabled":false,"paused":false}` |
| O19 | Private vulnerability reporting is disabled | `gh api repos/Tomperez98/probloom/private-vulnerability-reporting` | `{"enabled":false}` |
| O20 | CodeQL default setup is not configured | `gh api repos/Tomperez98/probloom/code-scanning/default-setup` | `{"state":"not-configured","languages":["actions","csharp","python"],"query_suite":"default","threat_model":"remote"}` |
| O21 | All three merge methods are allowed; head branches are not auto-deleted | `gh api repos/Tomperez98/probloom --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge,license:.license.spdx_id}'` | `{"allow_squash_merge":true,"allow_merge_commit":true,"allow_rebase_merge":true,"delete_branch_on_merge":false,"license":null}` |
| O22 | No PRs and no issues yet | `gh pr list --state all`; `gh issue list --state all` | Both empty. |
| O23 | The five canonical triage labels exist | `gh label list --limit 50` | `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix` are all present, alongside GitHub default labels. |
| O24 | No contribution/security/ownership files | `find .github -type f`; `ls` | Only `.github/workflows/ci.yml`. No `CODEOWNERS`, `CONTRIBUTING.md`, `SECURITY.md`, `PULL_REQUEST_TEMPLATE`, `ISSUE_TEMPLATE`, or `dependabot.yml`. |
| O25 | Existing process conventions | `AGENTS.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md` (local) | Issues live in GitHub and are driven by `gh`; five triage labels; ADRs + `GLOSSARY.md`; **PRs are explicitly not a request surface** (`PRs as a request surface: no`). |
| O26 | Package metadata exists but no license | `pyproject.toml` (local) | Project `probloom` 0.1.0 with `uv_build`; no `license` field. If it ships, PyPI Trusted Publishing and a license decision are relevant. |

**Bottom line from the observation:** the repository is a clean, public, single-maintainer project with a fast CI suite and no branch guard at all. The risk is not a hostile co-maintainer; it is an accidental direct push, a force-push, an agent pushing to `main`, or a required check that silently stops reporting.

---

## 2. What GitHub actually provides

### 2.1 Rulesets vs legacy branch protection

GitHub supports both mechanisms, and they layer: if both target the same branch, all applicable rules apply, and the **most restrictive** version of a duplicated rule wins ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)). Rulesets are the better fit here because they support multiple rules, explicit bypass lists, `disabled`/`active`/`evaluate` enforcement, fnmatch targeting, and visibility to anyone with read access ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).

| Capability | Ruleset representation | Legacy branch protection | Notes for this repo |
|---|---|---|---|
| Require a PR before merging | `pull_request` rule | "Require a pull request before merging" | Rulesets allow `required_approving_review_count: 0` (API min 0, max 10) ([REST rules](https://docs.github.com/en/rest/repos/rules)). |
| Required approvals | `pull_request.parameters.required_approving_review_count` | Same UI setting | Solo maintainer must use `0`; authors cannot approve their own PRs ([docs](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)). |
| Dismiss stale approvals | `dismiss_stale_reviews_on_push` | Same UI setting | Moot with 0 approvals, but keep `true` for future contributors. |
| Require review from Code Owners | `require_code_owner_review` | Same UI setting | Do **not** enable with one owner; it would require the author to approve their own PR. |
| Require status checks | `required_status_checks` | "Require status checks to pass before merging" | The only real gate for this repo. |
| Require branches up to date | `strict_required_status_checks_policy` | "Require branches to be up to date before merging" | Strict = re-run after `main` moves; loose = fewer rebuilds. |
| Require conversation resolution | `required_review_thread_resolution` | Same UI setting | Cheap and useful for agent PRs. |
| Require linear history | `required_linear_history` | Same UI setting | Combine with squash-only. |
| Block force pushes | `non_fast_forward` | "Block force pushes" | Enabled by default in the ruleset UI per [Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets). |
| Restrict deletions | `deletion` | "Restrict deletions" | Selected by default in the ruleset UI per the same page. |
| Require signed commits | `required_signatures` | Same UI setting | Defer until agent commit signing is solved; unsigned head commits can block a squash merge even though GitHub signs the final squash commit ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)). |
| Require deployments | `required_deployments` | Same UI setting | Not relevant; no deployment target. |
| Require merge queue | `merge_queue` | "Require merge queue" | **Unavailable for user-owned repos** (see §2.2). |
| Restrict creations/updates | `creation`, `update` | "Restrict who can push" (classic: public repos owned by a Free org, or org repos on Team/Enterprise; not available on user-owned repos) | **Do not add `update` without a bypass actor.** Merging a PR updates the target ref, so `update` blocks every merge, including for admins. The `pull_request` rule already blocks direct pushes. |
| Path-scoped required reviewers | `pull_request.parameters.required_reviewers` | Not available | Teams only; **not available on user-owned repositories** ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)). |
| Bypass actors | `bypass_actors` | Admins bypass by default; "Do not allow bypassing the above settings" | Rulesets make bypass an explicit grant ([Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)). |
| Multiple rules on one branch | Multiple rulesets layer | One rule per branch | Rulesets are strictly more flexible ([About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)). |
| Enforcement modes | `active`, `disabled`, `evaluate` | On/off | `evaluate` is Enterprise-only ([REST rules](https://docs.github.com/en/rest/repos/rules)). |
| Targeting | `conditions.ref_name.include` with `~DEFAULT_BRANCH`, `~ALL`, `refs/heads/main`, fnmatch | Branch name pattern | Use `~DEFAULT_BRANCH`; **never `~ALL`** here (it would also protect agent feature branches). |

**Limit:** up to **75 rulesets per repository** and 75 organization-wide rulesets ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)). Approval count max is **10** ([REST rules](https://docs.github.com/en/rest/repos/rules)). Required-reviewer rules support up to 15 teams, but teams do not exist on user-owned repos ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)).

### 2.2 Plan availability — verified, not assumed

| Feature | Public repository | Private repository |
|---|---|---|
| Branch protection | **GitHub Free and Free for organizations** ([REST protected branches](https://docs.github.com/en/rest/branches/branch-protection)) | **Pro, Team, Enterprise Cloud, Enterprise Server** ([same](https://docs.github.com/en/rest/branches/branch-protection)) |
| Repository-level rulesets | Available; the GA announcement describes rulesets as branch protections "in your public repositories" ([GitHub Blog](https://github.blog/news-insights/product-news/github-repository-rules-are-now-generally-available/)) | Docs do not gate repo-level rulesets, but org-wide rulesets require **Team or Enterprise** ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)). Private-repo behavior on Free is **UNVERIFIED** here. |
| Required status checks | Available as part of the ruleset/branch-protection feature above | Same |
| Merge queue | **Only organization-owned public repositories** — not user-owned repos ([gated-feature source](https://github.com/github/docs/blob/main/data/reusables/gated-features/merge-queue.md); [GA changelog](https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/)) | Organization-owned private repos on **Enterprise Cloud** ([same gated-feature source](https://github.com/github/docs/blob/main/data/reusables/gated-features/merge-queue.md)) |
| Secret scanning | **Free and automatic** ([Secret scanning docs](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning)) | Requires **GitHub Secret Protection** on Team/Enterprise Cloud, or GHES with Secret Protection ([same](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning)) |
| Push protection | **Free and on by default for public repos** ([GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features)) | Requires Secret Protection ([same](https://docs.github.com/en/code-security/getting-started/github-security-features)) |
| CodeQL / code scanning | **Free for public repositories** ([GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features)) | Requires a **GitHub Code Security** license ([About code scanning](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning)) |
| Dependency review action | **Free for all public repositories** ([Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)) | Requires Code Security or GitHub Advanced Security ([same](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)) |
| Dependabot alerts + security updates | **All plans** ([GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features)) | All plans ([same](https://docs.github.com/en/code-security/getting-started/github-security-features)) |
| Private vulnerability reporting | **Public repositories; owners/admins can enable** ([docs](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately)) | Not described as a private-repo feature on this page; treat as public-only here. |
| Code owners | Free for public repos; listed under private-repo advanced tools for **Pro/Team** ([GitHub's plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)) | Pro/Team and above ([same](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)) |
| Artifact attestations | Free/Pro/Team: **public repos only** ([GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features)) | Enterprise Cloud ([same](https://docs.github.com/en/code-security/getting-started/github-security-features)) |
| `evaluate` ruleset enforcement | **GitHub Enterprise only** ([REST rules](https://docs.github.com/en/rest/repos/rules)) | Enterprise only ([same](https://docs.github.com/en/rest/repos/rules)) |
| Actions minutes | Free for standard GitHub-hosted runners on public repos ([GitHub's plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)) | Plan-dependent included minutes ([same](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)) |

**What this means concretely:** every P0 recommendation is documented as available for this public repository; none of them requires a paid plan according to the sources above. The tempting features that are **not** available are merge queue (user-owned repo limitation) and `evaluate` enforcement (Enterprise-only).

### 2.3 Enforcement modes and targeting

The REST API exposes three enforcement values ([REST rules](https://docs.github.com/en/rest/repos/rules)):

- `active` — rules enforced immediately.
- `disabled` — rules not enforced, but the ruleset remains configured.
- `evaluate` — rules are evaluated for insights without enforcement; the API docs state **"evaluate is only available with GitHub Enterprise"** ([REST rules](https://docs.github.com/en/rest/repos/rules)).

The UI documentation lists only **Active** and **Disabled** as enforcement statuses ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)); the `evaluate` value is an Enterprise API capability. **Do not plan a "start in evaluate" rollout for this repo** — it will not work. Instead:

1. Create the ruleset as `disabled`.
2. Inspect the payload and targeting with `gh api repos/Tomperez98/probloom/rulesets/<id>`.
3. Flip to `active` with a `PUT` (the ruleset update endpoint is `PUT /repos/{owner}/{repo}/rulesets/{ruleset_id}`, not `PATCH`) ([REST rules](https://docs.github.com/en/rest/repos/rules)).
4. Keep `disabled` documented as the emergency path.

Targeting uses `conditions.ref_name.include` / `exclude` ([REST rules](https://docs.github.com/en/rest/repos/rules)):

- `~DEFAULT_BRANCH` — the repository's default branch (`main` here). This is the right target.
- `refs/heads/main` — an explicit alternative, but it will not follow a future default-branch rename.
- `~ALL` — all branches. **Do not use this**: it would also protect `feat/*` and `fix/*` branches and block agents from pushing their own branches.
- `fnmatch` patterns such as `releases/**/*` are supported for narrower targeting ([Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)).

### 2.4 Required status checks: the mechanics that actually bite

This is the part most likely to break a working setup. GitHub's own troubleshooting page is explicit about the check-name format ([Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules)):

> **Workflow:** the name format is `<job name>`.
> **Reusable workflow:** `<job name> / <reusable job name>`.
> **Other checks:** `<check name>`.

So for this repo:

- Workflow `name: ci` is **not** part of the required context.
- Job key `test` (with no `name:`) produces a check named **`test`**.
- The live check run on `main` confirms `"name": "test"` (O10).
- The required status check context must therefore be **`test`**.

Additional rules that matter:

1. **A required check must have completed successfully in the repository during the past seven days** to be recognized ([Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). This repo already has a successful `test` run, so the requirement is satisfiable now.
2. **Required checks must pass on the latest commit SHA; checks from earlier commits do not satisfy the requirement** ([same](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)).
3. **Successful statuses are `success`, `skipped`, and `neutral`** ([same](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). A job skipped by an `if:` conditional reports **"Success"** and does not block, even if required ([Status checks](https://docs.github.com/en/pull-requests/reference/status-checks)).
4. **A workflow skipped by path filtering, branch filtering, or a commit-message skip leaves the associated checks "Pending" and blocks the PR** ([Troubleshooting table](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). This is the classic "skipped but required" pitfall: the check does not fail, it simply never reports. **Do not add `paths:` or `branches:` filters to the workflow that produces a required check.**
5. **Renaming the job changes the check name.** The old required context will stop reporting and the PR will hang at "Waiting for status to be reported." This is an inference from the documented name-matching rule; verify with `gh api .../check-runs` after any rename.
6. **Matrix jobs can produce suffixed check names** (for example `test (3.14)`). The docs say required checks do not take matrix into account ([Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules)), but if a matrix is added later, re-check the actual check names before assuming `test` still matches. This is a caution, not a documented guarantee.
7. **If a check and a commit status share a name, both must pass** ([Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). This repo uses GitHub Actions checks, not commit statuses, so this is currently moot.
8. **Only workflows triggered by `push`, `pull_request`, `pull_request_review`, `pull_request_target`, `deployment`, or `deployment_status` produce checks that are evaluated for a PR** ([Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). A `workflow_dispatch`-only workflow will never satisfy a required check. This repo's `pull_request` trigger qualifies.
9. **The test merge commit vs the head commit:** if the test merge commit has a status, that commit must pass; if it has no status, the head commit must pass ([Troubleshooting table](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). With `on: pull_request`, GitHub Actions runs against the test merge commit, which is exactly what you want for a PR gate.
10. **Anyone with write access can set any status check** ([Status checks](https://docs.github.com/en/pull-requests/reference/status-checks)). To stop a write-scoped agent token from faking `test`, set `integration_id` to the GitHub Actions app ID `15368` in the ruleset. The docs describe selecting an app as the expected source ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)); the ID is confirmed by `gh api /apps/github-actions --jq .id` → `15368`.

### 2.5 CI trigger hygiene

Current workflow: `on: push` with no branch filter, plus `on: pull_request` ([local `ci.yml`](.github/workflows/ci.yml)). A push to a branch that has an open PR triggers **both** a `push` run and a `pull_request` run. That is a duplicate run and a duplicate check surface (inference from the two event definitions; the repo has no PRs yet, so the duplicate is not visible in O11).

Recommended triggers:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Why this is safe:

- Feature-branch pushes no longer run CI directly; the PR event runs CI on the test merge commit.
- `main` still gets a post-merge run, which validates the actual squashed commit that landed.
- The required `test` check still reports on PRs because `pull_request` runs on the PR's test merge commit ([Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)).
- If the repo ever moves to an organization and adopts merge queue, add `merge_group:` as an additional trigger; the docs are explicit that merge queue requires it or the required check will never report ([Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)).

Also add a workflow-level `permissions: contents: read` and a concurrency group:

```yaml
permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

`concurrency` cancels superseded runs in the same group ([docs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)). `permissions` applies least privilege to `GITHUB_TOKEN` ([workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)); the repo default is already `read` (O13), but an explicit block survives a future settings change.

---

## 3. Recommended target state (prioritized)

### P0 — do now (low risk, high value)

| # | Recommendation | Why | Primary source |
|---|---|---|---|
| P0-1 | Create an **active** ruleset `protect-main` targeting `~DEFAULT_BRANCH` with: `pull_request` (0 approvals, conversation resolution, squash-only), `required_status_checks` (`test`, integration `15368`, strict), `required_linear_history`, `non_fast_forward`, `deletion`; **empty bypass list**. Do **not** add `update`. | This is the actual guard. It stops direct pushes (via `pull_request`), force-pushes, deletion, merge commits, and merges without the `test` check — while remaining workable for one human because approvals are 0 and merges can write the target ref. | [REST rules](https://docs.github.com/en/rest/repos/rules); [Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| P0-2 | Change CI triggers to `push: branches: [main]` + `pull_request: branches: [main]`; add `permissions: contents: read`, `concurrency`, and an explicit job `name: test`. | Kills duplicate runs, limits token scope, and freezes the check context so a future refactor does not silently break the required check. | [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax); [Concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency); [Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules) |
| P0-3 | Set squash-only merges, disable merge commits and rebase merges, and enable `delete_branch_on_merge`. | Produces a linear history and removes stale branches; matches the `allowed_merge_methods: ["squash"]` rule. | [REST repositories](https://docs.github.com/en/rest/repos/repos) |
| P0-4 | Enable Dependabot alerts + Dependabot security updates; add `.github/dependabot.yml` for `github-actions`, `uv`, and `nuget`. | SHA pinning is good, but pinned actions do **not** get Dependabot vulnerability alerts; version updates keep the pins fresh. `uv` and NuGet are supported ecosystems. | [GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features); [Secure use](https://docs.github.com/en/actions/reference/security/secure-use); [Dependabot for actions](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions); [Supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories) |
| P0-5 | Enable private vulnerability reporting and add `SECURITY.md`. | The repo is public and security reports should not become public issues. PVR is documented for public repositories. | [Report privately](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately); [Security policy](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy) |
| P0-6 | Add `CONTRIBUTING.md`, `.github/pull_request_template.md`, issue templates, and `.github/CODEOWNERS`. | Encodes the existing `AGENTS.md` process (issues via `gh`, five triage labels, PRs are not a request surface) in the places GitHub surfaces to contributors. CODEOWNERS is routing/notification only — do not enable required code-owner review. | [Contributing guidelines](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors); [PR templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository); [Code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) |
| P0-7 | Set `sha_pinning_required: true` in Actions repository permissions. | The workflow already pins all three actions to full SHAs; this makes the policy enforced rather than conventional. | [REST Actions permissions](https://docs.github.com/en/rest/actions/permissions); [Secure use](https://docs.github.com/en/actions/reference/security/secure-use) |

### P1 — next (security depth, still low friction)

| # | Recommendation | Why | Primary source |
|---|---|---|---|
| P1-1 | Enable **CodeQL default setup** for `actions`, `csharp`, `python`. Do **not** make its check required yet. | CodeQL is free for public repos and can scan GitHub Actions workflows for dangerous patterns. Default setup auto-selects languages/query suite/events, so it is a one-click/one-API change. | [Code scanning](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning); [CodeQL default setup](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql); [Secure use](https://docs.github.com/en/actions/reference/security/secure-use) |
| P1-2 | Add the **dependency review action** on `pull_request`; optionally make its check required after it has run successfully. | Blocks new dependencies with known vulnerabilities and license surprises before merge; free for public repos. | [Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review); [Configuring the action](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action) |
| P1-3 | Add **OpenSSF Scorecard** via the Security tab's starter workflow. | Free for public repos; checks include dangerous workflows, token permissions, and pinned dependencies. Scorecard can read repository rulesets with the default `GITHUB_TOKEN`. | [scorecard-action README](https://github.com/ossf/scorecard-action); [Secure use](https://docs.github.com/en/actions/reference/security/secure-use) |
| P1-4 | Give agents a **fine-grained PAT or GitHub App installation** with `Contents: write`, `Pull requests: write`, `Issues: write`, `Metadata: read`; **no `Administration`, no `Workflows`**. | Technical boundary: the token cannot edit the ruleset or `.github/workflows/`, even if the agent is compromised or confused. `Workflows` permission is what governs creating/updating workflow files. | [Fine-grained PAT permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens) |
| P1-5 | Optional **PR hygiene workflow**: comment (not fail) when a PR does not link an issue or lacks a triage label. | Makes the `AGENTS.md` process visible without adding another required check that can hang. | [Issue/PR templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates) |

### P2 — later / conditional

| # | Recommendation | Why | Primary source |
|---|---|---|---|
| P2-1 | Require signed commits **only after** agent commit signing is solved. | Required signatures check head-branch commits and can block a squash merge even though GitHub signs the final squash commit. | [Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| P2-2 | Add a **tag ruleset** for `v*` with `deletion` + `non_fast_forward`. | Release tags should not be movable or deletable once published. | [REST rules](https://docs.github.com/en/rest/repos/rules) |
| P2-3 | If the package ships to PyPI, use **Trusted Publishing (OIDC)** and generate provenance/attestations. Never use a long-lived PyPI token. | Short-lived OIDC credentials; PyPI forbids `pull_request_target` and `issue_comment` triggers for Trusted Publishing. | [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/); [PyPI Trusted Publishing troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/); [Artifact attestations](https://docs.github.com/en/code-security/getting-started/github-security-features) |
| P2-4 | Review `secret_scanning_non_provider_patterns` and `secret_scanning_validity_checks`; enable if available on this plan. | Generic patterns catch private keys/connection strings that provider patterns miss; validity checks prioritize live secrets. Availability on public free repos is **UNVERIFIED**. | [Secret scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning) |
| P2-5 | Add a `LICENSE`. | The repo is public but `license: null`; without a license, default copyright applies and contributions are not clearly reusable. This is a project hygiene question, not a branch-protection one. | Local observation O21/O26 (no license). |

### Explicitly **not** recommended

| Idea | Why not |
|---|---|
| Require 1+ approvals | Only one human collaborator; GitHub does not let authors approve their own PRs ([docs](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)). Every PR would deadlock. |
| Require code-owner review | Same problem: the only code owner is the author. |
| Require review from a second bot account | Adds a fake human gate; a bot approval does not add judgment. Use CI + a PR trail instead. |
| Merge queue | Not available for a user-owned repo ([gated feature](https://github.com/github/docs/blob/main/data/reusables/gated-features/merge-queue.md)); designed for high PR volume ([Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)). |
| `evaluate` mode first | Enterprise-only ([REST rules](https://docs.github.com/en/rest/repos/rules)). Use `disabled` → `active`. |
| Protect `~ALL` branches | Would block agents from pushing feature branches; target `~DEFAULT_BRANCH` only. |
| `pull_request_target` for CI | Privileged trigger with base-repo secrets; unsafe with untrusted PR code ([Secure use](https://docs.github.com/en/actions/reference/security/secure-use); [Events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target)). |
| Path-filtered required workflow | Workflow-level skips leave checks pending and block merges ([Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)). |
| Require signed commits today | Unsigned agent commits would block squash merges ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)). |

---

## 4. How to apply it

> These are copy-pasteable commands for this exact repo. They were written before the changes were applied; the commands actually run and the resulting state are recorded in §8.

### 4.1 Create the ruleset

Save this as `.github/rulesets/protect-main.json` (a useful source-of-truth artifact even though it is applied manually). The installed `gh` (2.103.2) exposes `gh ruleset list`, `view`, and `check`, but not `create`, so the creation path below uses `gh api`:

```json
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_extra_approval_for_unattributed_changes": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          { "context": "test", "integration_id": 15368 }
        ]
      }
    }
  ]
}
```

Create it **disabled first**, inspect, then activate:

```bash
# 1. Create in disabled mode (evaluate is Enterprise-only; disabled is the safe dry run here)
jq '.enforcement = "disabled"' .github/rulesets/protect-main.json \
  | gh api --method POST repos/Tomperez98/probloom/rulesets --input - \
  | tee /tmp/probloom-ruleset.json

RULESET_ID=$(jq -r '.id' /tmp/probloom-ruleset.json)
echo "$RULESET_ID"

# 2. Inspect the stored payload and targeting
gh api "repos/Tomperez98/probloom/rulesets/$RULESET_ID" \
  --jq '{id,name,enforcement,target,conditions,rules:[.rules[].type]}'

# 3. Activate from the active source-of-truth (ruleset updates use PUT, not PATCH)
gh api --method PUT "repos/Tomperez98/probloom/rulesets/$RULESET_ID" \
  --input .github/rulesets/protect-main.json

# 4. Confirm
gh ruleset check main
gh api repos/Tomperez98/probloom/rules/branches/main --jq '.[].type'
```

These snippets use `jq` to rewrite `enforcement` before the API call. If `jq` is unavailable, set `"enforcement": "disabled"` in the JSON file by hand, create the ruleset with `gh api --method POST ... --input .github/rulesets/protect-main.json`, and update it with `gh api --method PUT ... --input <file>` after inspection. **The update endpoint is `PUT`; `PATCH` returns 404.** A full `PUT` also accepts the whole ruleset, so keep the JSON complete: fields omitted from a full `PUT` can be filled with API defaults.

Notes on the payload:

- `bypass_actors: []` means no actor is granted bypass. The docs describe bypass as an explicit grant ("you can allow certain users to bypass the rules") ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)); unlike classic protection, rulesets do not document an automatic admin exemption. The repo admin can still edit or disable the ruleset — that is the break-glass path, not a bypass.
- `update` is **omitted on purpose**. It means "only bypass actors can update the ref", and a PR merge is an update to the target ref. With `bypass_actors: []`, adding `update` makes every PR unmergeable, including for the admin (`viewerCanMergeAsAdmin: false`). The `pull_request` rule already blocks direct pushes; `non_fast_forward` blocks force-pushes; `deletion` blocks branch deletion.
- `required_approving_review_count: 0` is the key solo-maintainer setting. The PR is still required; it simply does not need an approval.
- `require_code_owner_review: false` avoids the self-approval deadlock. `CODEOWNERS` still routes notifications.
- `require_extra_approval_for_unattributed_changes: false` is explicit even though the docs say the extra approval "has no effect if the ruleset requires zero approvals". GitHub fills it in as `true` when omitted, and it would add one approval to an unattributed Copilot/agent PR if the approval count is ever raised ([Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)).
- `allowed_merge_methods: ["squash"]` makes squash the only merge path. The API values are `merge`, `squash`, `rebase` ([REST rules](https://docs.github.com/en/rest/repos/rules)).
- `integration_id: 15368` is the GitHub Actions app (`gh api /apps/github-actions --jq .id`). It prevents a write-scoped token from satisfying `test` with a forged check. If you ever move CI to another app, update this field.
- `strict_required_status_checks_policy: true` requires the PR branch to be up to date before merging. For a low-volume repo this is the safer choice; switch to `false` if the rebase friction becomes annoying.
- **Do not add `paths:` or `branches:` filters to the workflow that emits `test`.** A workflow-level skip leaves the check pending ([Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)).

If you later want an explicit emergency bypass that still preserves the PR trail, add yourself with `bypass_mode: "pull_request"` instead of `"always"`:

```json
"bypass_actors": [
  { "actor_id": 72174660, "actor_type": "User", "bypass_mode": "pull_request" }
]
```

The docs describe this mode as: the actor is required to open a PR, and can then choose to bypass branch protections and merge that PR ([Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)). It preserves the no-direct-push rule but allows a red merge in an emergency. Start with `[]`; add this only if you find yourself disabling the ruleset weekly.

### 4.2 Repository merge settings

```bash
gh api --method PATCH repos/Tomperez98/probloom \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true
```

`allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`, and `delete_branch_on_merge` are documented update fields ([REST repositories](https://docs.github.com/en/rest/repos/repos)). The docs note that setting `delete_branch_on_merge=true` on the create-repository endpoint requires an organization owner; this is a **user-owned** repo, so the PATCH behavior is **UNVERIFIED** until run. If the PATCH is rejected, use the repository's branch settings UI to enable automatic head-branch deletion. The field itself is the right control either way.

Optional, if you want cleaner squash messages:

```bash
gh api --method PATCH repos/Tomperez98/probloom \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=PR_BODY
```

### 4.3 Actions hardening

```bash
# Require full-length SHA pins for every action (all current pins already satisfy this)
gh api --method PUT repos/Tomperez98/probloom/actions/permissions \
  -F enabled=true \
  -f allowed_actions=all \
  -F sha_pinning_required=true

# Keep the default GITHUB_TOKEN read-only and unable to approve PRs
gh api --method PUT repos/Tomperez98/probloom/actions/permissions/workflow \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false

# Keep first-time contributor workflow approval (already the current policy)
gh api repos/Tomperez98/probloom/actions/permissions/fork-pr-contributor-approval
```

`sha_pinning_required` is a documented repository Actions permission field ([REST Actions permissions](https://docs.github.com/en/rest/actions/permissions)). The current workflow already pins `actions/checkout`, `astral-sh/setup-uv`, and `actions/setup-dotnet` to full SHAs ([local `ci.yml`](.github/workflows/ci.yml)), so turning this on should not break the current build.

**Warning:** If you later add a fourth action by tag (for example `actions/dependency-review-action@v4`), `sha_pinning_required: true` will reject it. Resolve the tag to a commit SHA first:

```bash
gh api repos/actions/dependency-review-action/commits/v4 --jq .sha
gh api repos/ossf/scorecard-action/commits/v2 --jq .sha
```

Then use the returned 40-character SHA in the workflow.

### 4.4 Security toggles

```bash
# Dependabot alerts (also enables the dependency graph)
gh api --method PUT repos/Tomperez98/probloom/vulnerability-alerts

# Dependabot security updates
gh api --method PUT repos/Tomperez98/probloom/automated-security-fixes

# Private vulnerability reporting
gh api --method PUT repos/Tomperez98/probloom/private-vulnerability-reporting

# CodeQL default setup (auto-selects languages/query suite/events)
gh api --method PATCH repos/Tomperez98/probloom/code-scanning/default-setup \
  -f state=configured
```

Endpoints and availability:

- `PUT /repos/{owner}/{repo}/vulnerability-alerts` and `PUT /repos/{owner}/{repo}/automated-security-fixes` ([REST repositories](https://docs.github.com/en/rest/repos/repos)).
- `PUT /repos/{owner}/{repo}/private-vulnerability-reporting` ([REST repositories](https://docs.github.com/en/rest/repos/repos)); public-repo feature ([docs](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately)).
- `PATCH /repos/{owner}/{repo}/code-scanning/default-setup` with `state: configured` ([REST code scanning](https://docs.github.com/en/rest/code-scanning/code-scanning)); default setup chooses languages and events automatically ([CodeQL docs](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql)).
- Do not make the CodeQL check required on day one. Let it run, inspect the check names, then decide.

### 4.5 Agent-safe contribution flow

The repo's `AGENTS.md` and `docs/agents/issue-tracker.md` already define the process: issues live in GitHub, `gh` is the interface, there are five triage labels, and **PRs are not a request surface**. The missing piece is technical enforcement. Recommended end-to-end flow:

1. **Pick work:** `gh issue list --state open --label ready-for-agent`.
2. **Claim:** `gh issue edit <n> --add-assignee @me` (the first write, per `issue-tracker.md`).
3. **Branch:** `git switch -c feat/<n>-<slug>` (or `fix/`, `docs/`, `chore/`).
4. **Implement + run the full suite locally:** `./scripts/ci`.
5. **Push the branch:** `git push -u origin HEAD`. On a feature branch this is allowed; `main` is protected.
6. **Open the PR:** `gh pr create --base main --title "<type>: <summary>" --body-file .github/pull_request_template.md` (or a filled-in body with `Closes #<n>`).
7. **Watch checks:** `gh pr checks --watch`. The required check is `test`.
8. **Human merges:** `gh pr merge --squash --delete-branch` (or let auto-merge do it if enabled for a trusted class of PRs).

Technical enforcement, in order of strength:

| Guard | What it stops | How |
|---|---|---|
| Ruleset with `pull_request` + empty bypass | Direct pushes to `main`; force-pushes; deletion; merge commits; merges without `test`. | P0-1 |
| Required `test` check with `integration_id: 15368` | Merges when CI is red; forged check runs from write-scoped tokens. | P0-1 |
| Agent token without `Administration` or `Workflows` | Agents editing the ruleset or `.github/workflows/`. | P1-4 |
| `permissions: contents: read` in CI | A compromised CI step escalating via `GITHUB_TOKEN`. | P0-2 |
| `CODEOWNERS` + PR template | Nothing technically; it routes notifications and makes ownership visible. | P0-6 |
| PR hygiene workflow (advisory) | Missing issue links / labels, visibly. | P1-5 |

**Limits of technical enforcement:** a repository admin can always disable the ruleset; a token with `Administration: write` can edit it; and an agent with `Contents: write` can still push a branch and open a PR. The realistic goal is to make the *safe* path the *easy* path and to ensure that a compromised agent cannot silently change the rules or CI. That is what the token scoping buys you.

**Important `GITHUB_TOKEN` nuance:** events triggered by `GITHUB_TOKEN` do not create new workflow runs (with narrow exceptions for `workflow_dispatch`, `repository_dispatch`, and PRs created/updated by the token, which land in an approval-required state) ([GITHUB_TOKEN docs](https://docs.github.com/en/actions/concepts/security/github_token)). If an agent uses the repo's `GITHUB_TOKEN` to push, its push will not trigger CI; use a GitHub App or fine-grained PAT for agent pushes and PR creation.

### 4.6 File sketches

#### `.github/CODEOWNERS`

```text
# Default owner for everything in this repository.
* @Tomperez98

# CI and contribution plumbing: changes here change the rules for everyone.
/.github/ @Tomperez98
/scripts/ci @Tomperez98

# The spec is the contract; changes need the owner's eyes.
/spec/ @Tomperez98
/docs/adr/ @Tomperez98
```

Code owners must have write access; the last matching pattern wins ([About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)). This file routes review requests. **Do not** set `require_code_owner_review: true` with a single owner.

#### `CONTRIBUTING.md` (skeleton)

````markdown
# Contributing to probloom

## Before you write code

1. Open or find an issue with `gh issue create` / `gh issue list`.
2. Wait for a triage label. The five labels are `needs-triage`, `needs-info`,
   `ready-for-agent`, `ready-for-human`, `wontfix`.
3. Only start work on an issue labelled `ready-for-agent` or `ready-for-human`.
4. Claim it: `gh issue edit <n> --add-assignee @me`.

PRs are not a request surface. Unsolicited feature PRs may be closed and
redirected to an issue.

## Local checks

```bash
uv sync --dev
./scripts/ci
```

`./scripts/ci` runs `ruff check`, `ruff format --check`, `ty check`, `pytest`,
and the .NET Accordant suite. CI runs the same script.

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
- Do not edit `.github/workflows/` or the ruleset unless the issue explicitly
  asks for it and the maintainer has approved.

## Security

Do not open a public issue for a vulnerability. Use the repository's
**Security → Report a vulnerability** flow (private vulnerability reporting).
````

#### `.github/pull_request_template.md`

```markdown
## Summary

<!-- What changed, and why? -->

## Linked issue

Closes #

## Test plan

- [ ] `./scripts/ci` passes locally
- [ ] Added/updated tests for the change
- [ ] If this changes an invariant, updated the spec and `docs/accordant.md`
- [ ] If this is a hard-to-reverse decision, added an ADR under `docs/adr/`

## Checklist

- [ ] No secrets, tokens, or credentials in the diff
- [ ] Docs/glossary updated if vocabulary changed
- [ ] The PR is squash-mergeable (linear history, one logical change)
- [ ] I did not edit `.github/workflows/` or repository rules without maintainer approval

## Notes for the reviewer

<!-- Anything risky, skipped, or worth a second look. -->
```

PR templates are automatically shown in the PR body when placed in `.github/` ([docs](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)).

#### `.github/ISSUE_TEMPLATE/bug.yml` (minimal issue form)

```yaml
name: Bug report
description: Something is wrong with probloom
labels: ["needs-triage"]
body:
  - type: textarea
    id: repro
    attributes:
      label: Reproduction
      description: Minimal code or commands that show the problem.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: probloom version / commit
    validations:
      required: true
  - type: textarea
    id: ci
    attributes:
      label: Output of ./scripts/ci
      render: shell
```

Issue templates live under `.github/ISSUE_TEMPLATE/` and can pre-apply labels ([docs](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)).

#### `.github/workflows/ci.yml` (trigger + permissions sketch)

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: test
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4

      - uses: astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v5
        with:
          python-version: "3.14.7"

      - uses: actions/setup-dotnet@67a3573c9a986a3f9c594539f4ab511d57bb3ce9 # v4
        with:
          dotnet-version: "10.0.403"

      - name: Run the suite
        run: ./scripts/ci
```

Keep the pinned SHAs exactly as they are. The explicit `name: test` freezes the required-check context; changing the job name would change the check name ([Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules)).

#### `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "nuget"
    directory: "/spec/Probloom.Spec.Tests"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
```

`github-actions` is the documented ecosystem for workflow action updates ([Dependabot for actions](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions)). `uv` is a supported ecosystem ([supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)). Dependabot updates SHA-pinned actions and the version comment ([2022 changelog](https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/)). Note: Dependabot PRs are treated like fork PRs for workflow purposes ([Events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)), so their CI runs with a read-only token; that is fine for `./scripts/ci`.

#### `SECURITY.md` (skeleton)

```markdown
# Security policy

## Supported versions

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Do not open a public issue. Use the repository's **Security → Report a
vulnerability** flow (private vulnerability reporting). If that is unavailable,
contact the maintainer privately through the address in `pyproject.toml`.

Please include a minimal reproduction, the affected commit, and the impact.

## Response

The maintainer aims to acknowledge reports within 7 days and to publish a
coordinated advisory after a fix is available.
```

GitHub surfaces `SECURITY.md` from the root, `docs/`, or `.github/` ([docs](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy)).

#### Dependency review workflow (optional, P1)

The docs' example is the correct baseline ([configuring the action](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action)):

```yaml
name: dependency-review
on:
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  dependency-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
      - uses: actions/dependency-review-action@<FULL_SHA_FOR_V4> # v4
```

Resolve `<FULL_SHA_FOR_V4>` with `gh api repos/actions/dependency-review-action/commits/v4 --jq .sha`. The action is free for public repositories and fails on vulnerable packages by default ([Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)). If you make it required, its check context is the job name `dependency-review`; add it to the ruleset only after it has run successfully.

### 4.7 Break-glass procedure

Because there is no bypass actor, the emergency path is to disable the ruleset, merge, and re-enable it. The docs explicitly support changing enforcement without deleting the ruleset ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).

```bash
RULESET_ID=$(gh api repos/Tomperez98/probloom/rulesets \
  --jq '.[] | select(.name=="protect-main") | .id')

# 1. Disable (ruleset updates use PUT, not PATCH)
gh api --method PUT "repos/Tomperez98/probloom/rulesets/$RULESET_ID" \
  --input <(jq '.enforcement="disabled"' .github/rulesets/protect-main.json)

# 2. Do the emergency merge (still via a PR if possible)
gh pr merge <n> --squash --delete-branch

# 3. Re-enable immediately
gh api --method PUT "repos/Tomperez98/probloom/rulesets/$RULESET_ID" \
  --input .github/rulesets/protect-main.json

# 4. Leave a trail
gh issue create --title "Break-glass: ruleset disabled for #<n>" \
  --body "Reason, time, and the PR that needed the exception."
```

Rules for using it:

- Only for a broken CI check or an urgent security fix, not for convenience.
- Prefer the PR path even in an emergency, so the change is reviewable.
- Re-enable in the same session.
- Open an issue recording why. This is the audit trail that a bypass actor would otherwise provide.

---

## 5. Verification

Run these after applying. Each maps to a guard above.

```bash
REPO=Tomperez98/probloom

# Ruleset exists, is active, targets the default branch, and has the expected rules
gh ruleset list
RULESET_ID=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name=="protect-main") | .id')
gh api "repos/$REPO/rulesets/$RULESET_ID" \
  --jq '{name,enforcement,target,conditions,rules:[.rules[].type]}'

# The active rules that apply to main (rules in disabled/evaluate rulesets are excluded)
gh api "repos/$REPO/rules/branches/main" --jq '.[] | {type,parameters}'

# gh's own summary
gh ruleset check main

# Branch object (expect protected: true; if it stays false, trust /rules/branches/main)
gh api "repos/$REPO/branches/main" --jq '{name,protected}'

# The required check name is still `test` and it succeeds
gh api "repos/$REPO/commits/main/check-runs" \
  --jq '.check_runs[] | {name,status,conclusion,app:.app.slug}'

# SHA pinning is enforced
gh api "repos/$REPO/actions/permissions" --jq '{enabled,allowed_actions,sha_pinning_required}'

# GITHUB_TOKEN is read-only and cannot approve PRs
gh api "repos/$REPO/actions/permissions/workflow"

# Merge strategy
gh api "repos/$REPO" \
  --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge}'

# Security toggles
gh api "repos/$REPO" --jq '.security_and_analysis'
gh api "repos/$REPO/vulnerability-alerts" -i | head -1          # 204 = enabled
gh api "repos/$REPO/automated-security-fixes"                    # enabled: true
gh api "repos/$REPO/private-vulnerability-reporting"             # enabled: true
gh api "repos/$REPO/code-scanning/default-setup"                 # state: configured
```

**Safe negative test (optional).** Do not test by pushing to `main`. Instead, create a temporary branch and a temporary ruleset that targets only that branch:

```bash
# Create a scratch branch from main
SHA=$(gh api repos/Tomperez98/probloom/commits/main --jq .sha)
gh api --method POST repos/Tomperez98/probloom/git/refs \
  -f ref=refs/heads/protection-test -f sha="$SHA"

# Create a temporary ruleset targeting refs/heads/protection-test with the same rules,
# then clone, commit, and try `git push origin HEAD:protection-test`.
# Expect the push to be rejected by the update/pull_request rules.
# Delete the temporary ruleset and branch afterward.
```

This validates the enforcement mechanics without risking `main`. It is a write operation; do it only when you are deliberately testing.

**What to check after a CI change:** run `gh api "repos/$REPO/commits/<pr-merge-commit>/check-runs" --jq '.check_runs[] | {name,conclusion}'` and confirm the name is still `test`. A rename is the most likely cause of "Waiting for status to be reported."

---

## 6. Tradeoffs and things NOT to do

### Solo-maintainer tradeoffs

1. **0 approvals means the PR is a record, not a review.** The gate is CI plus your own discipline. That is the honest ceiling with one human. Do not pretend otherwise by adding a bot approval.
2. **No bypass means emergencies require disabling the ruleset.** This is slightly more friction than an admin bypass, but it leaves a deliberate trail and prevents casual "just this once" merges. If you want a built-in emergency path, use `bypass_mode: "pull_request"` (still requires a PR) rather than `"always"` (allows direct pushes).
3. **Strict up-to-date adds rebases.** With one required check and a 24-second suite (O11), the cost is low. If it becomes annoying, set `strict_required_status_checks_policy: false`; the tradeoff is that a PR can merge with a stale base.
4. **SHA pinning trades Dependabot alerts for immutability.** Dependabot does not create vulnerability alerts for actions pinned to SHA values ([Secure use](https://docs.github.com/en/actions/reference/security/secure-use)). Dependabot version updates still bump the pins ([changelog](https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/)); keep `dependabot.yml` healthy.
5. **Rulesets are not tamper-proof against the owner.** The repo admin can edit or disable them. They are a guardrail against mistakes and compromised non-admin tokens, not a constitutional limit.
6. **`evaluate` is not available.** The "test in evaluate, then enforce" workflow is Enterprise-only. `disabled` → `active` is the substitute; it does not give you rule insights.
7. **Merge queue is unavailable and unnecessary here.** The repo is user-owned, and the docs pitch merge queue for branches with many PRs per day ([Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)). One required check and a solo maintainer do not need it.
8. **CodeQL/dependency review add checks and time.** They are cheap on a 24-second suite, but do not make them required until you have seen their check names and failure modes. A required check that only runs on some PRs is worse than no check.

### Do NOT do these

| Anti-pattern | Why it hurts | Source |
|---|---|---|
| Require 1+ approvals | The only collaborator is the author; authors cannot approve their own PRs. Every PR deadlocks. | [docs](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews) |
| Require code-owner review with one owner | Same deadlock; the code owner is the author. | [Code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) |
| Target `~ALL` branches | Blocks agents from pushing feature branches; protects branches that should be freely pushable. | [REST rules](https://docs.github.com/en/rest/repos/rules) |
| Use `pull_request_target` to get secrets in CI | Privileged trigger; checking out untrusted PR code with base-repo secrets is a repository-takeover pattern. | [Secure use](https://docs.github.com/en/actions/reference/security/secure-use); [Events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target) |
| Add `paths:` filters to the required workflow | Workflow-level skips leave required checks pending and block merges. | [Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) |
| Rename the `test` job without updating the ruleset | The required context changes; the old check never reports; PRs hang. | [Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules) |
| Require `test` before it has succeeded in the last 7 days | A required check must have completed successfully in the repo during the past seven days. | [Troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) |
| Turn on `sha_pinning_required` before pinning every action | Tag-pinned actions will be rejected; workflows fail until fixed. | [REST Actions permissions](https://docs.github.com/en/rest/actions/permissions) |
| Give agents an admin token | An admin token can edit/disable the ruleset and workflows; the guard is only as strong as the token scope. | [Fine-grained PAT permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens) |
| Enable "Allow GitHub Actions to create and approve pull requests" | Lets workflows approve PRs, which defeats the review trail and can create recursive automation. It is already `false` here. | [Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository) |
| Require signed commits before agent signing works | Unsigned head commits can block a squash merge. | [Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| Rely on a queued third-party check (SonarQube, Netlify, Vercel, Railway, Mintlify) | Those suites are `queued` with no check runs on `main` (O12); requiring an app you have not verified is a recipe for pending checks. | Live observation O12 |

---

## 7. Open questions for the maintainer

1. **Plan tier:** `gh api /user` returns `plan: null` with the current token. Public-repo features are unaffected, but Enterprise-only features such as `evaluate` are not available. Can you confirm the plan from the billing settings?
2. **Will `probloom` ship to PyPI?** `pyproject.toml` has `uv_build` and version `0.1.0`, but there is no publish workflow. If yes: Trusted Publishing + attestations + a license decision.
3. **Do you want strict up-to-date checks?** `strict_required_status_checks_policy: true` is safer but adds rebases after every merge. `false` is lower friction.
4. **Do you want an emergency bypass actor?** Start with `[]`. If you find yourself disabling the ruleset often, add yourself with `bypass_mode: "pull_request"` (not `"always"`).
5. **Will agents run as you (fine-grained PAT) or as a separate GitHub App/bot?** A separate identity gives cleaner audit logs and easier revocation.
6. **Are the queued SonarQube / Netlify / Vercel / Railway / Mintlify check suites intentional?** If not, uninstall those GitHub Apps to reduce noise in the checks surface.
7. **Should docs-only PRs skip the .NET suite?** If yes, do not add `paths:` to the required workflow. Either keep one workflow (current 24-second cost) or split checks and require only the relevant job; adding a path filter to the required job will hang PRs.
8. **Do you want signed commits?** This is worth doing only after agent commit signing is solved, because unsigned head commits can block squash merges.
9. **Do you want auto-merge?** With 0 approvals and a required check, auto-merge would let agents merge their own PRs once CI passes. That may be desirable for Dependabot, but it removes the human merge step. Decide deliberately.
10. **License:** `license: null` (O21/O26). A public repo without a license is not open source in the usual sense; contributors lack clear reuse rights. Add a license before inviting contributions.

---

## Evidence table

| # | Source | URL | Key claim used | Type | Confidence |
|---|---|---|---|---|---|
| S1 | GitHub Docs — About rulesets | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets | Rulesets layer; 75 per repo; bypass is opt-in; read access can view; enforcement can change without deletion | Primary | High |
| S2 | GitHub Docs — Available rules for rulesets | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets | Rule semantics: deletion/non-fast-forward defaults; pull_request; status checks; code owner; signed commits; required reviewers not on user-owned repos | Primary | High |
| S3 | GitHub Docs — REST API endpoints for rules | https://docs.github.com/en/rest/repos/rules | Exact ruleset schema, `~DEFAULT_BRANCH`, `bypass_actors`, `integration_id`, `evaluate` Enterprise-only | Primary | High |
| S4 | GitHub Docs — REST API endpoints for protected branches | https://docs.github.com/en/rest/branches/branch-protection | Branch protection availability: public Free; private Pro/Team/Enterprise | Primary | High |
| S5 | GitHub Docs — About protected branches | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches | Classic admins bypass by default; "Do not allow bypassing"; one rule per branch; unique job names; merge queue description | Primary | High |
| S6 | GitHub Docs — Status checks | https://docs.github.com/en/pull-requests/reference/status-checks | Skipped job reports success; check vs commit status; anyone with write can set a status | Primary | High |
| S7 | GitHub Docs — Troubleshooting required status checks | https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks | 7-day rule; latest SHA; skipped-but-required table; eligible trigger events; test merge commit vs head | Primary | High |
| S8 | GitHub Docs — Troubleshooting rules | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules | Workflow check name format is `<job name>`; required checks ignore workflow/matrix/event | Primary | High |
| S9 | GitHub Docs — GITHUB_TOKEN | https://docs.github.com/en/actions/concepts/security/github_token | App installation token; scoped to repo; events from GITHUB_TOKEN do not trigger new runs | Primary | High |
| S10 | GitHub Docs — Use GITHUB_TOKEN for authentication | https://docs.github.com/en/actions/tutorials/authenticate-with-github_token | `permissions` key; least privilege | Primary | High |
| S11 | GitHub Docs — Secure use reference | https://docs.github.com/en/actions/reference/security/secure-use | Pin full SHA; `pull_request_target`/`workflow_run` risk; Dependabot for actions; CODEOWNERS; Scorecard | Primary | High |
| S12 | GitHub Docs — Events that trigger workflows | https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows | Fork PRs get no secrets and read-only token; `pull_request_target` warning; `merge_group` requirement | Primary | High |
| S13 | GitHub Docs — Workflow syntax | https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax | `permissions`; `jobs.<job_id>.name`; `on.push.branches` / `on.pull_request.branches` | Primary | High |
| S14 | GitHub Docs — Managing GitHub Actions settings | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository | Default workflow permissions: permissive vs restricted; allow Actions to create/approve PRs | Primary | High |
| S15 | GitHub Docs — Secret scanning | https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning | Public repos: free automatic; private: Secret Protection | Primary | High |
| S16 | GitHub Docs — GitHub security features | https://docs.github.com/en/code-security/getting-started/github-security-features | Availability matrix: Dependabot all plans; code scanning/dependency review public free; attestations public only on Free/Pro/Team | Primary | High |
| S17 | GitHub Docs — Code scanning | https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning | Private repos need Code Security license; Actions minutes | Primary | High |
| S18 | GitHub Docs — CodeQL | https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql | Default setup auto-selects languages, query suite, events | Primary | High |
| S19 | GitHub Docs — Privately reporting a vulnerability | https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately | Public repos; owners/admins can enable PVR | Primary | High |
| S20 | GitHub Docs — Dependency review | https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review | Action free for public repos; fails on vulnerable packages | Primary | High |
| S21 | GitHub Docs — Configuring dependency review action | https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action | Exact example workflow and permissions | Primary | High |
| S22 | GitHub Docs — Dependabot for actions | https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions | `github-actions` ecosystem, `directory: "/"`, weekly schedule | Primary | High |
| S23 | GitHub Changelog — Dependabot updates SHA comments | https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/ | Dependabot updates SHA-pinned actions and version comments | Primary | High |
| S24 | GitHub Docs — Dependabot supported ecosystems | https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories | `uv` ecosystem supported; NuGet supported | Primary | High |
| S25 | github/docs — merge queue gated feature | https://github.com/github/docs/blob/main/data/reusables/gated-features/merge-queue.md | Merge queue: org-owned public repos, or org-owned private on GHE Cloud | Primary (docs source) | High |
| S26 | GitHub Changelog — merge queue GA | https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/ | Merge queue GA context | Primary | High |
| S27 | GitHub Blog — Repository Rules GA | https://github.blog/news-insights/product-news/github-repository-rules-are-now-generally-available/ | Rulesets for public repositories; flexible targeting/layering | Primary | High |
| S28 | GitHub Docs — About code owners | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners | Code owners need write access; CODEOWNERS locations; last match wins; required code owner review | Primary | High |
| S29 | GitHub Docs — Contributing guidelines | https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors | CONTRIBUTING.md locations and surfacing | Primary | High |
| S30 | GitHub Docs — PR templates | https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository | PR template location and behavior | Primary | High |
| S31 | GitHub Docs — Approving a PR with required reviews | https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews | Authors cannot approve their own PRs | Primary | High |
| S32 | GitHub Docs — Workflow concurrency | https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency | `concurrency`, `cancel-in-progress` | Primary | High |
| S33 | GitHub Docs — GitHub's plans | https://docs.github.com/en/get-started/learning-about-github/githubs-plans | Code owners private Pro/Team; Actions free for public repos | Primary | High |
| S34 | GitHub Docs — REST repositories | https://docs.github.com/en/rest/repos/repos | Merge settings; vulnerability alerts; automated security fixes; PVR endpoints | Primary | High |
| S35 | GitHub Docs — REST Actions permissions | https://docs.github.com/en/rest/actions/permissions | `sha_pinning_required`; default workflow permissions | Primary | High |
| S36 | GitHub Docs — REST code scanning | https://docs.github.com/en/rest/code-scanning/code-scanning | Default setup GET/PATCH and `state: configured` | Primary | High |
| S37 | PyPI Docs — Trusted Publishers | https://docs.pypi.org/trusted-publishers/ | OIDC publishing; no long-lived tokens; forbidden triggers | Primary | High |
| S38 | GitHub — ossf/scorecard-action | https://github.com/ossf/scorecard-action | Free for public repos; default token can read rulesets; push/schedule triggers | Primary (project README) | High |
| S39 | GitHub Docs — Fine-grained PAT permissions | https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens | `Workflows` permission governs workflow-file writes | Primary | High |
| S40 | Live GitHub API (read-only) | https://api.github.com/repos/Tomperez98/probloom | Observed state O1–O26 | Primary (observation) | High for observed values |
| S41 | Local repository files | https://github.com/Tomperez98/probloom | CI shape (`.github/workflows/ci.yml`, `scripts/ci`), process conventions (`AGENTS.md`, `docs/agents/*`), package metadata (`pyproject.toml`) | Primary (local) | High |
| S42 | GitHub Docs — Configuring issue templates | https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository | Issue templates live under `.github/ISSUE_TEMPLATE/`; can pre-apply labels | Primary | High |
| S43 | PyPI Docs — Trusted Publishing troubleshooting | https://docs.pypi.org/trusted-publishers/troubleshooting/ | PyPI forbids `pull_request_target` and `issue_comment` triggers for Trusted Publishing | Primary | High |

---

## Sources

1. GitHub Docs — About rulesets — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
2. GitHub Docs — Available rules for rulesets — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
3. GitHub Docs — REST API endpoints for rules — https://docs.github.com/en/rest/repos/rules
4. GitHub Docs — REST API endpoints for protected branches — https://docs.github.com/en/rest/branches/branch-protection
5. GitHub Docs — About protected branches — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
6. GitHub Docs — Status checks — https://docs.github.com/en/pull-requests/reference/status-checks
7. GitHub Docs — Troubleshooting required status checks — https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
8. GitHub Docs — Troubleshooting rules — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules
9. GitHub Docs — GITHUB_TOKEN — https://docs.github.com/en/actions/concepts/security/github_token
10. GitHub Docs — Use GITHUB_TOKEN for authentication — https://docs.github.com/en/actions/tutorials/authenticate-with-github_token
11. GitHub Docs — Secure use reference — https://docs.github.com/en/actions/reference/security/secure-use
12. GitHub Docs — Events that trigger workflows — https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
13. GitHub Docs — Workflow syntax — https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
14. GitHub Docs — Managing GitHub Actions settings — https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
15. GitHub Docs — Secret scanning — https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning
16. GitHub Docs — GitHub security features — https://docs.github.com/en/code-security/getting-started/github-security-features
17. GitHub Docs — Code scanning — https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning
18. GitHub Docs — CodeQL — https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
19. GitHub Docs — Privately reporting a vulnerability — https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately
20. GitHub Docs — Dependency review — https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review
21. GitHub Docs — Configuring dependency review action — https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action
22. GitHub Docs — Dependabot for actions — https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions
23. GitHub Changelog — Dependabot updates SHA comments — https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/
24. GitHub Docs — Dependabot supported ecosystems — https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories
25. github/docs — merge queue gated feature — https://github.com/github/docs/blob/main/data/reusables/gated-features/merge-queue.md
26. GitHub Changelog — merge queue GA — https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/
27. GitHub Blog — Repository Rules GA — https://github.blog/news-insights/product-news/github-repository-rules-are-now-generally-available/
28. GitHub Docs — About code owners — https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
29. GitHub Docs — Contributing guidelines — https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors
30. GitHub Docs — PR templates — https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository
31. GitHub Docs — Approving a PR with required reviews — https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews
32. GitHub Docs — Workflow concurrency — https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
33. GitHub Docs — GitHub's plans — https://docs.github.com/en/get-started/learning-about-github/githubs-plans
34. GitHub Docs — REST repositories — https://docs.github.com/en/rest/repos/repos
35. GitHub Docs — REST Actions permissions — https://docs.github.com/en/rest/actions/permissions
36. GitHub Docs — REST code scanning — https://docs.github.com/en/rest/code-scanning/code-scanning
37. PyPI Docs — Trusted Publishers — https://docs.pypi.org/trusted-publishers/
38. GitHub — ossf/scorecard-action — https://github.com/ossf/scorecard-action
39. GitHub Docs — Fine-grained PAT permissions — https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
40. Live GitHub API (read-only) — https://api.github.com/repos/Tomperez98/probloom
41. Local repository files — https://github.com/Tomperez98/probloom (`.github/workflows/ci.yml`, `scripts/ci`, `AGENTS.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `pyproject.toml`)
42. GitHub Docs — Configuring issue templates — https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository
43. PyPI Docs — Trusted Publishing troubleshooting — https://docs.pypi.org/trusted-publishers/troubleshooting/

---

## Coverage Status

**Checked directly**

- Live repository state via read-only `gh api` GET calls: visibility, permissions, rulesets, branch protection, branch object, ruleset-check output, collaborators, Actions permissions, workflow permissions, fork PR approval policy, secret scanning/security analysis, Dependabot alerts, Dependabot security updates, private vulnerability reporting, CodeQL default setup, merge settings, check runs, check suites, workflow runs, labels, PRs/issues.
- Local files: `.github/workflows/ci.yml`, `scripts/ci`, `AGENTS.md`, `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, `docs/agents/domain.md`, `README.md`, `pyproject.toml`, `global.json`, `.github` tree.
- GitHub Docs pages listed in Sources 1–22, 28–36, 39, and 42, plus the GitHub Changelog entries, the PyPI Trusted Publishers docs (37 and 43), and the OpenSSF Scorecard action README (38).
- The `github/docs` gated-feature source for merge queue.

**Uncertain / UNVERIFIED**

- **Plan tier.** `gh api /user` returns `plan: null`; I could not confirm Free/Pro/Team from the API. This does not affect the public-repo P0 recommendations, but it does affect Enterprise-only features such as `evaluate`.
- **Rulesets on private repos on Free.** The docs do not explicitly gate repo-level rulesets by plan; org-level rulesets require Team/Enterprise. I did not test a private repo. The target repo is public, so this is not blocking.
- **`delete_branch_on_merge` PATCH on a user-owned repo.** Resolved during application: the PATCH succeeded and the setting is on (§8).
- **`integration_id: 15368` acceptance in the ruleset payload.** Resolved during application: the ruleset accepted the field and reports it back (§8).
- **`evaluate` behavior on a personal repo.** The REST docs say Enterprise-only; it was not attempted. Treat it as unavailable.
- **Private vulnerability reporting on a user-owned public repo.** Resolved during application: `PUT` succeeded and the endpoint now reports `enabled: true` (§8).
- **Whether `protected` flips to `true` when only a ruleset applies.** Resolved during application: `GET /branches/main` reports `protected: true` (§8).
- **The five queued third-party check suites** (SonarQube, Netlify, Vercel, Railway, Mintlify) exist on the current commit, but I did not inspect the installed GitHub Apps or determine whether they are intentional.

**Research constraints (before application)**

- The research pass performed no write operations; §8 records the changes applied afterward.
- No ruleset was created during the research pass to validate the exact JSON; the payload was built from the documented schema and later applied successfully (§8).

---

## 8. Application record (2026-10-31)

The P0 set was applied after this research was written. It is committed on `chore/protect-main` and pushed to origin; it is not merged yet.

**Ruleset** — `protect-main`, id `26298093`, `enforcement: active`, target `~DEFAULT_BRANCH`, five active rules (`deletion`, `non_fast_forward`, `required_linear_history`, `pull_request`, `required_status_checks`). Created `disabled`, inspected, then activated. `bypass_actors: []`, `current_user_can_bypass: never`, and `GET /branches/main` reports `protected: true`. `required_status_checks`: context `test`, integration `15368`, strict.

**Repository settings** — squash-only (`allow_squash_merge: true`, merge/rebase `false`), `delete_branch_on_merge: true`, `sha_pinning_required: true`, default `GITHUB_TOKEN` read-only with PR approval disabled, Dependabot alerts and security updates enabled, private vulnerability reporting enabled.

**Files added/changed** — `.github/rulesets/protect-main.json`, `.github/workflows/ci.yml` (triggers, `permissions`, concurrency, explicit `name: test`), `.github/CODEOWNERS`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug.yml`, `.github/dependabot.yml`, `CONTRIBUTING.md`, `SECURITY.md`.

**Three corrections found while applying**

1. **Ruleset updates use `PUT`, not `PATCH`.** `PATCH /repos/{owner}/{repo}/rulesets/{id}` returned 404; `PUT` succeeded. The commands in §4 and §4.7 were corrected.
2. **`require_extra_approval_for_unattributed_changes` is filled in as `true` when omitted**, even though the payload did not set it. The docs say it has no effect at zero approvals, but it is now set to `false` explicitly so raising the approval count later cannot silently add a gate for unattributed/agent PRs. The JSON sketch and notes were corrected.
3. **The `update` rule blocks merges, not just direct pushes.** With `bypass_actors: []`, a PR was `mergeStateStatus: BLOCKED` even though `test` passed and 0 approvals were required, because merging updates the target ref. The rule was removed; the `pull_request` rule still blocks direct pushes. The JSON sketch and notes were corrected.

**Verification** — `./scripts/ci` passes locally: 25 pytest tests and 6 .NET tests. `gh ruleset check main` reports 5 rules; `gh api repos/Tomperez98/probloom/rules/branches/main` lists the expected rules; `gh api .../rulesets/26298093` reports `bypass_actors: []`.

**Not done** — not merged to `main` (PR pending); P1 items (CodeQL, dependency review, Scorecard, agent tokens) and the tag ruleset remain open; no negative push test was run.

---

*This document started as research and now records the applied state in §8. Record any break-glass use in an issue.*
