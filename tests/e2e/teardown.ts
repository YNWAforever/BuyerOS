import { spawnSync } from 'node:child_process';
import { readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';

export default function cleanupDisposableE2eDatabase() {
  const marker = join(process.cwd(), 'test-results', 'e2e-db-container.txt');
  let name: string;
  try {
    name = readFileSync(marker, 'utf8').trim();
  } catch {
    return;
  }

  if (!/^buyeros-test-[0-9a-f]{8}$/.test(name)) {
    throw new Error('Refusing to clean an unrecognized E2E database container');
  }
  const result = spawnSync('docker', ['rm', '-f', name], { encoding: 'utf8' });
  if (result.status !== 0 && !result.stderr.includes('No such container')) {
    throw new Error(`Could not clean disposable E2E database: ${result.stderr}`);
  }
  rmSync(marker);
}
