---
name: resolve-issue
description: Resolve one rdl-tools GitHub issue end to end on a branch the maintainer has already created — plan, test first, implement, document, review — and hand back a proposed PR title and body. Use for "resolve issue N", "work on #N", "fix #N".
argument-hint: "<issue number>"
---

# Resolve an issue

The contributor process is in [CONTRIBUTING.md](../../../CONTRIBUTING.md) under "Resolving an issue". This skill runs that process with the agent tooling named at each step. It does not repeat the gate list or the invariants; read them there.

The skill is for small and medium issues. An issue too big for one session gets a bespoke plan outside it.

## Hard limits

- No subagents. Every step runs in this session. The one exception is `/code-review` in step 7, which launches its own.
- No git or gh command that writes. Reading is allowed: `git status`, `git diff`, `git log`, `git show`, `git rev-parse`, `gh issue view`, `gh pr view`. No branch, commit, stash, push, checkout, restore, or PR. The maintainer does all of that.
- A `gh` command that prints `gh auth login` means `gh` has no login. Stop and point the maintainer to CONTRIBUTING.md's "Claude Code" setup section. Only the maintainer logs in, with a read-only fine-grained token. Never run any `gh auth` command, including `gh auth status` and `gh auth token`.
- Work stays uncommitted in the working tree.
- Stop at each **Checkpoint** and wait for the maintainer.

## Steps

### 0. Precondition

Run `git rev-parse --abbrev-ref HEAD`. If it prints `main`:

1. Run `gh issue view N --repo jamrce/rdl-tools --json title,labels`.
2. Propose a branch name following CONTRIBUTING.md's naming rule, and print the command for the maintainer to run:

   ```sh
   git pull --ff-only && git switch -c <type>/<N>-<slug>
   ```

3. Stop.

Run `git status --short`. If the tree has changes unrelated to the issue, list them and ask before continuing.

### 1. Read the issue

```sh
gh issue view N --repo jamrce/rdl-tools --comments
gh api repos/jamrce/rdl-tools/issues/N/dependencies/blocked_by --jq '.[] | "#\(.number) \(.state) \(.title)"'
```

If any blocking issue is open, stop and name it.

### 2. Plan — `/caveman`

Discussion and planning use the `caveman` skill. Find the code the issue touches and read it. Produce:

- The acceptance criteria, each written as a test name and the file it goes in.
- The files to change.
- Whether the change is a decision that needs an ADR under `docs/adrs/`.
- Anything in the issue that the code contradicts.

**Checkpoint: the maintainer approves the plan.**

### 3. Red — `test-driven-development`

Follow the `test-driven-development` skill's red step and verify-red step for every acceptance criterion. Write all the tests from the plan, run them, and report each test with the one line that shows it failing for the expected reason.

**Checkpoint: the maintainer approves the tests.**

### 4. Green — `/ponytail`

Implementation uses the `ponytail` skill, inside the `test-driven-development` skill's green and verify-green steps: the least code that makes the approved tests pass. A test does not change in this step; if one looks wrong, stop and say so.

### 5. Refactor and gates

The `test-driven-development` skill's refactor step, then every command in CONTRIBUTING.md's "Before opening a PR", in order. All must pass. Report any that do not, with the shortest decisive line of output.

### 6. Docs

- `CHANGELOG.md`: one entry under `## [Unreleased]`, written for a module maintainer, ending with the issue link, as CONTRIBUTING.md's "Resolving an issue" specifies. Caveman style: 40 words at most, fragments allowed. State what changed and what the module maintainer must do, if anything. No before-and-after story, nothing the README already says. Keep every command, path, flag and value exact.
- `README.md`: only if a user-visible command, flag or output changed.
- An ADR, if step 2 said one is needed.
- Docstrings and comments follow the Style section of `CLAUDE.md`.

The README, ADRs, docstrings and comments are normal English, not caveman.

### 7. Review — `/code-review`

Run `/code-review` over the working tree. Fix each confirmed finding through the same red-green loop when it changes behaviour. Run step 5's gates again.

### 8. Hand-off

Print, then stop:

1. **Proposed PR title**: a Conventional Commit, `<type>: <summary>` in the imperative, with `type` one of `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, `chore`.
2. **Proposed PR body**: [.github/PULL_REQUEST_TEMPLATE.md](../../../.github/PULL_REQUEST_TEMPLATE.md) filled in — `Fixes #N`, the Changes list, and each checklist box ticked only if it is true.
3. **Suggested commits**: the changed files grouped into commits in order — tests first, then the implementation, then docs — each with a message, so the history shows the tests came first.
