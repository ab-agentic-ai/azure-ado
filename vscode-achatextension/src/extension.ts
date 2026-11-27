import * as vscode from 'vscode';
import { ChatView } from './chatView';

const VIEW_ID = 'achat.chat';

export function activate(context: vscode.ExtensionContext): void {
  const chatView = new ChatView(context);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(VIEW_ID, chatView, { webviewOptions: { retainContextWhenHidden: true } }),
    vscode.commands.registerCommand('achat.open', () => vscode.commands.executeCommand('workbench.view.extension.achat')),
    vscode.commands.registerCommand('achat.signIn', async () => {
      try { await chatView.signIn(); }
      catch (error) { void vscode.window.showErrorMessage(error instanceof Error ? error.message : 'Could not connect to AChat.'); }
    }),
    vscode.commands.registerCommand('achat.signOut', () => chatView.signOut()),
    vscode.commands.registerCommand('achat.attachSelection', () => chatView.attachSelection()),
    vscode.commands.registerCommand('achat.attachFile', () => chatView.attachFile()),
    vscode.commands.registerCommand('achat.analyzeWorkspace', () => chatView.analyzeWorkspace()),
    vscode.commands.registerCommand('achat.chooseWorkspaceSkills', () => chatView.chooseWorkspaceSkills()),
    vscode.commands.registerCommand('achat.reviewEdit', () => chatView.reviewLatestAction('edit')),
    vscode.commands.registerCommand('achat.runCommand', () => chatView.reviewLatestAction('command')),
  );
}

export function deactivate(): void {}
