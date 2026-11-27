import { createHash } from 'node:crypto';
import { lstat, mkdir, realpath, writeFile } from 'node:fs/promises';
import { dirname, relative, resolve, sep, isAbsolute } from 'node:path';
import * as vscode from 'vscode';
import { applyUnifiedDiff, EditProposal, isDeletePatch, ProposedChange, validateRelativePath } from './editProtocol';

interface StagedEdit {
  uri: vscode.Uri;
  original: string;
  proposed: string;
  exists: boolean;
  deletesFile: boolean;
}

export async function reviewNewFile(relativePath: string, content: string, globalStorageUri: vscode.Uri): Promise<'applied' | 'rejected' | 'cancelled'> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) throw new Error('Open a workspace before saving generated code.');
  if (workspace.uri.scheme !== 'file') throw new Error('Saving generated code currently requires a local file workspace.');
  if (!content.trim()) throw new Error('There is no code to save.');

  const safePath = validateRelativePath(relativePath, workspace.uri.fsPath);
  const targetUri = vscode.Uri.joinPath(workspace.uri, ...safePath.split('/'));
  try {
    await vscode.workspace.fs.stat(targetUri);
    throw new Error(`${safePath} already exists. Choose another path to avoid overwriting it.`);
  } catch (error) {
    if (!isNotFound(error)) throw error;
  }
  await ensureInsideWorkspace(workspace.uri.fsPath, targetUri.fsPath, false);

  const previewId = createHash('sha256').update(`${safePath}\0${content}`).digest('hex');
  const previewRoot = vscode.Uri.joinPath(globalStorageUri, 'review');
  const originalUri = vscode.Uri.joinPath(previewRoot, `${previewId}.empty`);
  const proposedUri = vscode.Uri.joinPath(previewRoot, `${previewId}.new`);
  await mkdir(previewRoot.fsPath, { recursive: true });
  await writeFile(originalUri.fsPath, '', { encoding: 'utf8', mode: 0o600 });
  await writeFile(proposedUri.fsPath, content, { encoding: 'utf8', mode: 0o600 });
  await vscode.commands.executeCommand('vscode.diff', originalUri, proposedUri, `New file: ${safePath}`, { preview: false });

  const choice = await vscode.window.showInformationMessage(
    `Review the new file in the diff editor. Create ${safePath} in the open workspace?`,
    { modal: true }, 'Create File', 'Cancel',
  );
  if (choice === 'Cancel') return 'rejected';
  if (choice !== 'Create File') return 'cancelled';

  try {
    await vscode.workspace.fs.stat(targetUri);
    throw new Error(`${safePath} was created while the proposal was open. Nothing was overwritten.`);
  } catch (error) {
    if (!isNotFound(error)) throw error;
  }
  await ensureInsideWorkspace(workspace.uri.fsPath, targetUri.fsPath, false);
  const workspaceEdit = new vscode.WorkspaceEdit();
  workspaceEdit.createFile(targetUri, { overwrite: false, ignoreIfExists: false });
  workspaceEdit.insert(targetUri, new vscode.Position(0, 0), content);
  if (!await vscode.workspace.applyEdit(workspaceEdit)) throw new Error('VS Code could not create the approved file.');
  return 'applied';
}

/** Create a generated source file in the workspace without replacing existing files. */
export async function writeGeneratedFile(relativePath: string, content: string): Promise<string> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) throw new Error('Open a workspace before saving generated code.');
  if (workspace.uri.scheme !== 'file') throw new Error('Saving generated code currently requires a local file workspace.');
  if (!content.trim()) throw new Error('There is no code to save.');
  if (content.length > 1_000_000) throw new Error('Generated code is too large to save automatically (limit: 1 MB).');

  const safePath = validateRelativePath(relativePath, workspace.uri.fsPath);
  const parts = safePath.split('/');
  const fileName = parts.pop()!;
  const parent = parts.length ? vscode.Uri.joinPath(workspace.uri, ...parts) : workspace.uri;
  const parentInfo = await vscode.workspace.fs.stat(parent);
  if (parentInfo.type !== vscode.FileType.Directory) throw new Error('The destination folder is not a directory.');

  const extensionAt = fileName.lastIndexOf('.');
  const stem = extensionAt > 0 ? fileName.slice(0, extensionAt) : fileName;
  const extension = extensionAt > 0 ? fileName.slice(extensionAt) : '';
  for (let index = 1; index <= 100; index += 1) {
    const candidateName = index === 1 ? fileName : `${stem}-${index}${extension}`;
    const candidatePath = [...parts, candidateName].join('/');
    const target = vscode.Uri.joinPath(workspace.uri, ...candidatePath.split('/'));
    try {
      await vscode.workspace.fs.stat(target);
      continue;
    } catch (error) {
      if (!isNotFound(error)) throw error;
    }
    await ensureInsideWorkspace(workspace.uri.fsPath, target.fsPath, false);
    const edit = new vscode.WorkspaceEdit();
    edit.createFile(target, { overwrite: false, ignoreIfExists: false });
    edit.insert(target, new vscode.Position(0, 0), content.endsWith('\n') ? content : `${content}\n`);
    if (!await vscode.workspace.applyEdit(edit)) throw new Error(`VS Code could not create ${candidatePath}.`);
    return candidatePath;
  }
  throw new Error(`Could not find an unused file name for ${safePath}.`);
}

export async function reviewEdit(proposal: EditProposal, globalStorageUri: vscode.Uri, autoApply = false): Promise<'applied' | 'rejected' | 'cancelled'> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) throw new Error('Open a workspace before reviewing code edits.');
  const staged = await Promise.all(proposal.changes.map((change) => stageChange(change, workspace.uri, globalStorageUri)));
  if (!autoApply) {
    for (const edit of staged) {
      await vscode.commands.executeCommand('vscode.diff', edit.originalUri, edit.proposedUri, `Proposed: ${vscode.workspace.asRelativePath(edit.uri, false)}`, { preview: false });
    }
    const choice = await vscode.window.showInformationMessage(
      `Review ${staged.length} proposed file change${staged.length === 1 ? '' : 's'} in the diff editor.`,
      { modal: true }, 'Apply All', 'Reject',
    );
    if (choice === 'Reject') return 'rejected';
    if (choice !== 'Apply All') return 'cancelled';
  }

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

async function stageChange(change: ProposedChange, rootUri: vscode.Uri, storageUri: vscode.Uri): Promise<StagedEdit & { proposedUri: vscode.Uri; originalUri: vscode.Uri }> {
  if (rootUri.scheme !== 'file') throw new Error('Edit previews currently require a local file workspace.');
  const relativePath = validateRelativePath(change.path, rootUri.fsPath);
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
  const proposed = change.content !== undefined ? change.content : applyUnifiedDiff(original, change.diff, relativePath);
  const key = createHash('sha256').update(relativePath).digest('hex');
  const proposedUri = vscode.Uri.joinPath(storageUri, 'review', `${key}.proposed`);
  const originalUri = vscode.Uri.joinPath(storageUri, 'review', `${key}.original`);
  const proposedFsPath = resolve(proposedUri.fsPath);
  await mkdir(dirname(proposedFsPath), { recursive: true });
  await writeFile(proposedFsPath, proposed, { encoding: 'utf8', mode: 0o600 });
  await writeFile(resolve(originalUri.fsPath), original, { encoding: 'utf8', mode: 0o600 });
  return { uri, original, proposed, exists, deletesFile: change.content === undefined && isDeletePatch(change.diff), proposedUri, originalUri };
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
