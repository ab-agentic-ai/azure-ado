---
name: code-writer
description: Use when asked to create, implement, update, refactor, debug, or fix source code in this workspace.
---

# Code Writer

## Workflow

1. Inspect the current workspace structure, relevant source files, and project instructions before editing.
2. Identify the smallest complete change that satisfies the request. Follow existing languages, conventions, and architecture.
3. For changes spanning multiple files, keep related interfaces, configuration, documentation, and generated artifacts consistent.
4. Make edits directly in the workspace when the user asks for implementation. Do not leave code only in a chat response when the workspace is available.
5. Preserve existing user changes. Read a file before editing it, and avoid replacing unrelated content.
6. Explain assumptions when requirements are unclear; prefer a safe, useful default when they are not blocking.

## Safety and verification

- Do not put credentials, access tokens, or private configuration values in source files. Use the project’s established secret mechanism and provide placeholders in examples.
- Do not run generated programs, shell commands, deployments, or destructive operations unless the user requested or approved that action.
- Do not add or run tests unless requested; use the project’s build or static checks when needed to validate an implementation.
- Report what changed and what verification was run, including failures or limitations.
