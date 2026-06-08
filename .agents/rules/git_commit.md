---
trigger: always_on
description: ensures code is committed, but not to the `main` branch
---

# Git Commit and Branching Rules

These rules must be followed by any AI agent working on this repository when finishing an implementation or a task.

## Triggering Condition
- After an implementation plan is finished and all changes are successfully made, verified, and tested.

## Branch Management
Before committing or pushing any changes, the agent must check the current git branch.
- **If the current branch is `main` (or `master`):**
  1. Determine a meaningful branch name based on the task performed (e.g., `feature/add-git-commit-rules`, `fix/issue-triage-bug`).
  2. Create and switch to the new branch:
     ```bash
     git checkout -b <meaningful-branch-name>
     ```
  3. Never commit directly to the `main` or `master` branch.
- **If the current branch is already a feature/topic branch (not `main`/`master`):**
  - Proceed with committing on the current branch.

## Commit Guidelines
- Stage all changes using `git add` (e.g., `git add .` or stage specific modified/added files, while respecting `.gitignore`).
- Commit all staged changes with a meaningful git commit message:
  ```bash
  git commit -m "<meaningful git message>"
  ```
- Make sure the commit message is clear, descriptive, and accurately reflects the modifications.
