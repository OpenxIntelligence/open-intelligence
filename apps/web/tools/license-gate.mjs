// Review evidence, not legal advice or whole-product clearance. No package execution.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root = process.cwd();
const output = path.join(root, '.licenses');
fs.mkdirSync(output, { recursive: true });
if (!fs.lstatSync(output).isDirectory()) throw new Error('Expected a regular evidence directory');
const bomPath = path.join(output, 'web.cdx.json');
// Invalidate prior success even if reading or parsing this lock fails.
fs.rmSync(bomPath, { force: true });

function writeJson(target, data) {
  const temporary = fs.mkdtempSync(path.join(output, '.pending-'));
  try {
    const filename = path.join(temporary, 'report');
    fs.writeFileSync(filename, JSON.stringify(data, null, 2) + '\n');
    fs.renameSync(filename, target);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

const lockBytes = fs.readFileSync('package-lock.json');
const lock = JSON.parse(lockBytes);
const lockHash = crypto.createHash('sha256').update(lockBytes).digest('hex');
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

function sha512Integrity(value) {
  if (typeof value !== 'string' || !/^sha512-[A-Za-z0-9+/]{86}==$/.test(value)) return false;
  const digest = value.slice('sha512-'.length);
  return Buffer.from(digest, 'base64').toString('base64') === digest;
}

const application = lock.packages?.[''];
if (!application || typeof application.name !== 'string' || !packageName.test(application.name) ||
    typeof application.version !== 'string' || !application.version) errors.push('missing root package identity');
if (lock.lockfileVersion !== 3) errors.push('lockfileVersion must be 3');
for (const [location, record] of Object.entries(lock.packages)) {
  if (!location) continue;
  const parts = location.startsWith('node_modules/')
    ? location.slice('node_modules/'.length).split('/node_modules/') : [];
  if (!parts.length || parts.some(part => !packageName.test(part))) {
    errors.push(location + ': unsafe or unexpected lock path');
    continue;
  }
  if (!sha512Integrity(record.integrity)) errors.push(location + ': missing SHA512 integrity');
  if (typeof record.version !== 'string' || !record.version.trim()) errors.push(location + ': missing locked version');
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

    const notices = fs.readdirSync(base).filter(name => noticeName.test(name)).sort().map(name => {
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

writeJson(path.join(output, 'inventory.json'), {
  schema: 'oi.frontend-dependency-evidence/1',
  scope: 'local-fictional-development-only',
  commercial_release_cleared: false,
  native_object_linkage_reviewed: false,
  lock_sha256: lockHash,
  records: rows, errors,
});

if (!errors.length) {
  const components = rows.filter(r => r.installed).map(row => {
    const parts = row.name.split('/');
    const archiveHash = Buffer.from(row.integrity.slice('sha512-'.length), 'base64').toString('hex');
    return {
      type: 'library',
      'bom-ref': row.location,
      ...(parts.length === 2 ? { group: parts[0] } : {}),
      name: parts.at(-1),
      version: row.version,
      purl: 'pkg:npm/' + parts.map(encodeURIComponent).join('/') + '@' + encodeURIComponent(row.version),
      licenses: [{ expression: row.license }],
      externalReferences: [{
        type: 'distribution', url: row.resolved,
        hashes: [{ alg: 'SHA-512', content: archiveHash }],
      }],
      properties: [
        { name: 'oi:development-dependency', value: String(lock.packages[row.location].dev === true) },
      ],
    };
  });
  writeJson(bomPath, {
    bomFormat: 'CycloneDX', specVersion: '1.6', version: 1,
    metadata: {
      component: { type: 'application', name: application.name, version: application.version },
      properties: [
        { name: 'oi:scope', value: 'Installed npm build environment for fictional H1 development' },
        { name: 'oi:package-lock-sha256', value: lockHash },
        { name: 'oi:absent-optional-count', value: String(rows.length - components.length) },
        { name: 'oi:license-evidence', value: 'inventory.json' },
      ],
    },
    components,
  });
}
console.log(JSON.stringify({
  installed: rows.filter(r => r.installed).length,
  optional_uninspected: rows.filter(r => !r.installed).length,
  errors,
}, null, 2));
if (errors.length) process.exitCode = 1;

