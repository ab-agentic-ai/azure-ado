# VS Code Coding Assistant Extension Design

## Intent

Provide a VS Code editor extension with a native chat panel that can inspect the user's workspace, explain code, propose edits, and help build software from inside VS Code. The extension is for coding work; the existing DevOps-Agent remains the read-only Azure DevOps assistant.

## Goals

- Add a **Coding Assistant** chat view and command in VS Code.
- Let the user include the active editor selection, the active file, or explicitly selected workspace files as context. Do not silently read or upload the whole workspace.
- Connect to the configured AChat server at a configurable base URL, defaulting to `http://127.0.0.1:3080`; users can enter the current Cloudflare URL. Quick Tunnel addresses change, so never bake one into the extension.
- Load the agents exposed to the signed-in user and send chat through LibreChat's remote-agent API.
- Authenticate as the user's AChat account without collecting or storing their AChat password. Sign-in opens AChat in the system browser; the user creates/copies a personal Agent API key in AChat Settings and enters it once in the extension. Store it in VS Code `SecretStorage`.
- Let the user select an AChat agent visible to their account. Do not route code tasks to the ADO-only DevOps-Agent unless the user explicitly selects it for an ADO question.
- Stream model replies and render Markdown and code blocks.
- Offer generated file changes as reviewable diffs. Apply a change only after the user confirms it; allow rejecting it.
- Ask for confirmation before running any terminal command. Never run generated commands automatically.
- Keep the extension read/write scope to the currently opened workspace and use VS Code APIs for file edits.
- Document how to connect AChat and install the packaged VSIX.

## Non-goals

- Reuse AChat's web UI or browser session cookies inside the extension. The extension has a native chat surface and uses the user's AChat Agent API key and agent access rules; AChat web login remains in the system browser.
- Use the read-only DevOps-Agent endpoint for code generation or workspace file changes.
- Automatically apply edits, execute commands, access files outside the opened workspace, or train/fine-tune model weights.
- Change Docker deployment, Cloudflare tunnel operation, or the Azure DevOps read-only behavior. The minimum LibreChat remote-agent permission is in scope as described below.

## Constraints

- The current local Qwen model runs in Ollama inside Docker. The extension should reach it through the authenticated AChat server and its configured agent, not by exposing Ollama directly.
- The DevOps-Agent endpoint at `/v1/chat/completions` interprets ADO requests and executes a fixed read-only ADO catalog. It is not a general coding endpoint and must not be used as one.
- The pinned LibreChat source provides a remote-agent API (`GET /api/agents/v1/models`, `POST /api/agents/v1/chat/completions`) authenticated with a personal Agent API key. This differs from the browser login cookie; opening the Cloudflare URL alone does not authenticate API requests.
- AChat must permit the user to create/use remote-agent API keys, and the agent owner/admin must grant remote access to a coding-capable agent; Marketplace visibility alone does not grant API access. Store the Agent API key in VS Code `SecretStorage`, never in settings or workspace files.
- LibreChat's `remoteAgents.use` permission defaults to false for regular users in the pinned source. Enable only `remoteAgents.use` for the intended user role; keep `create`, `share`, and `public` disabled unless separately required. The administrator still controls which agents users can access.
- Cloudflare Quick Tunnel URLs are temporary. Keep the AChat base URL in a VS Code setting so the user can update it after a tunnel restart; never store a Cloudflare tunnel token in the extension.
- Keep the extension in a separate `vscode-achatextension/` directory inside `azure-ado/`.

## Approaches

1. **Embed AChat in a sidebar webview.** Reuses AChat UI, sign-in, and Marketplace. It does not provide workspace context or controlled file editing without changes to AChat itself, and browser framing and session policies may prevent it from working reliably.
2. **Build a native VS Code coding assistant panel (selected).** Provides workspace-aware context, diffs, and approved commands using VS Code APIs while using AChat's authenticated remote-agent API. AChat login remains in the browser; API access uses the user's personal Agent API key, and only agents granted by AChat are listed.

The user accepted the workspace-aware coding assistant requirement. The native panel is selected because the extension must read selected workspace context and apply user-reviewed edits safely.

## Remaining implementation choices

- Expose an `achat.baseUrl` setting defaulting to `http://127.0.0.1:3080`; users can set it to the current Cloudflare AChat URL. Normalize trailing slashes and call `/api/agents/v1/models` and `/api/agents/v1/chat/completions` beneath it.
- Provide a **Sign in to AChat** command that opens the configured base URL in the system browser, then guide the user to create an Agent API key in AChat Settings and enter it through a secure VS Code secret prompt. Add **Sign out** to delete the stored key.
- Fetch authorized agents from `GET /api/agents/v1/models`; send streamed chat to `POST /api/agents/v1/chat/completions` using the selected agent ID and personal Agent API key.
- Enable the minimum LibreChat permission needed for user API keys (`remoteAgents.use`), while leaving remote agent creation and sharing disabled.
- Add commands to open the assistant, attach the current editor selection/file, review/apply/reject proposed edits, and confirm a proposed terminal command.
- Apply changes through `WorkspaceEdit` and show a diff before the user confirms.
- Include packaging instructions for installing the generated VSIX in VS Code.

## Acceptance criteria

- A user can ask a coding question and explicitly attach selected code or files from the open workspace.
- The assistant can propose a change, which appears in a VS Code diff; workspace files remain untouched until the user applies it.
- A proposed terminal command is shown for approval before execution.
- The extension never writes PATs, model API keys, or workspace file content into logs or configuration files.
- The extension uses the configured AChat base URL and a user-scoped Agent API key to list only agents with remote access granted to that account.
- Changing the AChat URL or revoking its Agent API key produces a clear reconnect/sign-in message; updating a Quick Tunnel URL requires only changing `achat.baseUrl`.
