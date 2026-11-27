# AChat Coding Assistant for VS Code

Chat with agents hosted by your AChat server from Visual Studio Code. The compact chat view places agent selection in the composer, gathers fresh open-workspace context when you send a coding-agent prompt, and shows proposed code in VS Code's diff editor for review before applying edits or running terminal commands.

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

1. Obtain `achat-coding-assistant-0.1.11.vsix` from the release/artifact supplied by your administrator.
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

- Ask coding questions directly. The composer lets you choose the agent for each chat.
- Select code in an editor and use **AChat: Attach Editor Selection**, or use the paperclip control to attach the active file or choose workspace files.
- Workspace scanning runs locally on each send for coding agents, so prompts such as “explain this project” do not require a file picker or a separate scan action. A fresh snapshot is included with that turn only; earlier automatic snapshots are not resent on later turns.
- The total context is bounded to 80,000 characters and the scan examines up to 300 candidate files, each at most 1 MB. It prioritizes project manifests and source files, then configuration and documentation. It excludes credentials, dependency/build folders, and common private metadata folders. If the workspace is too large, the transcript labels the snapshot as partial and the model is instructed not to claim it read omitted files.
- Explicitly attached selections and files are retained and take priority within the context limit. Sensitive-looking file names still require confirmation when attached manually. Files outside the open workspace are rejected.
- The **Analyze workspace** action remains for a focused codebase summary. It shows a confirmation before staging its snapshot; the contents are sent only when you submit the prompt.
- DevOps-Agent does not receive local source snapshots automatically. Use it for Azure DevOps questions. For workspace coding, choose a coding agent.
- AChat never scans or sends files before you submit a message.

## Use project skills

- Add a `SKILL.md` with `name` and `description` front matter under `.agents/skills/`, `.codex/skills/`, `.github/skills/`, or another folder in the open workspace. For example:

  ```markdown
  ---
  name: code-writer
  description: Use when creating or updating code in this repository.
  ---
  Follow the repository's coding conventions and explain meaningful changes.
  ```

- For coding requests, AChat matches the prompt against skill names and descriptions, then attaches only the best matching instructions. It reports the skills used in the chat.
- Run **AChat: Choose Workspace Skills** from the Command Palette to select skills manually. Choose **Automatic matching** to clear the manual selection. Manual choices last for the current extension session.
- Discovery is limited to 100 project-local `SKILL.md` files, each no larger than 128 KiB. AChat reads only their front matter while matching; selected instructions are limited to 12,000 characters per skill and 24,000 characters total.
- Skill discovery currently supports local file workspaces. Skills outside the open workspace are not read. Symlink paths that resolve outside a workspace folder, dependencies, generated output, and secrets folders are excluded. Skill text cannot authorize shell commands, network access, credential access, or writes outside the workspace.

## Review edits and commands

When you explicitly ask for code to be created or changed, AChat applies a valid file-change proposal directly to the open workspace by default and opens the first changed file. If a model returns regular Markdown source blocks instead, AChat saves each supported source block for explicit code-writing requests; it ignores shell/terminal blocks. `File:` or `Script:` headings supply filenames when present. Otherwise it infers a filename for Azure DevOps project scripts (`ado_project_details.py` for Python) or uses `generated_code.<extension>`. Existing files are never overwritten: AChat adds a numbered suffix if a suggested name already exists. This is limited to validated paths inside the workspace; shell commands are never run automatically. Set `achat.autoApplyEdits` to `false` in VS Code Settings to require the regular code-block **Save code…** flow and review proposed edits.

When you ask to run a shell operation, the model can return an `achat-command` proposal. Select **Review command** to inspect the full command and working directory. The command is sent to the integrated terminal only after you choose **Run in Terminal**. Review commands carefully; approved shell commands can change or remove files.

## Commands

- **AChat: Open Coding Assistant**
- **AChat: Sign In** / **AChat: Sign Out**
- **AChat: Attach Editor Selection**
- **AChat: Attach File**
- **AChat: Choose Workspace Skills**
- **AChat: Review Proposed Edit** / **AChat: Review Proposed Command** (proposal actions are normally available directly below an assistant response)

## Build the VSIX locally

```sh
cd azure-ado/vscode-achatextension
npm ci
npm run compile
npm run package
```

The generated file is `achat-coding-assistant-0.1.11.vsix` in this directory. The package icon and chat header use the AChat logo in `media/achat-icon.png`.
