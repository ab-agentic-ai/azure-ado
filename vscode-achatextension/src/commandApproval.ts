import { resolve, relative, isAbsolute, sep } from 'node:path';
import { realpath } from 'node:fs/promises';
import * as vscode from 'vscode';
import { CommandProposal, validateRelativePath } from './editProtocol';

export async function reviewCommand(proposal: CommandProposal): Promise<'run' | 'rejected' | 'cancelled'> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) throw new Error('Open a workspace before running a proposed command.');
  const cwdRelative = validateRelativePath(proposal.cwd, workspace.uri.fsPath, true);
  const cwd = resolve(workspace.uri.fsPath, cwdRelative);
  if (workspace.uri.scheme !== 'file') throw new Error('Command proposals currently require a local file workspace.');
  const rootReal = await realpath(workspace.uri.fsPath);
  const cwdReal = await realpath(cwd);
  const realRelative = relative(rootReal, cwdReal);
  if (realRelative.startsWith(`..${sep}`) || realRelative === '..' || isAbsolute(realRelative)) {
    throw new Error('The proposed command directory resolves outside the workspace.');
  }
  const cwdStat = await vscode.workspace.fs.stat(vscode.Uri.file(cwdReal));
  if ((cwdStat.type & vscode.FileType.Directory) === 0) throw new Error('The proposed command working directory is not a folder.');
  const withinWorkspace = relative(resolve(workspace.uri.fsPath), cwd);
  if (withinWorkspace === '..' || withinWorkspace.startsWith(`..${sep}`) || isAbsolute(withinWorkspace)) {
    throw new Error('The proposed command directory is outside the workspace.');
  }
  const choice = await vscode.window.showWarningMessage(
    `Run this command in ${cwdRelative || '.'}?\n\n${proposal.command}`,
    { modal: true }, 'Run in Terminal', 'Reject',
  );
  if (choice === 'Reject') return 'rejected';
  if (choice !== 'Run in Terminal') return 'cancelled';

  const terminal = vscode.window.createTerminal({ name: 'AChat Approved Command', cwd: cwdReal });
  terminal.show(true);
  terminal.sendText(proposal.command, true);
  return 'run';
}
