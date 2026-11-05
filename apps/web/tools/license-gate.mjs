// Review evidence, not legal advice or whole-product clearance. No package execution.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root = process.cwd();
const lockBytes = fs.readFileSync('package-lock.json');
const lock = JSON.parse(lockBytes);
const allowed = new Set(['MIT', 'ISC', 'BSD-2-Clause', 'BSD-3-Clause', 'Apache-2.0', '0BSD', 'CC0-1.0', '(MIT OR Apache-2.0)', '(Apache-2.0 OR MIT)']);
const packageName = /^(?:@[A-Za-z0-9_][A-Za-z0-9._-]*\/)?[A-Za-z0-9_][A-Za-z0-9._-]*$/;
const noticeName = /^(license|licence|copying|notice)(\.|$)|third.?party.*(?:notice|licen)/i;
const rows = [], errors = [];

// Registry-only installs have real directories; npm aliases are names, not links.
// Inspect every ancestor, including scopes and nested node_modules directories.
function installedDirectory(location) {
  let current = root;
  for (const component of location.split('/')) {
    current = path.join(current, component);
    let stat;
    try { stat = fs.lstatSync(current); }
    catch (error) {
      if (error.code === 'ENOENT') return false;
      throw new Error('cannot inspect package directory');
    }
    if (stat.isSymbolicLink() || !stat.isDirectory()) {
      throw new Error('package directory must be a directory without symbolic links');
    }
  }
  return true;
}

function readEvidence(filename) {
  let descriptor;
  try {
    if (!fs.lstatSync(filename).isFile()) throw new Error('not regular');
    descriptor = fs.openSync(filename, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    if (!fs.fstatSync(descriptor).isFile()) throw new Error('not regular');
    return fs.readFileSync(descriptor);
  } catch {
    throw new Error(path.basename(filename) + ': evidence must be a readable regular file without symbolic links');
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

if (lock.lockfileVersion !== 3) errors.push('lockfileVersion must be 3');
for (const [location, record] of Object.entries(lock.packages)) {
  if (!location) continue;
  const parts = location.startsWith('node_modules/')
    ? location.slice('node_modules/'.length).split('/node_modules/') : [];
  if (!parts.length || parts.some(part => !packageName.test(part))) {
    errors.push(location + ': unsafe or unexpected lock path');
    continue;
  }
  if (!record.integrity?.startsWith('sha512-')) errors.push(location + ': missing SHA512 integrity');
  if (typeof record.resolved !== 'string' || !record.resolved.startsWith('https://registry.npmjs.org/')) errors.push(location + ': unapproved registry');
  if (!allowed.has(record.license)) errors.push(location + ': unreviewed lock license ' + record.license);

  try {
    const expectedName = record.name ?? parts.at(-1);
    if (typeof expectedName !== 'string' || !packageName.test(expectedName)) throw new Error('invalid locked package identity');
    if (!installedDirectory(location)) {
      if (record.optional) {
        rows.push({ location, version: record.version, license: record.license, installed: false, scope: 'optional-platform-not-inspected', integrity: record.integrity });
        continue;
      }
      throw new Error('required package missing');
    }
    const base = path.join(root, location);
    let p;
    const manifestBytes = readEvidence(path.join(base, 'package.json'));
    try { p = JSON.parse(manifestBytes); }
    catch { throw new Error('package.json: invalid manifest'); }
    if (!p || p.name !== expectedName) throw new Error('installed package identity mismatch');
    if (p.version !== record.version) throw new Error('installed version mismatch');
    if (p.license !== record.license) throw new Error('installed license declaration mismatch');
    if (!allowed.has(p.license)) throw new Error('unreviewed installed license');

    const notices = fs.readdirSync(base).filter(name => noticeName.test(name)).map(name => {
      const bytes = readEvidence(path.join(base, name));
      const text = bytes.toString('utf8');
      if (/GNU (?:AFFERO |LESSER )?GENERAL PUBLIC LICENSE|CC-BY-NC|Commons Clause|Elastic License/i.test(text)) {
        errors.push(location + ': manual restrictive-term review required');
      }
      return { name, sha256: crypto.createHash('sha256').update(bytes).digest('hex'), text };
    });
    if (!notices.length) errors.push(location + ': actual LICENSE/NOTICE file missing');
    rows.push({ location, name: p.name, version: p.version, license: p.license, integrity: record.integrity, resolved: record.resolved, installed: true, notice_files: notices });
  } catch (error) {
    errors.push(location + ': ' + error.message);
  }
}

fs.mkdirSync('.licenses', { recursive: true });
fs.writeFileSync('.licenses/inventory.json', JSON.stringify({
  schema: 'oi.frontend-dependency-evidence/1',
  scope: 'local-fictional-development-only',
  commercial_release_cleared: false,
  native_object_linkage_reviewed: false,
  lock_sha256: crypto.createHash('sha256').update(lockBytes).digest('hex'),
  records: rows, errors,
}, null, 2) + '\n');
console.log(JSON.stringify({
  installed: rows.filter(r => r.installed).length,
  optional_uninspected: rows.filter(r => !r.installed).length,
  errors,
}, null, 2));
if (errors.length) process.exitCode = 1;

