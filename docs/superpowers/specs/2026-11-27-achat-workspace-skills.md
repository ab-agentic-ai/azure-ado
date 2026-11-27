# AChat Workspace Skills Design

## Intent

Let AChat use project-local `SKILL.md` guidance while writing or updating code, so workspace-specific workflows such as code generation and extension maintenance are followed.

## Goals and bounds

- Discover skills only inside the currently open VS Code workspace; do not read `~/.codex/skills` or other global paths.
- Support conventional project locations such as `.agents/skills/`, `.codex/skills/`, `.github/skills/`, and other workspace-local `SKILL.md` paths.
- Match skills to each request using their front-matter `name` and `description`, and provide a manual picker override.
- Read only matching skill files, with limits on file count, per-file size, and total injected text. Preserve the existing workspace context budget.
- Treat skill text as project guidance only. It cannot authorize shell execution, network calls, credential access, or writes outside the workspace.

## Approaches considered

1. Automatically match workspace skills and offer a manual picker. **Chosen:** useful by default while still letting users choose a skill when matching misses.
2. Require a manual skill choice for every message. Predictable, but adds friction to routine code writing.
3. Bundle fixed Code Writer and Extension Updater skills into AChat. Easy to start, but cannot reflect each repository's conventions and becomes difficult to maintain.

## Proposed behavior

For coding requests, AChat indexes bounded workspace-local `SKILL.md` metadata, selects the best matching skills, and includes only those instructions with the prompt. A command opens a picker of discovered skills for explicit selection; choosing none returns to automatic matching. AChat indicates which skills were applied. If no skill matches, it behaves as it does today.

## Constraints and acceptance

Do not read global skill directories or dependencies/build output. Reject paths outside the workspace and ignore oversized or unreadable skill files. Skill instructions remain subordinate to system safety rules and explicit user requests. A successful build should show a clear applied-skill notice, and an empty/no-match index should leave chat behavior unchanged.
