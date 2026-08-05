import { spawnSync } from 'node:child_process'
import path from 'node:path'

export default function globalTeardown(): void {
  const python = process.platform === 'win32' ? 'python' : 'python3'
  const script = path.resolve('apps', 'api', 'scripts', 'sanitize-playwright-artifacts.py')
  const result = spawnSync(
    python,
    [
      script,
      '--path',
      path.resolve('test-results'),
      '--path',
      path.resolve('playwright-report'),
      '--report',
      path.resolve('test-results', 'artifact-secret-scan.json'),
    ],
    { env: process.env, encoding: 'utf8' },
  )
  if (result.stdout) process.stdout.write(result.stdout)
  if (result.stderr) process.stderr.write(result.stderr)
  if (result.status !== 0) throw new Error('Playwright artifact secret scan failed.')
}
