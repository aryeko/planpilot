# Security and Quality Hardening Plan

Created: 2026-06-30

This plan captures the follow-up work from live GitHub triage on `main` at
`a6b0018836fbc6841ba6d26520fe26d895de53e5`.

## Evidence Snapshot

- Latest `main` runs were green:
  - CI run `28450886731`
  - CodeQL run `28450886816`
  - Secret Scan run `28450887099`
  - Release run `28450930324`
- Local gate passed in the planning worktree:
  - `poetry run poe check`
- Secret scanning had no open alerts through the GitHub API.
- Dependabot alerts were enabled during execution of this plan. The first
  post-enable read returned an empty alert list:
  ```bash
  gh api repos/aryeko/planpilot/dependabot/alerts --paginate
  # []
  ```
- CodeQL had 36 open alerts, all severity `note`:
  - 23 `py/ineffectual-statement`
  - 11 `py/unused-global-variable`
  - 2 `py/repeated-import`
- The release workflow emitted a repo-owned warning:
  - `actions/create-github-app-token` input `app-id` is deprecated; use
    `client-id`.
- Repository Actions variable `RELEASE_APP_CLIENT_ID` now stores the GitHub App
  client ID. Repository secret `RELEASE_APP_PRIVATE_KEY` stores the private key.

## Goals

1. Restore dependency vulnerability visibility.
2. Remove the release workflow deprecation warning.
3. Close or intentionally suppress low-risk CodeQL quality alerts.
4. Keep security workflows least-privilege and deterministic.
5. Verify through local gates and live GitHub status before closeout.

## Non-Goals

- Do not change release semantics, publish environments, or package versioning.
- Do not weaken CodeQL, Gitleaks, or CI failure behavior.
- Do not add live GitHub calls to tests.
- Do not rewrite public CLI import surfaces unless compatibility is preserved.

## Workstream 1: Dependency Vulnerability Visibility

### Problem

`.github/dependabot.yml` keeps dependencies current, but Dependabot alerts are
disabled. That means the repo has version-update automation without a reliable
security-advisory surface.

### Plan

1. Enable Dependabot alerts in GitHub repository settings.
2. Re-run:
   ```bash
   gh api repos/aryeko/planpilot/dependabot/alerts --paginate
   ```
3. Triage any newly visible alerts:
   - If there are no open alerts, record that as the baseline.
   - If alerts exist, prefer normal dependency updates through Dependabot PRs.
   - For urgent advisories, patch the lockfile directly in a dedicated branch.
4. Optional hardening: add a CI dependency-audit job only if GitHub alerts are
   insufficient for the desired gate. Keep it advisory unless a hard failure
   policy is explicitly chosen.

### Acceptance Criteria

- Dependabot alert API no longer returns disabled/forbidden for repo settings.
- Any open alerts are either fixed, dismissed with reason, or tracked.
- `.github/dependabot.yml` remains active for weekly `pip` and GitHub Actions
  updates.

### Owner

Repository admin action is required for enabling alerts. Code changes are only
needed if an audit job is added or alerts require dependency patches.

### Execution Status

Completed in this branch's execution run:

- Enabled Dependabot vulnerability alerts through the GitHub REST API.
- Confirmed the Dependabot alerts API now returns `[]`.
- Confirmed the live workflow list includes Dependabot update workflows.

No dependency patch is needed for the current empty alert baseline.

## Workstream 2: Release Workflow Deprecation

### Problem

The release workflow passes `app-id` to `actions/create-github-app-token`.
The current action logs warn that `app-id` is deprecated in favor of
`client-id`.

### Plan

1. Add or identify a repository Actions variable containing the GitHub App
   client ID. Name: `RELEASE_APP_CLIENT_ID`.
2. Update `.github/workflows/release.yml`:
   ```yaml
   with:
     client-id: ${{ vars.RELEASE_APP_CLIENT_ID }}
     private-key: ${{ secrets.RELEASE_APP_PRIVATE_KEY }}
   ```
3. Keep token scope and job permissions unchanged.
4. Run local workflow validation:
   ```bash
   poetry run poe workflow-lint
   poetry run poe docs-links
   ```
5. After merge, verify the next release workflow run no longer emits the
   deprecation warning.

### Acceptance Criteria

- Release workflow no longer references deprecated `app-id`.
- Release job still checks out the CI-tested commit.
- Release job still uses least-privilege default permissions and job-scoped
  elevation only where needed.

### Owner

Code change plus repository-variable setup.

### Execution Status

Completed in this branch:

- Added repository Actions variable `RELEASE_APP_CLIENT_ID`.
- Updated `.github/workflows/release.yml` to pass `client-id` from
  `vars.RELEASE_APP_CLIENT_ID`.
- Kept `RELEASE_APP_PRIVATE_KEY` in secrets and left job permissions unchanged.

## Workstream 3: CodeQL Quality Cleanup

### Problem

Open CodeQL alerts are quality notes, not active security issues. They create
dashboard noise and can hide higher-signal findings later.

### Plan

1. Replace abstract method ellipsis bodies with explicit
   `raise NotImplementedError` in:
   - `src/planpilot/core/contracts/item.py`
   - `src/planpilot/core/contracts/provider.py`
   - `src/planpilot/core/contracts/renderer.py`
   - `src/planpilot/core/engine/progress.py`
   - `src/planpilot/cli/__init__.py` protocol methods
2. Preserve abstract contracts and public typing.
3. Fix repeated imports in `tests/test_cli.py` by moving `json` to module scope.
4. Review `src/planpilot/cli/__init__.py` re-export aliases:
   - Keep compatibility exports that tests or users rely on.
   - Prefer a clear `__all__` for intentional public symbols.
   - Remove aliases only when they are proven unused and not part of the CLI
     compatibility surface.
5. If CodeQL still flags intentional compatibility exports, dismiss those
   alerts as false-positive or intentional with a short reason instead of
   contorting the module.

### Acceptance Criteria

- `poetry run poe check` passes.
- `poetry run poe docs-links` passes if docs are touched.
- New CodeQL run shows no open alerts for mechanical abstract-method stubs or
  repeated test imports.
- Any remaining CodeQL notes are intentionally dismissed with a reason.

### Owner

Code change.

### Execution Status

Completed in this branch:

- Replaced abstract/protocol ellipsis bodies with explicit
  `raise NotImplementedError` in the contract and progress interfaces.
- Removed repeated local `json` imports from `tests/test_cli.py`.
- Added an explicit `planpilot.cli.__all__` to preserve the intentional
  compatibility exports instead of removing aliases used by tests and command
  modules.

Current live CodeQL alerts still reflect the pre-branch `main` scan until a new
CodeQL run analyzes these changes.

## Workstream 4: Current Warning Noise Triage

### Problem

Some logs contain warning-like lines that are not currently repo defects.

### Decisions

- Gitleaks Node deprecations are upstream action noise. Do not change unless a
  newer action removes them.
- Codecov `xcrun`, `gcov`, and `coverage.py` messages are scanner noise; the
  intended `.coverage/coverage.xml` upload succeeded.
- Git checkout default-branch hints are runner setup noise.
- `if-no-files-found: error` in artifact upload is desired fail-fast behavior.

### Acceptance Criteria

- No code changes for these items unless they become failing checks or upstream
  updates are available through Dependabot.

## Verification Plan

Run before publishing code changes:

```bash
poetry run poe docs-links
poetry run poe workflow-lint
poetry run poe check
```

Run if CLI behavior changes:

```bash
poetry run poe test-e2e
poetry run planpilot --help
```

Live GitHub verification after merge:

```bash
ghx chain --steps - <<'EOF'
[
  {"task":"workflow.runs.list","input":{"first":10}},
  {"task":"workflow.list","input":{"first":50}}
]
EOF
gh api repos/aryeko/planpilot/code-scanning/alerts --paginate
gh api repos/aryeko/planpilot/secret-scanning/alerts --paginate
gh api repos/aryeko/planpilot/dependabot/alerts --paginate
```

### Execution Results

Local verification passed in the execution worktree:

```bash
poetry run poe docs-links
poetry run poe workflow-lint
poetry run poe check
poetry run poe test-e2e
poetry run planpilot --help
```

Live alert baseline after enabling Dependabot alerts:

- Dependabot alerts: `0`
- Secret scanning alerts: `0`
- CodeQL open alerts before this branch is analyzed: `36`

## Execution Order

1. Completed: enable Dependabot alerts and confirm the alert list is empty.
2. Completed: patch CodeQL note sources and run local gates.
3. Completed: add `RELEASE_APP_CLIENT_ID` as an Actions variable.
4. Completed: patch release workflow input to use `client-id`.
5. Remaining: open PR with explicit notes for post-merge workflow verification.
6. After merge, verify live workflow and alert state.

## Risks and Mitigations

- Missing `RELEASE_APP_CLIENT_ID` Actions variable would break release token
  generation. The variable was added before the workflow was changed.
- `src/planpilot/cli/__init__.py` may intentionally expose compatibility
  aliases. Remove only with evidence; otherwise use `__all__` or dismiss
  remaining CodeQL notes.
- Dependabot alerts may reveal existing vulnerabilities. Treat that as a
  surfaced backlog, not as a regression introduced by this plan.
