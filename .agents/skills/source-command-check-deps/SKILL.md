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
   - Every pin floor matches the latest available version (using the existing `>=` style). This covers both "new release available" and "pin floor is behind installed version" cases.
   - Skip any package flagged as a major bump in step 4 — leave those for the user to review manually.
   - If no bumps are needed, say so and skip the edits.

6. After editing, run `pip install -r requirements.txt -r requirements-dev.txt` to install the new versions locally so the user can test immediately.

7. End with a clear summary:
   - What was auto-applied (and the resulting diff hunks)
   - What was skipped and why (e.g., majors)
   - Any follow-up the user should take (review majors, run tests, etc.)

## Notes

- This project uses Flask/WSGI with gunicorn gthread worker, single worker mode.
- If the venv doesn't exist or pip fails, instruct the user to set up the venv first.
- The goal: after this command runs, the user should have local changes ready to review, test, and commit.
- Never commit, push, or create a PR without explicit approval (per project workflow memory).
- Don't worry about open Dependabot PRs. They'll rebase/close after the bundled PR merges. The user may still cherry-pick specific Dependabot PRs between runs; next `/check-deps` will see the new state and adjust.
