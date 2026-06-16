import { copyFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../docs/USER_MANUAL.md');
const destDir = resolve(here, '../src/help');
const dest = resolve(destDir, 'manual.generated.md');

if (!existsSync(src)) {
  console.error(`[sync-manual] source not found: ${src}`);
  process.exit(1);
}
mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`[sync-manual] copied ${src} -> ${dest}`);
