# CLAUDE.md

Instructions for Claude Code when working in this repository.

## Git command policy

- **Allowed without asking:** `git diff`, `git pull`, `git status`, `git log`, and other read-only/inspection commands. Run these freely.
- **Never run directly:** `git commit`, `git push`, `git merge`, `git rebase`, `git reset`, `git checkout -- <file>`, `git clean`, branch deletion, force-push, or any command that deletes files, deletes branches, or otherwise mutates repo/shared state.
- For anything in the "never run directly" category, do not execute it. Instead, present the exact command to the user and let them run it themselves. Only execute it yourself if the user explicitly tells you to.
- This applies to all delete operations in general (files, branches, remote refs), not just git — always surface the command and ask, rather than run it.

## README and tests

- After every code change, update the `README` to reflect the change (new behavior, usage, setup steps, etc.) if it is affected.
- After every code change, update or add tests covering the change.
- Treat README and test updates as part of the change itself, not a follow-up step — do them in the same turn as the code change.


## Access Instructions
- Ignore all files that are starting with ".", You are not permitted to view or access them
- All commands like cd or ls which are read or view only options does not need user permission


