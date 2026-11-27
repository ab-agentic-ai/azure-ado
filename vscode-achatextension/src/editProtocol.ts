import { existsSync } from 'node:fs';
import { isAbsolute, normalize, relative, resolve, sep } from 'node:path';
import { parsePatch, applyPatch } from 'diff';

export interface ProposedChange {
  path: string;
  diff: string;
  content?: string;
}

export interface EditProposal {
  changes: ProposedChange[];
}

export interface CommandProposal {
  command: string;
  cwd: string;
}

export interface ParsedAction {
  kind: 'edit' | 'command';
  payload: EditProposal | CommandProposal;
  raw: string;
}

export function parseActions(text: string, workspaceRoot: string): ParsedAction[] {
  const actions: ParsedAction[] = [];
  // Small local models sometimes follow the JSON shape but label the block
  // `json` instead of the requested `achat-edit` language. Accept that shape
  // only when it validates as a complete edit proposal.
  const pattern = /```(achat-edit|achat-command|json)\s*\n([\s\S]*?)```/gi;
  for (const match of text.matchAll(pattern)) {
    try {
      const value: unknown = JSON.parse(match[2]);
      const label = match[1].toLowerCase();
      if (label === 'achat-edit' || label === 'json' && isEditProposalShape(value)) {
        actions.push({ kind: 'edit', payload: validateEdit(value, workspaceRoot), raw: match[0] });
      } else if (label === 'achat-command') {
        actions.push({ kind: 'command', payload: validateCommand(value, workspaceRoot), raw: match[0] });
      }
    } catch {
      // Invalid proposals remain ordinary inert response text.
    }
  }
  return actions;
}

function isEditProposalShape(value: unknown): boolean {
  if (!isObject(value) || !Array.isArray(value.changes) || value.changes.length === 0) return false;
  return value.changes.every((item) => isObject(item) && typeof item.path === 'string' && (typeof item.diff === 'string' || typeof item.content === 'string'));
}

function validateEdit(value: unknown, workspaceRoot: string): EditProposal {
  if (!isObject(value) || !Array.isArray(value.changes) || value.changes.length === 0 || value.changes.length > 20) {
    throw new Error('Invalid edit proposal.');
  }
  const changes = value.changes.map((item): ProposedChange => {
    if (!isObject(item) || typeof item.path !== 'string') {
      throw new Error('Invalid edit change.');
    }
    const path = validateRelativePath(item.path, workspaceRoot);
    const targetExists = existsSync(resolve(workspaceRoot, path));
    if (typeof item.content === 'string') {
      if (!item.content.trim() || item.content.length > 1_000_000 || item.content.includes('\0')) throw new Error('New file content is empty, binary, or too large.');
      return { path, content: item.content, diff: '' };
    }
    if (typeof item.diff !== 'string' || !item.diff.trim()) throw new Error('Invalid edit change.');
    if (item.diff.length > 200_000) throw new Error('Patch exceeds size limit.');
    const normalizedDiff = normalizeUnifiedDiff(item.diff);
    if (!targetExists) {
      const content = extractNewFileContent(normalizedDiff);
      if (content === undefined || !content.trim() || content.length > 1_000_000 || content.includes('\0')) {
        throw new Error(`Could not safely extract the contents for new file ${path}.`);
      }
      return { path, content, diff: '' };
    }
    const patches = parsePatch(normalizedDiff);
    if (patches.length !== 1) throw new Error('Each change must contain exactly one unified diff.');
    return { path, diff: normalizedDiff };
  });
  if (new Set(changes.map((change) => change.path)).size !== changes.length) {
    throw new Error('An edit proposal cannot change the same file twice.');
  }
  return { changes };
}

function normalizeUnifiedDiff(patchText: string): string {
  return patchText.replace(/\r\n/g, '\n').replace(/^@{3,}(\s)/gm, '@@$1');
}

function extractNewFileContent(patchText: string): string | undefined {
  const lines = patchText.split('\n');
  const hunkIndex = lines.findIndex((line) => /^@{2,}\s/.test(line));
  if (hunkIndex < 0) {
    const newFileHeader = lines.findIndex((line) => line.startsWith('+++ '));
    return newFileHeader < 0 ? undefined : lines.slice(newFileHeader + 1).join('\n');
  }
  const addedOrContext: string[] = [];
  const unmarked: string[] = [];
  let hasUnifiedMarkers = false;
  for (const line of lines.slice(hunkIndex + 1)) {
    if (/^@{2,}\s/.test(line)) break;
    if (line.startsWith('\\')) continue;
    if (line.startsWith('+') && !line.startsWith('+++')) {
      hasUnifiedMarkers = true;
      addedOrContext.push(line.slice(1));
    } else if (line.startsWith(' ')) {
      hasUnifiedMarkers = true;
      addedOrContext.push(line.slice(1));
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      hasUnifiedMarkers = true;
    } else {
      unmarked.push(line);
    }
  }
  const contentLines = hasUnifiedMarkers ? addedOrContext : unmarked;
  if (!contentLines.length) return undefined;
  return contentLines.join('\n') + (lines.at(-1) === '' ? '\n' : '');
}

function validateCommand(value: unknown, workspaceRoot: string): CommandProposal {
  if (!isObject(value) || typeof value.command !== 'string' || !value.command.trim() || value.command.length > 2000) {
    throw new Error('Invalid command proposal.');
  }
  const cwd = typeof value.cwd === 'string' ? value.cwd : '.';
  validateRelativePath(cwd, workspaceRoot, true);
  return { command: value.command.trim(), cwd: normalize(cwd || '.') };
}

export function validateRelativePath(path: string, workspaceRoot: string, allowDot = false): string {
  if (!path || path.includes('\0') || isAbsolute(path) || /^[a-zA-Z]:/.test(path) || path.startsWith('\\')) {
    throw new Error('Proposal paths must be relative to the open workspace.');
  }
  const normalized = normalize(path.replace(/[\\/]+/g, sep));
  if (normalized === '.' && allowDot) return '.';
  const absolute = resolve(workspaceRoot, normalized);
  const fromRoot = relative(resolve(workspaceRoot), absolute);
  if (!fromRoot || fromRoot === '.' && !allowDot || fromRoot === '..' || fromRoot.startsWith(`..${sep}`) || isAbsolute(fromRoot)) {
    throw new Error('Proposal path must point inside the open workspace.');
  }
  return fromRoot.split(sep).join('/');
}

export function applyUnifiedDiff(original: string, patchText: string, path: string): string {
  const patch = parsePatch(patchText);
  if (patch.length !== 1) throw new Error('Each file change must contain one unified diff.');
  const target = patch[0].newFileName === '/dev/null' ? patch[0].oldFileName : patch[0].newFileName || patch[0].oldFileName;
  if (target && target !== '/dev/null') {
    const cleaned = target.replace(/^[ab]\//, '');
    if (cleaned !== path && cleaned !== path.replaceAll('\\', '/')) {
      throw new Error(`Patch header targets ${cleaned}, but the proposal names ${path}.`);
    }
  }
  const result = applyPatch(original, patch[0]);
  if (result === false) throw new Error(`Patch for ${path} does not apply cleanly to the current file.`);
  return result;
}

export function isDeletePatch(patchText: string): boolean {
  const patches = parsePatch(patchText);
  return patches.length === 1 && patches[0].newFileName === '/dev/null';
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
