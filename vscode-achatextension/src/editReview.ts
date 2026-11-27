import { createHash } from 'node:crypto';
import { lstat, mkdir, realpath, writeFile } from 'node:fs/promises';
import { dirname, relative, resolve, sep, isAbsolute } from 'node:path';
import * as vscode from 'vscode';
import { applyUnifiedDiff, EditProposal, isDeletePatch, validateRelativePath } from './editProtocol';

interface StagedEdit {
  uri: vscode.Uri;
  original: string;
  proposed: string;
  exists: boolean;
  deletesFile: boolean;
}

export async function reviewEdit(proposal: EditProposal, globalStorageUri: vscode.Uri): Promise<'applied' | 'rejected' | 'cancelled'> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) throw new Error('Open a workspace before reviewing code edits.');
  const staged = await Promise.all(proposal.changes.map((change) => stageChange(change.path, change.diff, workspace.uri, globalStorageUri)));
  for (const edit of staged) {
    await vscode.commands.executeCommand('vscode.diff', edit.originalUri, edit.proposedUri, `Proposed: ${vscode.workspace.asRelativePath(edit.uri, false)}`, { preview: false });
  }
  const choice = await vscode.window.showInformationMessage(
    `Review ${staged.length} proposed file change${staged.length === 1 ? '' : 's'} in the diff editor.`,
    { modal: true }, 'Apply All', 'Reject',
  );
  if (choice === 'Reject') return 'rejected';
  if (choice !== 'Apply All') return 'cancelled';

  const workspaceEdit = new vscode.WorkspaceEdit();
  for (const edit of staged) {
    await ensureInsideWorkspace(workspace.uri.fsPath, edit.uri.fsPath, edit.exists);
    if (!edit.exists) {
      try {
        await vscode.workspace.fs.stat(edit.uri);
        throw new Error(`${vscode.workspace.asRelativePath(edit.uri, false)} was created while the proposal was open.`);
      } catch (error) {
        if (!(error instanceof vscode.FileSystemError && error.code === 'FileNotFound')) throw error;
      }
      workspaceEdit.createFile(edit.uri, { overwrite: false, ignoreIfExists: false });
      workspaceEdit.insert(edit.uri, new vscode.Position(0, 0), edit.proposed);
      continue;
    }
    const document = await vscode.workspace.openTextDocument(edit.uri);
    if (document.getText() !== edit.original) {
      throw new Error(`${vscode.workspace.asRelativePath(edit.uri, false)} changed since the proposal was reviewed. Recreate the proposal against the latest file.`);
    }
    if (edit.deletesFile) {
      workspaceEdit.deleteFile(edit.uri);
      continue;
    }
    const end = document.lineAt(document.lineCount - 1).range.end;
    workspaceEdit.replace(edit.uri, new vscode.Range(new vscode.Position(0, 0), end), edit.proposed);
  }
  const applied = await vscode.workspace.applyEdit(workspaceEdit);
  if (!applied) throw new Error('VS Code could not apply the approved edit.');
  return 'applied';
}

async function stageChange(path: string, patch: string, rootUri: vscode.Uri, storageUri: vscode.Uri): Promise<StagedEdit & { proposedUri: vscode.Uri; originalUri: vscode.Uri }> {
  if (rootUri.scheme !== 'file') throw new Error('Edit previews currently require a local file workspace.');
  const relativePath = validateRelativePath(path, rootUri.fsPath);
  const uri = vscode.Uri.joinPath(rootUri, ...relativePath.split('/'));
  let original = '';
  let exists = true;
  try {
    original = Buffer.from(await vscode.workspace.fs.readFile(uri)).toString('utf8');
  } catch (error) {
    if (isNotFound(error)) exists = false;
    else throw error;
  }
  await ensureInsideWorkspace(rootUri.fsPath, uri.fsPath, exists);
  const document = vscode.workspace.textDocuments.find((item) => item.uri.toString() === uri.toString());
  if (document?.isDirty) original = document.getText();
  const proposed = applyUnifiedDiff(original, patch, relativePath);
  const key = createHash('sha256').update(relativePath).digest('hex');
  const proposedUri = vscode.Uri.joinPath(storageUri, 'review', `${key}.proposed`);
  const originalUri = vscode.Uri.joinPath(storageUri, 'review', `${key}.original`);
  const proposedFsPath = resolve(proposedUri.fsPath);
  await mkdir(dirname(proposedFsPath), { recursive: true });
  await writeFile(proposedFsPath, proposed, { encoding: 'utf8', mode: 0o600 });
  await writeFile(resolve(originalUri.fsPath), original, { encoding: 'utf8', mode: 0o600 });
  return { uri, original, proposed, exists, deletesFile: isDeletePatch(patch), proposedUri, originalUri };
}

async function ensureInsideWorkspace(rootPath: string, candidatePath: string, candidateExists: boolean): Promise<void> {
  const rootReal = await realpath(rootPath);
  let targetReal: string;
  if (candidateExists) {
    targetReal = await realpath(candidatePath);
  } else {
    try {
      const candidateInfo = await lstat(candidatePath);
      if (candidateInfo.isSymbolicLink()) {
        throw new Error('Cannot create a new file through a symbolic link.');
      }
      targetReal = await realpath(candidatePath);
    } catch (error) {
      if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
      const parentReal = await realpath(dirname(candidatePath));
      targetReal = resolve(parentReal, candidatePath.slice(dirname(candidatePath).length + 1));
    }
  }
  const fromRoot = relative(rootReal, targetReal);
  if (!fromRoot || fromRoot === '..' || fromRoot.startsWith(`..${sep}`) || isAbsolute(fromRoot)) {
    throw new Error('Edit targets must remain inside the real workspace directory, including through symlinks.');
  }
}

function isNotFound(error: unknown): boolean {
  return error instanceof vscode.FileSystemError && error.code === 'FileNotFound';
}
