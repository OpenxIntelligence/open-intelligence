// Review evidence, not legal advice or whole-product clearance. No package execution.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const root=process.cwd(),lock=JSON.parse(fs.readFileSync('package-lock.json','utf8'));
const allowed=new Set(['MIT','ISC','BSD-2-Clause','BSD-3-Clause','Apache-2.0','0BSD','CC0-1.0','(MIT OR Apache-2.0)','(Apache-2.0 OR MIT)']);
const rows=[],errors=[];
if(lock.lockfileVersion!==3)errors.push('lockfileVersion must be 3');
for(const [location,record] of Object.entries(lock.packages)){
 if(!location)continue;
 if(!location.startsWith('node_modules/')){errors.push('unexpected lock path');continue;}
 const base=path.resolve(root,location);
 if(!base.startsWith(path.join(root,'node_modules')+path.sep)){errors.push('unsafe lock path');continue;}
 if(!record.integrity?.startsWith('sha512-'))errors.push(location+': missing SHA512 integrity');
 if(typeof record.resolved!=='string'||!record.resolved.startsWith('https://registry.npmjs.org/'))errors.push(location+': unapproved registry');
 if(!allowed.has(record.license))errors.push(location+': unreviewed lock license '+record.license);
 const manifest=path.join(base,'package.json');
 if(!fs.existsSync(manifest)){
  if(record.optional){rows.push({location,version:record.version,license:record.license,installed:false,scope:'optional-platform-not-inspected',integrity:record.integrity});continue;}
  errors.push(location+': required package missing');continue;
 }
 const p=JSON.parse(fs.readFileSync(manifest,'utf8'));
 if(p.version!==record.version)errors.push(location+': installed version mismatch');
 if(!allowed.has(p.license))errors.push(location+': unreviewed installed license');
 const notices=fs.readdirSync(base).filter(n=>/^(license|licence|copying|notice)(\.|$)/i.test(n)&&fs.statSync(path.join(base,n)).isFile()).map(name=>{
  const bytes=fs.readFileSync(path.join(base,name));const text=bytes.toString('utf8');
  if(/GNU (?:AFFERO |LESSER )?GENERAL PUBLIC LICENSE|CC-BY-NC|Commons Clause|Elastic License/i.test(text))errors.push(location+': manual restrictive-term review required');
  return {name,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),text};
 });
 if(!notices.length)errors.push(location+': actual LICENSE/NOTICE file missing');
 rows.push({location,name:p.name,version:p.version,license:p.license,integrity:record.integrity,resolved:record.resolved,installed:true,notice_files:notices});
}
fs.mkdirSync('.licenses',{recursive:true});
fs.writeFileSync('.licenses/inventory.json',JSON.stringify({schema:'oi.frontend-dependency-evidence/1',scope:'local-fictional-development-only',commercial_release_cleared:false,native_object_linkage_reviewed:false,lock_sha256:crypto.createHash('sha256').update(fs.readFileSync('package-lock.json')).digest('hex'),records:rows,errors},null,2)+'\n');
console.log(JSON.stringify({installed:rows.filter(r=>r.installed).length,optional_uninspected:rows.filter(r=>!r.installed).length,errors},null,2));
if(errors.length)process.exitCode=1;
