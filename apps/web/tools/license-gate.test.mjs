// Independently authored filesystem fixtures; no packages are installed or executed.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const tool = fileURLToPath(new URL('./license-gate.mjs', import.meta.url));
const sentinel = 'OUTSIDE_EVIDENCE_MUST_NOT_BE_READ';

function fixture(t, location = 'node_modules/example', name = 'example') {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'oi-rights-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const root = path.join(temp, 'project');
  const base = path.join(root, location);
  fs.mkdirSync(base, { recursive: true });
  const manifest = { name, version: '1.0.0', license: 'MIT' };
  const record = { version: '1.0.0', license: 'MIT', integrity: 'sha512-fixture', resolved: 'https://registry.npmjs.org/example/-/example-1.0.0.tgz' };
  const lock = { lockfileVersion: 3, packages: { '': {}, [location]: record } };
  const writeManifest = () => fs.writeFileSync(path.join(base, 'package.json'), JSON.stringify(manifest));
  writeManifest();
  fs.writeFileSync(path.join(base, 'LICENSE'), 'Independently authored fictional notice.\n');
  const run = () => {
    fs.writeFileSync(path.join(root, 'package-lock.json'), JSON.stringify(lock));
    const result = spawnSync(process.execPath, [tool], { cwd: root, encoding: 'utf8', timeout: 10000 });
    assert.equal(result.error, undefined);
    const raw = fs.readFileSync(path.join(root, '.licenses/inventory.json'), 'utf8');
    return { ...result, raw, inventory: JSON.parse(raw) };
  };
  return { root, base, temp, manifest, record, lock, writeManifest, run };
}

function blocked(result, reason) {
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.ok(result.inventory.errors.some(error => reason.test(error)), JSON.stringify(result.inventory.errors));
  assert.equal(result.inventory.commercial_release_cleared, false);
  assert.ok(!result.raw.includes(sentinel), 'outside bytes were included in the evidence artifact');
}

for (const [label, location, name, alias] of [
  ['ordinary', 'node_modules/example', 'example'],
  ['scoped', 'node_modules/@fictional/example', '@fictional/example'],
  ['nested', 'node_modules/parent/node_modules/example', 'example'],
  ['npm alias', 'node_modules/example', '@fictional/actual', true],
]) {
  test(`accepts ${label} package identity with actual notice evidence`, t => {
    const f = fixture(t, location, name);
    if (alias) f.record.name = name;
    const result = f.run();
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.deepEqual(result.inventory.errors, []);
    assert.equal(result.inventory.records[0].name, name);
    assert.equal(result.inventory.records[0].notice_files[0].text, 'Independently authored fictional notice.\n');
    assert.equal(result.inventory.commercial_release_cleared, false);
  });
}

test('rejects a different installed package with the same version and license', t => {
  const f = fixture(t);
  f.manifest.name = 'substituted-package';
  f.writeManifest();
  blocked(f.run(), /identity|name/i);
});

test('rejects a license mismatch even when both declarations are allowed', t => {
  const f = fixture(t);
  f.manifest.license = 'ISC';
  f.writeManifest();
  blocked(f.run(), /license.*mismatch/i);
});

test('rejects path normalization that substitutes another package', t => {
  const f = fixture(t);
  delete f.lock.packages['node_modules/example'];
  f.lock.packages['node_modules/unused/../example'] = f.record;
  blocked(f.run(), /lock path/i);
});

test('rejects a linked package directory before inspecting its evidence', t => {
  const f = fixture(t);
  const external = path.join(f.temp, 'external');
  fs.renameSync(f.base, external);
  fs.writeFileSync(path.join(external, 'LICENSE'), sentinel);
  fs.symlinkSync(external, f.base, 'dir');
  blocked(f.run(), /link|directory/i);
});

test('rejects a linked scope directory before inspecting its evidence', t => {
  const f = fixture(t, 'node_modules/@fictional/example', '@fictional/example');
  const scope = path.dirname(f.base);
  const external = path.join(f.temp, 'external');
  fs.renameSync(scope, external);
  fs.writeFileSync(path.join(external, 'example/LICENSE'), sentinel);
  fs.symlinkSync(external, scope, 'dir');
  blocked(f.run(), /link|directory/i);
});

for (const filename of ['package.json', 'LICENSE']) {
  test(`rejects linked ${filename} without copying outside content`, t => {
    const f = fixture(t);
    const external = path.join(f.temp, 'external');
    fs.writeFileSync(external, filename === 'package.json' ? JSON.stringify({ ...f.manifest, description: sentinel }) : sentinel);
    fs.unlinkSync(path.join(f.base, filename));
    fs.symlinkSync(external, path.join(f.base, filename));
    blocked(f.run(), /link|regular file/i);
  });
}

test('retains absent optional packages as explicitly uninspected', t => {
  const f = fixture(t);
  f.record.optional = true;
  fs.rmSync(f.base, { recursive: true });
  const result = f.run();
  assert.equal(result.status, 0);
  assert.equal(result.inventory.records[0].installed, false);
  assert.equal(result.inventory.records[0].scope, 'optional-platform-not-inspected');
});

test('an installed optional package cannot hide a missing manifest', t => {
  const f = fixture(t);
  f.record.optional = true;
  fs.unlinkSync(path.join(f.base, 'package.json'));
  blocked(f.run(), /manifest|regular file|package.json/i);
});
