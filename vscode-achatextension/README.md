# AChat Coding Assistant for VS Code

Chat with agents hosted by your AChat server from Visual Studio Code. The extension can use explicitly attached editor selections and files as context, show model-proposed code in VS Code's diff editor, and ask before applying edits or running terminal commands.

## Requirements

- Visual Studio Code 1.96 or later.
- An AChat server reachable from VS Code. Local default: `http://127.0.0.1:3080`. For remote use, configure your current HTTPS Cloudflare Tunnel URL.
- An AChat user account and a personal Agent API key.
- Remote Access enabled for the agents you want to use.

The AChat administrator enables the Remote Agents API in `librechat.yaml`:

```yaml
interface:
  remoteAgents:
    use: true
    create: false
    share: false
    public: false
```

The owner of each custom agent must separately grant Remote Access. Marketplace visibility by itself does not grant API access.

## Install from VSIX

1. Obtain `achat-coding-assistant-0.1.1.vsix` from the release/artifact supplied by your administrator.
2. In VS Code, open **Extensions** (`⇧⌘X` on macOS or `Ctrl+Shift+X` on Windows/Linux).
3. Select the **…** menu in the Extensions view.
4. Choose **Install from VSIX…** and select the `.vsix` file.
5. Reload VS Code if prompted. Select the **AChat** icon in the Activity Bar.

To update, install the newer VSIX using the same command.

## Connect to AChat

1. If AChat is not running locally, open **Settings → Extensions → AChat Coding Assistant** and set `achat.baseUrl` to the current HTTPS tunnel URL. Quick Tunnel URLs can change after restart.
2. Open **AChat → Coding Assistant** in the Activity Bar and select **Sign in**. This opens AChat in your browser.
3. Create a personal Agent API key in AChat's **Settings → Data & Privacy → Agent API Keys**, then paste that key in the secure VS Code prompt.
4. Select an available agent in the chat panel. If an agent is missing, ask its owner to grant Remote Access and refresh the list.

The API key is stored in VS Code SecretStorage, not in workspace files or settings. **Sign out** removes it from VS Code.

## Use workspace context

- Ask general questions directly.
- Select code in an editor and use **AChat: Attach Editor Selection**, or use the paperclip control to attach the active file or choose workspace files.
- Attachments are shown in the composer and are sent only when you submit a prompt. Files outside the active workspace are rejected. Large files and total context are bounded; sensitive-looking file names require an additional confirmation.
- To analyze local project code, select **Analyze workspace** in the composer. Choose the relevant files in the picker and confirm; only then are they attached. They are sent to AChat when you submit a prompt. Common credentials and build/dependency folders are excluded, and only supported text/source files up to 1 MB each are offered. The picker lists up to 300 files.
- The extension never scans or sends workspace contents in the background. For DevOps-Agent, ask ADO questions without attaching source files.

## Review edits and commands

When you ask for a code change, the model can return an `achat-edit` proposal. Select **Review and apply changes** to open a side-by-side diff, then choose **Apply All** or **Reject**. The extension checks that each path remains inside the workspace and that source files have not changed since the proposal was reviewed.

When you ask to run a shell operation, the model can return an `achat-command` proposal. Select **Review command** to inspect the full command and working directory. The command is sent to the integrated terminal only after you choose **Run in Terminal**. Review commands carefully; approved shell commands can change or remove files.

## Commands

- **AChat: Open Coding Assistant**
- **AChat: Sign In** / **AChat: Sign Out**
- **AChat: Attach Editor Selection**
- **AChat: Attach File**
- **AChat: Review Proposed Edit** / **AChat: Review Proposed Command** (proposal actions are normally available directly below an assistant response)

## Build the VSIX locally

```sh
cd azure-ado/vscode-achatextension
npm ci
npm run compile
npm run package
```

The generated file is `achat-coding-assistant-0.1.1.vsix` in this directory.
