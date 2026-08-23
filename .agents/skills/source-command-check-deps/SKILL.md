---
name: "source-command-check-deps"
description: "Evaluate all Python dependencies for available updates, then proactively apply safe bumps."
---

# source-command-check-deps

Use this skill when the user asks to run the migrated source command `check-deps`.

## Command Template

# Check Deps

Evaluate all Python dependencies for available updates, then proactively apply safe bumps.

## Scope

This repo's `.github/dependabot.yml` tracks **three** ecosystems. Cover all three
every run — a pip-only pass silently misses two thirds of the surface:

| Ecosystem | Where it lives |
|---|---|
| pip | `requirements.txt`, `requirements-dev.txt` |
| github-actions | `uses:` lines in `.github/workflows/*.yml` |
| docker | `FROM` lines in `Dockerfile`, `image:` in `docker-compose.yml` |

Also check **pinned runtime versions inside workflow inputs** (`python-version`,
`node-version`). Dependabot does NOT track these — it bumps `actions/setup-node@vN`
but never the Node version that action installs, so they rot silently. Verify each
against its upstream support schedule, not just "is there a newer one".

## Steps

0. **Read the open Dependabot PRs first** for context:

   ```bash
   gh pr list --state open --json number,title,headRefName
   ```

   Do not merge or chase them — they rebase or close on their own. But knowing what
   is proposed prevents writing a *new* file that pins something Dependabot has
   already opened a PR to bump. Note which are superseded by what you are about to
   apply; those should be closed rather than left to conflict.

1. Read `requirements.txt` and `requirements-dev.txt` to get the current version pins.

2. Run this command to check the latest available version for each package:

   ```bash
   source venv/bin/activate && for pkg in <list of packages from step 1, space-separated, without extras like [default]>; do echo "=== $pkg ===" && pip index versions "$pkg" 2>&1 | head -3; done
   ```

2b. **GitHub Actions.** Collect every distinct action and compare to its latest tag:

   ```bash
   grep -rhn "uses:" .github/workflows/ | sed 's/.*uses: //' | sort -u
   gh release view --repo actions/<name> --json tagName --jq .tagName
   ```

   Before proposing a major action bump, confirm the inputs this repo actually
   passes still exist in the new version — release notes are often vague:

   ```bash
   curl -sL https://raw.githubusercontent.com/actions/<name>/v<N>/action.yml
   ```

   **Apply the same version to every workflow that uses that action.** A Dependabot
   PR only patches the files that existed when it was opened, so a newly added
   workflow can be left stranded on the old version.

2c. **Docker and runtime versions.** Check the `FROM` base image in `Dockerfile`
   and every `image:` in `docker-compose.yml` against current upstream tags. An
   untagged image silently means `:latest` — flag it, but pinning to a fixed
   version is not automatically the right fix. Match the tag to what the
   dependency is:

   - **Build/gate tools** (linters, formatters): pin exactly. A new version
     changing pass/fail on untouched code is the failure mode to avoid.
   - **Fast-moving runtime deps** (yt-dlp, bgutil): track the latest. These chase
     upstream changes, so staleness *is* the outage — a frozen token server stops
     returning DASH formats. Keep the compose tag and the matching pip requirement
     on the same policy so the pair cannot drift.
   - **Always name the variant** when one exists (`node` vs `deno` here). The
     compose healthcheck shells out to `node`; a default-variant switch upstream
     would break it silently.

   Also check each `python-version` / `node-version`
   against its support schedule (e.g. `https://raw.githubusercontent.com/nodejs/Release/main/schedule.json`).
   CI runtimes should match what production actually runs — a CI version that differs
   from what the Dockerfile ships is validating a configuration nobody deploys.

   For Python bumps, confirm wheels exist for the target version before switching;
   a missing wheel means a slow source build or an outright failure:

   ```bash
   # inspect the "python tags present" across the package's wheels
   curl -s https://pypi.org/pypi/<pkg>/<ver>/json
   ```

3. Present results in a table per ecosystem, with these columns:
   - **Package**: package name
   - **Pinned At**: current version constraint from requirements file
   - **Installed**: currently installed version (from pip output)
   - **Latest**: latest available version
   - **Bump?**: Yes/No/Major (flag majors separately)
   - **Safe?**: Assessment with brief reasoning (patch = safe, minor = usually safe, major = needs evaluation)

4. For any **major version bumps**, do a web search for the changelog and summarize breaking changes relevant to this project. Do NOT auto-apply majors — surface them for the user to decide. This applies to action majors (`v6` -> `v7`) and base-image majors as well as pip majors.

5. **Apply safe bumps automatically.** After presenting the tables, edit `requirements.txt` and `requirements-dev.txt` so that:
   - **Preserve each package's existing operator.** A `>=` floor stays `>=`; an `==` exact pin stays `==`. Never loosen `==` to `>=` — exact pins are deliberate (see below).
   - Every pin matches the latest available version. This covers both "new release available" and "pin floor is behind installed version" cases.
   - Skip any package flagged as a major bump in step 4 — leave those for the user to review manually.
   - If no bumps are needed, say so and skip the edits.

6. After editing, run `pip install -r requirements.txt -r requirements-dev.txt` to install the new versions locally so the user can test immediately.

   **If `ruff` was bumped, re-run the CI gate locally before reporting success:**

   ```bash
   ruff check .
   ruff format --check .
   ```

   Ruff ships roughly weekly and a new version can change lint or format results on
   untouched code. If either command now fails, surface the new violations in the summary
   and either fix them or flag them — do not leave a bump that would red-X CI.

7. End with a clear summary:
   - What was auto-applied (and the resulting diff hunks)
   - What was skipped and why (e.g., majors)
   - Any follow-up the user should take (review majors, run tests, etc.)

## Notes

- This project uses Flask/WSGI with gunicorn gthread worker, single worker mode.
- If the venv doesn't exist or pip fails, instruct the user to set up the venv first.
- The goal: after this command runs, the user should have local changes ready to review, test, and commit.
- Ruff is version-independent (`py3-none-<platform>` wheels), so the CI Python
  version does not change lint results. It does determine which wheels resolve for
  everything else, which is why CI should match the Dockerfile's runtime.
- `ruff`'s `target-version` in `pyproject.toml` is the *minimum* Python the code
  must support, not the version CI runs. Raising CI to 3.14 does not mean raising
  `target-version` — leave it at the declared floor unless dropping support.
- Never commit, push, or create a PR without explicit approval (per project workflow memory).
- **Why `ruff` is pinned exactly:** `.github/workflows/lint.yml` gates every push and PR on
  `ruff check` and `ruff format --check`. A floor pin would let CI adopt a new ruff weekly and
  fail unrelated PRs on code nobody touched. The `==` pin keeps CI reproducible and makes each
  ruff bump a reviewable change. Runtime deps (yt-dlp, certifi, etc.) intentionally keep `>=`
  floors — fast-moving extractor fixes are desirable there.
- Don't worry about open Dependabot PRs. They'll rebase/close after the bundled PR merges. The user may still cherry-pick specific Dependabot PRs between runs; next `/check-deps` will see the new state and adjust.
