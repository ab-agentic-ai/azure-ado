import * as vscode from 'vscode';
import { posix as path } from 'node:path';
import { ChatContextItem } from './types';

export const MAX_FILE_CHARS = 20_000;
export const MAX_TOTAL_CONTEXT_CHARS = 80_000;
const MAX_FILE_BYTES = 1_000_000;

function workspaceRelativePath(uri: vscode.Uri): string {
  const folder = vscode.workspace.getWorkspaceFolder(uri);
  if (!folder || uri.scheme !== folder.uri.scheme || uri.authority !== folder.uri.authority) {
    throw new Error('Choose a file inside the open VS Code workspace.');
  }
  const relative = path.relative(folder.uri.path, uri.path);
  if (!relative || relative === '.' || relative === '..' || relative.startsWith('../') || path.isAbsolute(relative)) {
    if (relative === '.' || relative === '') return folder.name;
    throw new Error('Choose a file inside the open VS Code workspace.');
  }
  return vscode.workspace.workspaceFolders?.length === 1 ? relative : `${folder.name}/${relative}`;
}

export function collectSelection(editor: vscode.TextEditor): ChatContextItem | undefined {
  if (editor.selection.isEmpty) {
    return undefined;
  }
  const content = editor.document.getText(editor.selection);
  if (!content.trim()) {
    return undefined;
  }
  return limitItem({
    id: `selection:${workspaceRelativePath(editor.document.uri)}`,
    path: workspaceRelativePath(editor.document.uri),
    kind: 'selection',
    content,
  }, []);
}

export async function collectFile(uri: vscode.Uri, maxChars = MAX_FILE_CHARS): Promise<ChatContextItem> {
  const relativePath = workspaceRelativePath(uri);
  const openDocument = vscode.workspace.textDocuments.find((document) => document.uri.toString() === uri.toString());
  let content: string;
  if (openDocument) {
    content = openDocument.getText();
  } else {
    const stat = await vscode.workspace.fs.stat(uri);
    if (stat.size > MAX_FILE_BYTES) {
      throw new Error(`${relativePath} is larger than 1 MB. Choose a smaller source file or select only the relevant code.`);
    }
    const bytes = await vscode.workspace.fs.readFile(uri);
    content = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
  }
  if (content.length > MAX_FILE_BYTES) {
    throw new Error(`${relativePath} is larger than 1 MB. Choose a smaller source file or select only the relevant code.`);
  }
  if (content.includes('\u0000')) {
    throw new Error('Binary files cannot be attached as text.');
  }
  return limitItem({
    id: `file:${relativePath}`,
    path: relativePath,
    kind: 'file',
    content,
  }, [], maxChars);
}

export function limitItem(item: ChatContextItem, current: ChatContextItem[], maxItemChars = item.kind === 'workspace' ? MAX_TOTAL_CONTEXT_CHARS : MAX_FILE_CHARS): ChatContextItem {
  const remainingItems = current.filter((existing) => existing.id !== item.id);
  const remaining = MAX_TOTAL_CONTEXT_CHARS - remainingItems.reduce((sum, existing) => sum + existing.content.length, 0);
  if (remaining <= 0) {
    throw new Error('The 80,000 character context limit is full. Remove an attachment before adding another.');
  }
  const budget = Math.min(maxItemChars, remaining);
  const content = item.content.slice(0, budget);
  return {
    ...item,
    content,
    truncated: Boolean(item.truncated || content.length < item.content.length),
  };
}
