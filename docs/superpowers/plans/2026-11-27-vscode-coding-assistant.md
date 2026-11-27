# VS Code Coding Assistant Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a VS Code extension that signs into AChat through a user-scoped Agent API key, chats with authorized AChat agents, uses explicitly attached workspace context, previews edits, and requires approval before applying edits or running commands.

**Architecture:** A TypeScript VS Code extension hosts a native webview chat panel. The extension host owns AChat API requests, SecretStorage, workspace reads, diff previews, WorkspaceEdits, and terminal approval; the webview only renders chat and sends user actions through a narrow message protocol. AChat supplies authorized agents and model responses through its LibreChat remote-agent API.

**Tech Stack:** VS Code Extension API, TypeScript extension host, HTML/CSS/JavaScript webview bundled by esbuild, Node fetch/AbortController, `diff` for unified diff parsing/applying, `marked` plus DOMPurify for safe Markdown rendering, `@vscode/vsce` for VSIX packaging.

**Spec:** `docs/superpowers/specs/2026-11-27-vscode-achatextension-design.md`

## Global Constraints

- Extension source lives under `vscode-achatextension/`.
- The base URL defaults to `http://127.0.0.1:3080`; Cloudflare URL remains user-configurable and is never hard-coded.
- Agent API keys are stored only with VS Code `SecretStorage`.
- Sign-in opens the AChat site in the browser; the extension never collects AChat passwords or reuses browser cookies.
- Remote chat uses `GET /api/agents/v1/models` and streaming `POST /api/agents/v1/chat/completions` with the user's selected AChat agent.
- Enable `remoteAgents.use` only; keep remote agent `create`, `share`, and `public` permissions disabled.
- Do not use the DevOps-Agent as a code-editing model by default; it is ADO focused and read-only.
- Send only user-attached selections/files; never scan or upload the workspace silently.
- Do not write generated edits or run generated commands without a separate user confirmation.
- Never send requests or API keys to a non-HTTPS remote origin; allow HTTP only for loopback addresses.

## Review Focus

- A stale Quick Tunnel URL or revoked API key must show a reconnection message; validate with a deliberately unreachable URL and a rejected credential during manual smoke checks.
- API-key entry, storage, and sign-out must not put the key in settings, logs, or workspace files; inspect generated configuration and extension logs during manual smoke checks.
- File attachments must remain within the open workspace and be explicitly selected; try a file outside the workspace and a large file during manual smoke checks.
- A malformed or path-traversing edit must be rejected; try absolute paths and `../` paths during manual smoke checks.
- A generated shell command must never execute until the user confirms it; cancel a command in the manual smoke check and verify the terminal was not started.

---

### Task 1: Scaffold extension and enable AChat remote-agent use

**Files:**
- Create: `vscode-achatextension/package.json`
- Create: `vscode-achatextension/package-lock.json`
- Create: `vscode-achatextension/tsconfig.json`
- Create: `vscode-achatextension/esbuild.mjs`
- Create: `vscode-achatextension/src/extension.ts`
- Create: `vscode-achatextension/.gitignore`
- Modify: `librechat.yaml` (`interface.remoteAgents`)
- Modify: `docs/superpowers/specs/2026-11-27-vscode-achatextension-design.md` only if a discovered implementation constraint changes the approved behavior.

**Interfaces:**
- Produces: extension commands `achat.open`, `achat.signIn`, `achat.signOut`, `achat.attachSelection`, `achat.attachFile`, `achat.reviewEdit`, and `achat.runCommand`.
- Produces: configuration keys `achat.baseUrl` and `achat.agentId` (empty agent ID means prompt/fetch selection at runtime).

- [x] Add VS Code extension metadata, activation events, command registrations, a `Coding Assistant` activity-bar container/view, compile scripts, and VSIX packaging scripts; include `@types/vscode`, esbuild, `diff`, `marked`, DOMPurify, and `@vscode/vsce` as pinned dependencies.
- [x] Configure `interface.remoteAgents.use: true` in `librechat.yaml`, explicitly leaving `create`, `share`, and `public` false; preserve all existing user edits and configuration.
- [x] Add the extension-host entry point and register commands, validating the base URL as HTTPS or loopback HTTP.
- [x] Run `npm run compile` and `npm run package` in `vscode-achatextension/`; expected output is a VSIX with no compile errors.

### Task 2: AChat sign-in, SecretStorage, and agent discovery

**Files:**
- Create: `vscode-achatextension/src/achatClient.ts`
- Create: `vscode-achatextension/src/auth.ts`
- Create: `vscode-achatextension/src/types.ts`
- Modify: `vscode-achatextension/src/extension.ts`
- Modify: `vscode-achatextension/package.json`

**Interfaces:**
- `AChatClient(baseUrl: string, apiKey: string)` exposes `listAgents(signal?: AbortSignal): Promise<AChatAgent[]>` and `streamChat(request: ChatRequest, onDelta: (text: string) => void, signal?: AbortSignal): Promise<ChatResult>`.
- `AuthManager` exposes `signIn(): Promise<void>`, `getApiKey(): Promise<string | undefined>`, and `signOut(): Promise<void>`.
- `AChatAgent` contains `id: string`, `name: string`, and optional `description: string`.
- `ChatMessage` contains `role: 'system' | 'user' | 'assistant'` and `content: string`; `ChatRequest` contains `model: string`, `messages: ChatMessage[]`, and `stream: true`; `ChatResult` contains optional `finishReason` and `usage`.

- [x] Implement **Sign in to AChat** by opening the configured URL with `vscode.env.openExternal`, then ask for the personal Agent API key with a password-style prompt and persist it via `context.secrets`.
- [x] Implement sign-out by deleting the stored secret; never include the key in log messages or settings.
- [x] Implement `GET {baseUrl}/api/agents/v1/models` using `Authorization: Bearer <key>`, with redirect rejection, timeout, cancellation, and readable 401/403/network errors.
- [x] Implement streaming `POST {baseUrl}/api/agents/v1/chat/completions`; parse SSE `data:` chunks, use `[DONE]` as stream completion, and surface provider errors without exposing credentials.
- [x] Add runtime agent selection from authorized `/api/agents/v1/models` results; persist only the selected agent ID in VS Code settings.
- [x] Require remote API access to the selected AChat coding agent (the agent owner grants it separately from Marketplace visibility).
- [ ] Exercise agent listing and streaming manually against an authorized account and confirm a revoked key/rotated tunnel URL yield clear recovery messages (requires the user's Agent API key).

### Task 3: Chat webview and explicit workspace context

**Files:**
- Create: `vscode-achatextension/src/chatView.ts`
- Create: `vscode-achatextension/src/context.ts`
- Create: `vscode-achatextension/media/chat.html`
- Create: `vscode-achatextension/media/chat.css`
- Create: `vscode-achatextension/media/chat.js`
- Modify: `vscode-achatextension/src/extension.ts`

**Interfaces:**
- `ChatContextItem` contains a workspace-relative `path`, `kind: 'selection' | 'file'`, and `content`.
- `collectSelection(editor: TextEditor): ChatContextItem | undefined` returns only the current selection.
- `collectFile(uri: Uri): Promise<ChatContextItem>` reads a user-picked file only after verifying it is within the active workspace.
- `ChatContextItem` also includes `id: string` and optional `truncated: boolean`; file attachments use the current in-memory editor buffer when the file is open.
- Webview-to-host messages are limited to `ready`, `refreshAgents`, `signIn`, `signOut`, `send`, `selectAgent`, `attachSelection`, `attachFile`, `removeAttachment`, `cancel`, `newChat`, and `reviewEdit`.

- [x] Implement a CSP-restricted webview with accessible message input, agent selector, streaming Markdown response display sanitized with DOMPurify, explicit attachment chips, loading/error states, and cancel action.
- [x] Implement attach-selection and attach-active-file commands; implement file picker for explicitly chosen files inside the open workspace.
- [x] Enforce context limits of 20,000 characters per file and 80,000 characters total; reject source files larger than 1 MB before reading, warn visibly when context is truncated, and do not attach files until user action.
- [x] Build chat requests from conversation turns, selected agent, attached content, and a clear instruction to answer normally unless the user requests an edit/command proposal.
- [x] Run `npm run compile`; launch an isolated VS Code Extension Host with the development extension (AChat interaction and workspace UI actions still require manual use with the user's account).

### Task 4: Reviewable code edits and approved commands

**Files:**
- Create: `vscode-achatextension/src/editProtocol.ts`
- Create: `vscode-achatextension/src/editReview.ts`
- Create: `vscode-achatextension/src/commandApproval.ts`
- Modify: `vscode-achatextension/src/chatView.ts`
- Modify: `vscode-achatextension/src/extension.ts`
- Modify: `vscode-achatextension/package.json`

**Interfaces:**
- Model edit proposal format is a fenced `achat-edit` JSON block: `{ "changes": [{ "path": "relative/path", "diff": "unified diff" }] }`.
- Model command proposal format is a fenced `achat-command` JSON block: `{ "command": "...", "cwd": "." }`.
- `parseEditProposals(text: string): EditProposal[]` rejects invalid JSON, absolute paths, paths escaping the workspace, and patches that do not apply cleanly.
- `reviewEdit(proposal: EditProposal): Promise<'applied' | 'rejected' | 'cancelled'>` opens a VS Code diff before applying a user-approved `WorkspaceEdit`.
- Command proposal `cwd` must resolve inside the active workspace; an empty workspace or an out-of-root directory is rejected.

- [x] Add response prompting and parsing for the `achat-edit` and `achat-command` blocks; keep normal answer text visible and treat malformed action blocks as inert text.
- [x] Validate every edit path against the workspace root, apply each diff to the current file content, stage proposed content in extension `globalStorageUri`, and open VS Code diff UI.
- [x] Add **Apply** and **Reject** actions; apply accepted changes through `WorkspaceEdit` only after rechecking original file contents.
- [x] Show every proposed terminal command and working directory in a modal confirmation; only after the user chooses **Run**, open the integrated terminal at the workspace and send the command.
- [x] Run `npm run compile`; automated and interactive apply/run checks were not performed in this build session.

### Task 5: Package and installation guide

**Files:**
- Create: `vscode-achatextension/README.md`
- Modify: `vscode-achatextension/package.json`
- Create: `vscode-achatextension/.vscodeignore`

**Interfaces:**
- Produces: `vscode-achatextension/achat-coding-assistant-<version>.vsix` and documented install/update steps.

- [x] Document prerequisites, enabling the AChat `remoteAgents.use` permission, granting remote access to the coding agent, signing in through the configured Cloudflare URL, creating/revoking the AChat Agent API key, configuring a changed Quick Tunnel URL, selecting an agent, attaching context, reviewing edits, and approving commands.
- [x] Add VSIX package metadata and ignore source-only files, credentials, `.env`, and temporary build artifacts.
- [x] Build and inspect the VSIX using `npm run compile`, `npm run package`, and `npx vsce ls`; expected output includes compiled extension/webview assets and no environment files or secrets.
- [x] Provide the exact VS Code **Install from VSIX...** steps and the extension command names.

---

## Plan self-review

- **Spec coverage:** The tasks cover native chat, secure AChat authentication, authorized agent listing, explicit context attachment, bounded context, diff-reviewed edits, command approvals, minimal LibreChat permission, and VSIX delivery.
- **Step scan:** Each task has a buildable component and concrete compile or manual acceptance check; no behavior is intentionally delegated to unspecified follow-up work.
- **Type consistency:** The API client uses the same `AChatAgent`, `ChatRequest`, `ChatResult`, and `AbortSignal` interfaces across Tasks 2 and 3; edit and command proposal schemas match the parser interfaces in Task 4.
- **Review focus:** Tunnel/auth failure, secret leakage, workspace boundary/truncation, path traversal/stale edits, and command cancellation are explicitly covered by manual smoke checks.
- **Proportion:** Five tasks separate extension scaffolding, API/auth, context/chat, controlled actions, and packaging without duplicating existing backend functions.
