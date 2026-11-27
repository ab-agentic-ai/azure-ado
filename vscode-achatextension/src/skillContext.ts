import { open, realpath } from 'node:fs/promises';
import { isAbsolute, relative, sep } from 'node:path';
import * as vscode from 'vscode';

export interface WorkspaceSkill {
  name: string;
  description: string;
  relativePath: string;
  uri: vscode.Uri;
  instructions: string;
}

export const MAX_SKILL_FILES = 100;
export const MAX_SKILL_FILE_BYTES = 128 * 1024;
export const MAX_SKILL_INSTRUCTIONS_CHARS = 12_000;
export const MAX_SKILL_CONTEXT_CHARS = 24_000;
const MAX_FRONT_MATTER_BYTES = 8 * 1024;

const SKILL_EXCLUDES = '**/{.git,node_modules,.venv,venv,dist,build,out,coverage,.next,.cache,vendor,target,.secrets,secrets,.ssh,.aws,.azure,.claude,.cursor,.vscode,.idea,.superpowers,__pycache__}/**';
const STOP_WORDS = new Set([
  'a', 'about', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'can', 'do', 'for', 'from', 'how', 'i', 'in', 'into',
  'is', 'it', 'me', 'my', 'of', 'on', 'or', 'our', 'please', 'should', 'that', 'the', 'their', 'this', 'to', 'use',
  'when', 'which', 'with', 'you', 'your', 'user', 'users', 'skill', 'skills', 'workspace', 'project',
]);

interface SkillMetadata {
  name: string;
  description: string;
  bodyOffset: number;
}

/** Index workspace-local skill metadata without loading the instruction bodies. */
export async function discoverWorkspaceSkills(): Promise<WorkspaceSkill[]> {
  if (!vscode.workspace.workspaceFolders?.length) return [];
  const uris = await vscode.workspace.findFiles('**/SKILL.md', SKILL_EXCLUDES, MAX_SKILL_FILES);
  const skills: WorkspaceSkill[] = [];
  for (const uri of uris) {
    try {
      const folder = vscode.workspace.getWorkspaceFolder(uri);
      if (!folder || folder.uri.scheme !== 'file' || uri.scheme !== 'file') continue;
      const stat = await vscode.workspace.fs.stat(uri);
      if (stat.type !== vscode.FileType.File || stat.size > MAX_SKILL_FILE_BYTES) continue;
      await assertWithinWorkspace(uri, folder.uri);
      const frontMatter = await readFrontMatter(uri);
      if (!frontMatter) continue;
      skills.push({
        name: frontMatter.name,
        description: frontMatter.description,
        relativePath: workspaceSkillPath(uri, folder),
        uri,
        instructions: '',
      });
    } catch {
      // A malformed, unreadable, or outside-root skill must not block chat.
    }
  }
  return skills.sort((left, right) => left.name.localeCompare(right.name) || left.relativePath.localeCompare(right.relativePath));
}

/** Load full instructions only for a skill already selected for this request. */
export async function loadWorkspaceSkill(skill: WorkspaceSkill): Promise<WorkspaceSkill | undefined> {
  try {
    const folder = vscode.workspace.getWorkspaceFolder(skill.uri);
    if (!folder || folder.uri.scheme !== 'file' || skill.uri.scheme !== 'file') return undefined;
    const stat = await vscode.workspace.fs.stat(skill.uri);
    if (stat.type !== vscode.FileType.File || stat.size > MAX_SKILL_FILE_BYTES) return undefined;
    await assertWithinWorkspace(skill.uri, folder.uri);
    const content = new TextDecoder('utf-8', { fatal: false }).decode(await vscode.workspace.fs.readFile(skill.uri));
    const metadata = parseSkillMetadata(content);
    if (!metadata) return undefined;
    return { ...skill, name: metadata.name, description: metadata.description, instructions: content.slice(metadata.bodyOffset).trim().slice(0, MAX_SKILL_INSTRUCTIONS_CHARS) };
  } catch {
    return undefined;
  }
}

/** Rank skills by meaningful term overlap in their front-matter name and description. */
export function matchWorkspaceSkills(prompt: string, skills: WorkspaceSkill[], limit = 3): WorkspaceSkill[] {
  const promptTerms = terms(prompt);
  if (!promptTerms.size || limit < 1) return [];
  return skills
    .map((skill) => {
      const nameTerms = terms(skill.name);
      const descriptionTerms = terms(skill.description);
      let score = 0;
      for (const term of promptTerms) {
        if (nameTerms.has(term)) score += 3;
        if (descriptionTerms.has(term)) score += 1;
      }
      return { skill, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.skill.name.localeCompare(right.skill.name) || left.skill.relativePath.localeCompare(right.skill.relativePath))
    .slice(0, Math.min(limit, 3))
    .map((item) => item.skill);
}

/** Format selected skill bodies while enforcing the aggregate instruction budget. */
export function formatSkillInstructions(skills: WorkspaceSkill[], maxChars = MAX_SKILL_CONTEXT_CHARS): string {
  let remaining = Math.min(MAX_SKILL_CONTEXT_CHARS, Math.max(0, maxChars));
  const sections: string[] = [];
  for (const skill of skills.slice(0, 3)) {
    if (!skill.instructions || remaining <= 0) continue;
    const heading = `\n--- Skill: ${skill.name} (${skill.relativePath}) ---\n`;
    const instructionBudget = Math.min(MAX_SKILL_INSTRUCTIONS_CHARS, remaining - heading.length - 1);
    if (instructionBudget <= 0) break;
    const section = `${heading}${skill.instructions.slice(0, instructionBudget)}\n`;
    sections.push(section);
    remaining -= section.length;
  }
  return sections.join('');
}

async function readFrontMatter(uri: vscode.Uri): Promise<SkillMetadata | undefined> {
  const handle = await open(uri.fsPath, 'r');
  try {
    const buffer = Buffer.alloc(MAX_FRONT_MATTER_BYTES);
    const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
    return parseSkillMetadata(buffer.subarray(0, bytesRead).toString('utf8'));
  } finally {
    await handle.close();
  }
}

function parseSkillMetadata(content: string): SkillMetadata | undefined {
  const boundary = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(content);
  if (!boundary || boundary[0].length > MAX_FRONT_MATTER_BYTES) return undefined;
  const lines = boundary[1].split(/\r?\n/);
  let name = '';
  let description = '';
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const field = /^(name|description)\s*:\s*(.*)$/.exec(line);
    if (!field) continue;
    if (field[1] === 'name') {
      name = parseScalar(field[2]);
      continue;
    }
    const marker = field[2].trim();
    if (/^[>|][+-]?$/.test(marker)) {
      const block: string[] = [];
      while (index + 1 < lines.length && (!lines[index + 1].trim() || /^\s+/.test(lines[index + 1]))) {
        index += 1;
        block.push(lines[index].trim());
      }
      description = marker.startsWith('>') ? block.join(' ').trim() : block.join('\n').trim();
    } else {
      description = parseScalar(marker);
    }
  }
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(name) || description.length < 1 || description.length > 2_000) return undefined;
  return { name, description, bodyOffset: boundary[0].length };
}

function parseScalar(value: string): string {
  const scalar = value.trim();
  if (scalar.startsWith('"') && scalar.endsWith('"')) {
    try { return JSON.parse(scalar) as string; } catch { return ''; }
  }
  if (scalar.startsWith("'") && scalar.endsWith("'")) return scalar.slice(1, -1).replace(/''/g, "'");
  return scalar.replace(/\s+#.*$/, '').trim();
}

function terms(value: string): Set<string> {
  return new Set(value.toLowerCase().match(/[a-z0-9]+/g)?.filter((word) => word.length > 2 && !STOP_WORDS.has(word)) ?? []);
}

async function assertWithinWorkspace(file: vscode.Uri, root: vscode.Uri): Promise<void> {
  const rootPath = await realpath(root.fsPath);
  const filePath = await realpath(file.fsPath);
  const relativePath = relative(rootPath, filePath);
  if (!relativePath || relativePath === '..' || relativePath.startsWith(`..${sep}`) || isAbsolute(relativePath)) {
    throw new Error('Skill paths must remain inside the real workspace folder.');
  }
}

function workspaceSkillPath(file: vscode.Uri, folder: vscode.WorkspaceFolder): string {
  const filePath = relative(folder.uri.fsPath, file.fsPath).split(sep).join('/');
  const folders = vscode.workspace.workspaceFolders ?? [];
  if (folders.length < 2) return filePath;
  const duplicateName = folders.filter((candidate) => candidate.name === folder.name).length > 1;
  const label = duplicateName ? `${folder.name}-${folders.indexOf(folder) + 1}` : folder.name;
  return `${label}/${filePath}`;
}
