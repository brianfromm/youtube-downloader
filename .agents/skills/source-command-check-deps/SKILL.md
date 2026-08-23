---
name: "source-command-check-deps"
description: "Evaluate all Python dependencies for available updates, then proactively apply safe bumps."
---

# source-command-check-deps

Use this skill when the user asks to run the migrated source command `check-deps`.

## Command Template

# Check Deps

Evaluate all Python dependencies for available updates, then proactively apply safe bumps.

## Steps

1. Read `requirements.txt` and `requirements-dev.txt` to get the current version pins.

2. Run this command to check the latest available version for each package:

   ```bash
   source venv/bin/activate && for pkg in <list of packages from step 1, space-separated, without extras like [default]>; do echo "=== $pkg ===" && pip index versions "$pkg" 2>&1 | head -3; done
   ```

3. Present results in two tables (production and dev), with these columns:
   - **Package**: package name
   - **Pinned At**: current version constraint from requirements file
   - **Installed**: currently installed version (from pip output)
   - **Latest**: latest available version
   - **Bump?**: Yes/No/Major (flag majors separately)
   - **Safe?**: Assessment with brief reasoning (patch = safe, minor = usually safe, major = needs evaluation)

4. For any **major version bumps**, do a web search for the changelog and summarize breaking changes relevant to this project. Do NOT auto-apply majors — surface them for the user to decide.

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
- Never commit, push, or create a PR without explicit approval (per project workflow memory).
- **Why `ruff` is pinned exactly:** `.github/workflows/lint.yml` gates every push and PR on
  `ruff check` and `ruff format --check`. A floor pin would let CI adopt a new ruff weekly and
  fail unrelated PRs on code nobody touched. The `==` pin keeps CI reproducible and makes each
  ruff bump a reviewable change. Runtime deps (yt-dlp, certifi, etc.) intentionally keep `>=`
  floors — fast-moving extractor fixes are desirable there.
- Don't worry about open Dependabot PRs. They'll rebase/close after the bundled PR merges. The user may still cherry-pick specific Dependabot PRs between runs; next `/check-deps` will see the new state and adjust.
