import { isAbsolute, normalize, relative, resolve, sep } from 'node:path';
import { parsePatch, applyPatch } from 'diff';

export interface ProposedChange {
  path: string;
  diff: string;
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
  const pattern = /```(achat-edit|achat-command)\s*\n([\s\S]*?)```/g;
  for (const match of text.matchAll(pattern)) {
    try {
      const value: unknown = JSON.parse(match[2]);
      if (match[1] === 'achat-edit') {
        actions.push({ kind: 'edit', payload: validateEdit(value, workspaceRoot), raw: match[0] });
      } else {
        actions.push({ kind: 'command', payload: validateCommand(value, workspaceRoot), raw: match[0] });
      }
    } catch {
      // Invalid proposals remain ordinary inert response text.
    }
  }
  return actions;
}

function validateEdit(value: unknown, workspaceRoot: string): EditProposal {
  if (!isObject(value) || !Array.isArray(value.changes) || value.changes.length === 0 || value.changes.length > 20) {
    throw new Error('Invalid edit proposal.');
  }
  const changes = value.changes.map((item): ProposedChange => {
    if (!isObject(item) || typeof item.path !== 'string' || typeof item.diff !== 'string' || !item.diff.trim()) {
      throw new Error('Invalid edit change.');
    }
    const path = validateRelativePath(item.path, workspaceRoot);
    if (item.diff.length > 200_000) throw new Error('Patch exceeds size limit.');
    const patches = parsePatch(item.diff);
    if (patches.length !== 1) throw new Error('Each change must contain exactly one unified diff.');
    return { path, diff: item.diff };
  });
  if (new Set(changes.map((change) => change.path)).size !== changes.length) {
    throw new Error('An edit proposal cannot change the same file twice.');
  }
  return { changes };
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
