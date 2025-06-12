## Description

Brief description of changes

## Type of Change

Please select the primary type of change. Ensure your PR title (or squash commit message) starts with the corresponding semantic prefix (e.g., `feat:`, `fix:`, `docs:`, `style:`, `refactor:`, `test:`, `chore:`).

- [ ] **Bug fix** (non-breaking change which fixes an issue) -> `fix:`
- [ ] **New feature** (non-breaking change which adds functionality) -> `feat:`
- [ ] **Documentation update** -> `docs:`
- [ ] **Code style improvement** (formatting, white-space, etc.) -> `style:`
- [ ] **Refactoring** (no functional changes, no API changes) -> `refactor:`
- [ ] **Performance improvement** (Consider `feat:` for major improvements, `refactor:` for minor ones)
- [ ] **Test addition or update** (adding missing tests, refactoring tests) -> `test:`
- [ ] **Chore** (build process, dependency updates, non-code changes) -> `chore:`

**Is this a Breaking Change?**
- [ ] Yes, this change introduces a breaking change.
  *(If yes, ensure your commit message includes `BREAKING CHANGE:` in the footer or uses the `type!: ...` syntax, e.g., `feat!: ...`. This will trigger a MAJOR version bump.)*

## Checklist

- [ ] Tested locally
- [ ] **Dependency Review:** Considered if key dependencies (e.g., Flask, Gunicorn, yt-dlp) have newer stable versions and if updating them is appropriate for this PR.
- [ ] Documentation updated if needed (e.g., README, `docs/deployment.md`)
- [ ] If breaking changes are introduced, they are clearly marked in commit messages as per the "Is this a Breaking Change?" section above.
