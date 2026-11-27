import esbuild from 'esbuild';
import { watch } from 'node:fs';
import { mkdir } from 'node:fs/promises';

const watching = process.argv.includes('--watch');
await mkdir('dist', { recursive: true });

const builds = [
  {
    entryPoints: ['src/extension.ts'],
    bundle: true,
    platform: 'node',
    target: 'node20',
    format: 'cjs',
    external: ['vscode'],
    outfile: 'dist/extension.js',
    sourcemap: !watching,
  },
  {
    entryPoints: ['media/chat.js'],
    bundle: true,
    platform: 'browser',
    target: ['es2022'],
    format: 'iife',
    outfile: 'dist/chat.js',
    sourcemap: !watching,
  },
];

if (watching) {
  const contexts = await Promise.all(builds.map((options) => esbuild.context({ ...options, logLevel: 'info' })));
  await Promise.all(contexts.map((context) => context.watch()));
  console.log('Watching extension and webview bundles.');
} else {
  await Promise.all(builds.map((options) => esbuild.build({ ...options, logLevel: 'info' })));
}
