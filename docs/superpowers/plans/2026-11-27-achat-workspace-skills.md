# AChat Workspace Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AChat apply relevant project-local `SKILL.md` guidance to coding conversations, with automatic matching and a manual override.

**Architecture:** Add a workspace-only skill indexer that parses standard Markdown front matter, ranks skills against the current prompt, and bounds all reads. `ChatView` will attach selected skill instructions to that request and expose a Quick Pick command for manual selection; skills remain ephemeral context and never authorize commands or out-of-workspace writes.

**Tech Stack:** TypeScript, VS Code extension API, Node path/file APIs; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-27-achat-workspace-skills.md`

## Global Constraints

- Search only open workspace folders; never read global `~/.codex/skills` or other external paths.
- Discover at most 100 workspace-local `SKILL.md` files, each no larger than 128 KiB.
- Select at most 3 skills automatically or manually, cap each body at 12,000 characters, and cap total injected skill text at 24,000 characters.
- Never follow skill requests to reveal credentials, run shell commands, access network services, override user intent, or write outside the workspace.
- Preserve the existing 80,000-character workspace context cap and existing shell-command approval behavior.
- Keep using the repository's current dependencies and TypeScript build.

## Review Focus

- A nested or symlinked skill path must not escape the workspace; reject paths outside each real workspace root.
- Invalid/missing front matter, unreadable files, and oversized files must be skipped without failing chat.
- Empty/no-match skill catalogs must preserve current request behavior.
- Manual selections must be bounded and resettable to automatic matching.
- Skill text must not displace explicit attachments or cause the automatic code snapshot to exceed its context budget.

---

### Task 1: Discover and rank project skills

**Files:**
- Create: `vscode-achatextension/src/skillContext.ts`
- Modify: `vscode-achatextension/src/types.ts` only if a shared skill type is useful

**Interfaces:**
- Produces `WorkspaceSkill` with `name`, `description`, `relativePath`, and bounded `instructions`.
- Produces `discoverWorkspaceSkills()` for bounded workspace indexing and `matchWorkspaceSkills(prompt, skills, limit)` for deterministic local ranking.
- Produces a formatter that budgets selected instructions under the 24,000-character aggregate cap.

- [ ] Search for workspace-local `**/SKILL.md` files, including hidden in-workspace skill folders, while excluding dependencies, generated output, secrets, and VCS metadata; cap discovery at 100 paths.
- [ ] Validate each URI remains under its containing workspace folder, reject files larger than 128 KiB, parse YAML-style `name` and `description` front matter without adding a parser dependency, and skip invalid/unreadable documents.
- [ ] Rank skills by overlap between normalized prompt terms and front-matter name/description, return at most 3 positive matches, and cap instruction text at 12,000 characters per skill and 24,000 total.
- [ ] Review the new module against the spec’s path, size, parse-failure, and empty-index constraints.

### Task 2: Attach automatic or manually selected skills

**Files:**
- Modify: `vscode-achatextension/src/chatView.ts`
- Modify: `vscode-achatextension/src/extension.ts`
- Modify: `vscode-achatextension/package.json`

**Interfaces:**
- `ChatView` will expose `chooseWorkspaceSkills()` and retain an optional manual selection for the active extension session.
- Add command `achat.chooseWorkspaceSkills` / title `AChat: Choose Workspace Skills`.
- `undefined` manual selection means automatic matching; choosing **Automatic matching** clears the override.

- [ ] Register the contributed command and dispatch it to `ChatView`.
- [ ] Discover skills on demand; show name, description, and relative path in a multi-select Quick Pick with an **Automatic matching** reset action.
- [ ] Before a coding request, use manual selection if set; otherwise rank against the prompt. Add only selected instructions to the current request, never to retained history.
- [ ] Subtract skill and attachment characters from the automatic workspace snapshot budget, and post an informational notice naming the applied skills.
- [ ] Extend the system instructions to treat selected `SKILL.md` text as project coding guidance, subordinate to user intent and safety constraints; keep shell commands approval-gated.

### Task 3: Document and package the feature

**Files:**
- Modify: `vscode-achatextension/README.md`
- Modify: `vscode-achatextension/package.json`
- Modify: `vscode-achatextension/package-lock.json`

- [ ] Document supported workspace-local skill paths, automatic matching, the Quick Pick override/reset, and the size/path safety bounds.
- [ ] Bump the extension patch version and keep package script/artifact version references in sync.
- [ ] Run `npm run package` and `git diff --check`; inspect the VSIX contents to confirm the new module is bundled.
- [ ] Compare the finished implementation against every spec constraint; do not add or run tests unless requested.
