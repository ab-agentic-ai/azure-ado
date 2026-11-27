# AChat VS Code Coding Assistant Design

## Intent

Make the native AChat VS Code extension feel simple and familiar, with a Codex/Claude-style conversation and composer, while automatically giving coding agents bounded context from the open workspace.

## Workspace behavior

- Before each coding-agent message is sent, create a fresh snapshot of the current open workspace; no file picker or scan confirmation is required.
- Combine explicit attachments first, then use remaining room from the existing 80,000-character cap for the snapshot.
- Keep the current 300-candidate ceiling, source/text allowlist, 1 MB per-file limit, and sensitive/generated/dependency exclusions.
- Skip automatic workspace context for DevOps/ADO agents. Keep Analyze Workspace as an explicit, confirmed summary flow.
- Scanning is local; data is sent only when the user presses Send. Show an in-transcript context label and mark partial scans.

## Interface

- Use a compact AChat toolbar and a centered, readable conversation layout inspired by Codex and Claude.
- Move the agent selector into the composer so the selected agent is visible at the point of writing.
- Keep the composer pinned at the bottom, theme-aware, translucent/softly layered, and responsive to a narrow activity-bar view.
- Retain attachment chips, selection/file controls, workspace analysis, Stop, and review-before-apply proposal controls.
- Use the new AChat logo in the toolbar and extension package metadata/icon.

## Safety and limits

- Automatic scanning never reads outside open workspace roots.
- Keep file edits and terminal operations behind their existing explicit review flows.
- A partial snapshot must say it is partial and never imply omitted content was read.
- Do not cache snapshots across sends.

## Acceptance criteria

- Normal coding prompts automatically include a fresh workspace snapshot, with no picker/modal.
- Explicit attachments remain included and take precedence within the context limit.
- DevOps/ADO queries remain isolated from local source context.
- The chat view has a compact header, composer agent selector, centered conversation, theme-aware composer, and AChat logo.
- Large workspaces remain bounded and visibly labeled as partial.
