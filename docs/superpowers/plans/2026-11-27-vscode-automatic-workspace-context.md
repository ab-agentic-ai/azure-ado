# AChat VS Code Context and Interface Plan

**Goal:** Make the native AChat extension attach bounded current-workspace context automatically and give it a compact Codex/Claude-inspired chat layout.

**Architecture:** Extract the existing workspace scanner into a reusable collector. Normal coding-agent sends combine explicit attachments and a fresh transient snapshot. Keep the ADO agent path isolated. Move the agent selector into the composer and reuse the existing VS Code theme variables for the layout.

**Tech stack:** VS Code Extension API, TypeScript, webview HTML/CSS/JavaScript, AChat remote-agent API.

## Constraints

- Keep the 80,000-character total context bound, 300-candidate scan ceiling, 1 MB file limit, allowlist, and exclusions.
- Send workspace data only after the user presses Send; snapshots are fresh per message and never cached.
- Explicit attachments consume context before automatic snapshot content.
- Do not add or run tests unless requested. Run compile/typecheck and diff checks only.

## Tasks

### 1. Reusable bounded snapshot collector

- Extract path discovery, filtering, ordering, inventory, and truncation into a collector that accepts a character budget.
- Keep Analyze Workspace as the existing modal-confirmation and summary-prompt workflow.
- On regular coding-agent sends, collect a fresh snapshot using the capacity left after explicit attachments.
- Skip automatic source context for DevOps/ADO agents; preserve current routing guard.
- Include transient context and partial-coverage metadata in the sent user turn and transcript.
- Continue the prompt normally when no workspace exists or scanning fails.

### 2. Codex/Claude-inspired native chat layout

- Replace the prominent colored header with a compact brand toolbar.
- Put the agent picker beside the attachment and action controls in the composer.
- Center the conversation with a readable max width and keep the responsive composer at the bottom.
- Retain all existing attachment, stop, status, command, and edit-review controls.
- Apply VS Code theme tokens and restrained translucent layering so dark/light themes work.

### 3. AChat logo and package metadata

- Use `media/achat-icon.png` in the toolbar and as extension package icon.
- Bump the local package version and update the VSIX output name and install instructions.

### 4. Documentation and review

- Document automatic scanning, exclusions, limits, send-time behavior, and ADO-agent isolation.
- Run `npm run compile`, `git diff --check`, and inspect the final diff. Do not run tests.
