# Release Management Guide

## The problem this setup solves

The old setup used GitHub's `generate_release_notes: true`, which lists every merged PR.
Because feature branches were merged (not squash-merged) into `develop`, each feature
appeared **twice** in the release notes:

1. As the original commit from the feature branch (included transitively through develop→main)
2. As the merge commit of the PR (directly listed by GitHub's generator)

This guide explains the correct workflow and how the new tooling (`git-cliff`) fixes it.

---

## How it works now

### Tools

- **[git-cliff](https://git-cliff.org/)** — reads your git log, keeps only conventional commits,
  skips all merge commits, ignores `dev-*` tags, and groups changes by type.
- **`cliff.toml`** (repo root) — configuration for the above.

### Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `release-dev.yml` | push to `develop` | builds `something-x-dev`, publishes pre-release + PyPI dev |
| `release.yml` | push to `main` | bumps semver, tags, builds `something-x`, publishes release + PyPI + AUR |

---

## The only rule: **squash-merge feature branches into develop**

This is what prevents duplicate entries. When you squash-merge a feature PR into `develop`:

- The feature branch's original commits are **not** added to `develop`'s ancestry.
- A single clean conventional commit lands in `develop`.
- When `develop` is merged into `main`, that single commit appears **once** in `main`'s history.
- `git-cliff` reads it **once** → no duplicates.

If you use a regular merge instead of squash, the original feature commits enter `develop`'s
history and will appear in the changelog alongside the squash commit.

### Merge strategy by branch target

| PR target | Merge strategy | Why |
|---|---|---|
| `develop` | **Squash and merge** | one commit per feature, no duplicates |
| `main` (from `develop`) | **Create a merge commit** | preserves individual squashed commits from develop |

### How to enforce this in GitHub

1. Go to **Settings → General → Pull Requests**
2. Under "Allow merge commits": **✓ (keep enabled)** — needed for develop→main
3. Under "Allow squash merging": **✓ (keep enabled)**
4. Under "Allow rebase merging": uncheck (optional, avoids confusion)
5. You cannot enforce squash-only per target branch in vanilla GitHub — rely on convention
   and PR review. The commit history makes violations obvious immediately.

---

## Day-to-day workflow

```
feat/my-feature  ──squash──▶  develop  ──merge commit──▶  main
                                  │                          │
                            pre-release tag             release tag
                           (dev-<sha>)                  (v1.2.3)
```

### 1. Develop a feature

```bash
git checkout develop
git checkout -b feat/my-feature
# ... work ...
git push origin feat/my-feature
```

Open a PR from `feat/my-feature` → `develop`.  
Use **"Squash and merge"** when merging. Write a conventional commit message:

```
feat: add ANC mode detection for CMF Buds Pro 2
```

### 2. Ship a release

Open a PR from `develop` → `main`.  
Use **"Create a merge commit"** (default).

The commit message on main that triggers the release must follow conventional commits:

- `feat: ...` → bumps minor (1.6.0 → 1.7.0)
- `fix: ...` or `refactor: ...` or `perf: ...` → bumps patch (1.6.0 → 1.6.1)
- `feat!:` or `BREAKING CHANGE:` → bumps major (1.6.0 → 2.0.0)
- `docs:`, `chore:`, `ci:`, `style:` → **no release triggered**

The bot then:
1. Updates `version` in `pyproject.toml`
2. Commits `chore: release vX.Y.Z [skip ci]` and pushes the tag
3. Runs `git-cliff --latest` to build the changelog (skips merge commits, no duplicates)
4. Creates the GitHub release with the clean notes
5. Publishes to PyPI and updates AUR

---

## Deploying this PR without breaking existing tags

The existing tags (`v1.2.0` through `v1.6.0`, and the `dev-*` tags) are **untouched** by
this PR. Here is the exact sequence to land it safely:

### Step 1 — merge this branch into `main`

```bash
# On GitHub: open PR from chore/release-management → main
# Use "Create a merge commit" (or squash — doesn't matter for a CI-only change)
```

Use a `chore:` or `ci:` commit message so the release workflow **skips** (no spurious release):

```
ci: replace generate_release_notes with git-cliff
```

The `release.yml` will see `ci:` → log "Commit type does not trigger a release. Skipping." → done.
No new tag, no new release, existing tags are completely untouched.

### Step 2 — verify the cliff config picks up history correctly

After merging, run locally to preview what the next release changelog will look like:

```bash
pip install git-cliff
git cliff v1.6.0..HEAD --strip all
```

If that output looks right, you're good. If it's empty, check that your commits since v1.6.0
use conventional commit format (`feat:`, `fix:`, etc.).

### Step 3 — first real release under the new system

Work as normal (feature branches squash-merged into develop, then develop merged into main
with a conventional commit message). The workflow fires, `git-cliff --latest` generates notes
from `v1.6.0..v1.7.0` (or whatever the next version is), and the release notes are clean.

---

## Troubleshooting

### "Release notes are empty"

`git-cliff` with `filter_unconventional = true` silently drops non-conventional commits.
Check your commit messages since the last `vX.Y.Z` tag:

```bash
git log v1.6.0..HEAD --oneline --no-merges
```

Any commit not starting with `feat:`, `fix:`, `refactor:`, `perf:`, `docs:`, etc. is dropped.

### "I still see duplicates"

Someone used regular merge (not squash) for a feature PR into develop. Find the offending
merge commit:

```bash
git log develop --merges --oneline | head -10
```

For future PRs, remind contributors to use squash. For past ones, the duplicate is harmless —
`git-cliff` deduplicates by hash, so if two commits have the same hash they only appear once.
Cherry-picks (different hash, same message) can still appear twice — the fix is to never
cherry-pick; always merge or squash-merge properly.

### "The release workflow bumped the wrong version"

The bump is driven by the **last commit message on main** at trigger time. If the develop→main
merge commit has a vague message like "Merge branch develop", no release fires. Make sure the
merge commit (or the squash commit if you squash develop→main) has a conventional message
that reflects the highest-impact change in the batch.

### "I need to re-generate release notes for an existing tag"

Edit the release on GitHub manually, or delete and recreate it (the tag stays):

```bash
gh release delete v1.6.0 --yes        # deletes the release, NOT the tag
git cliff v1.5.0..v1.6.0 --strip all  # preview the notes
gh release create v1.6.0 --notes "$(git cliff v1.5.0..v1.6.0 --strip all)"
```
