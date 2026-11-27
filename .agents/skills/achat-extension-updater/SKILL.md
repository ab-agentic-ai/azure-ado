---
name: achat-extension-updater
description: Use when asked to develop, maintain, rebuild, package, install, or troubleshoot the AChat Visual Studio Code extension.
---

# AChat Extension Updater

## Before changing the extension

1. Locate the extension under `vscode-achatextension` and read its `package.json`, README, relevant TypeScript source, and applicable workspace instructions.
2. Inspect the current Git state. Preserve user changes and existing branding, including the AChat name and custom marketplace logo/assets.
3. Trace the feature through its command, UI, API, and configuration paths before changing behavior. Keep manifest contributions, implementation, documentation, and package metadata aligned.

## Implementation

- Keep TypeScript source authoritative and use existing project build/package scripts rather than hand-editing generated bundles.
- For code-writing features, ensure proposed files are applied to the open workspace through the extension’s supported edit/apply flow; do not present a patch as though it was written when it was only shown in chat.
- For workspace analysis, use the active VS Code workspace and its readable source files, respecting ignore rules and excluding credentials, dependencies, and generated output unless specifically requested.
- Keep user confirmation for edits or shell operations where the extension’s approval workflow requires it. Never bypass approval controls.
- Do not place provider keys, ADO PATs, tunnel tokens, or other secrets in source, logs, or extension output.
- Preserve the AChat identity and existing custom marketplace assets when updating, building, or packaging.

## Rebuild and handoff

- When asked to rebuild/package, use the documented package script from the extension directory and keep the extension version and VSIX artifact filename consistent.
- Verify the package/build result and inspect the resulting VSIX contents before claiming success.
- Do not install or publish a VSIX unless the user requests that action.
- Tell the user the exact artifact path and any required VS Code reload/restart step. Never trigger a reload while an unsaved editor is open.
