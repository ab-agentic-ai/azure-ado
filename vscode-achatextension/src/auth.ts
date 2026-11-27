import * as vscode from 'vscode';

const SECRET_KEY = 'achat.agentApiKey';

export class AuthManager {
  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly getBaseUrl: () => string,
  ) {}

  async signIn(): Promise<void> {
    const baseUrl = this.getBaseUrl();
    const opened = await vscode.env.openExternal(vscode.Uri.parse(baseUrl));
    if (!opened) {
      throw new Error('Could not open AChat in your browser. Open the configured AChat URL, sign in, then try again.');
    }

    const apiKey = await vscode.window.showInputBox({
      title: 'Connect VS Code to AChat',
      prompt: 'Sign in in the browser, then create an Agent API key in AChat Settings → Data & Privacy → Agent API Keys.',
      placeHolder: 'Paste the personal AChat Agent API key',
      password: true,
      ignoreFocusOut: true,
      validateInput: (value) => value.trim() ? undefined : 'Enter an AChat Agent API key.',
    });
    if (!apiKey) {
      return;
    }
    await this.context.secrets.store(SECRET_KEY, apiKey.trim());
    void vscode.window.showInformationMessage('AChat Agent API key saved securely in VS Code.');
  }

  async getApiKey(): Promise<string | undefined> {
    return await this.context.secrets.get(SECRET_KEY);
  }

  async signOut(): Promise<void> {
    await this.context.secrets.delete(SECRET_KEY);
    void vscode.window.showInformationMessage('AChat Agent API key removed from VS Code.');
  }
}
