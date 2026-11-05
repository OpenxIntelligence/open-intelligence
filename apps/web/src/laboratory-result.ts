// The result coding is the source's answer. LOINC separately identifies the test.
export type LaboratoryCoding=Readonly<{
  system:'urn:oi:synthetic:lab-results';code:string;version?:string;display?:string;
}>;
type AbsentReason='unknown'|'not-performed'|'error'|'masked';
export type LaboratoryValue=Readonly<
  {status:'reported_value';value_text:string;unit_code:string;absent_reason:null}|
  {status:'reported_absent';value_text:null;unit_code:null;absent_reason:AbsentReason}|
  {status:'reported_coded';value_text:null;unit_code:null;absent_reason:null;coded_result:LaboratoryCoding}
>;

const token=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(v);
const record=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
export function laboratoryValueKeys(v:unknown):string[]{
  const base=['status','value_text','unit_code','absent_reason'];
  return record(v)&&v.status==='reported_coded'?[...base,'coded_result']:base;
}

function readCoding(v:unknown):LaboratoryCoding{
  if(!record(v)||!Object.hasOwn(v,'system')||!Object.hasOwn(v,'code')||
    Object.keys(v).some(k=>!['system','code','version','display'].includes(k))||
    v.system!=='urn:oi:synthetic:lab-results'||!token(v.code)||
    (Object.hasOwn(v,'version')&&!token(v.version))||
    (Object.hasOwn(v,'display')&&(typeof v.display!=='string'||v.display.length<1||v.display.length>120||
      /[^ -~]/.test(v.display)||v.display!==v.display.trim())))throw Error('Invalid laboratory result coding');
  return Object.freeze({...v} as LaboratoryCoding);
}

// The enclosing contract also rejects any extra source or clinical fields.
export function readLaboratoryValue(v:Record<string,unknown>):LaboratoryValue{
  if(laboratoryValueKeys(v).some(key=>!Object.hasOwn(v,key)))throw Error('Missing laboratory result field');
  const {status,value_text,unit_code,absent_reason}=v;
  if(status==='reported_coded'&&value_text===null&&unit_code===null&&absent_reason===null)
    return {status,value_text,unit_code,absent_reason,coded_result:readCoding(v.coded_result)};
  if(!Object.hasOwn(v,'coded_result')){
    // Each reader applies its original length and character rules to quantities.
    if(status==='reported_value'&&typeof value_text==='string'&&typeof unit_code==='string'&&absent_reason===null)
      return {status,value_text,unit_code,absent_reason};
    if(status==='reported_absent'&&value_text===null&&unit_code===null&&
       (absent_reason==='unknown'||absent_reason==='not-performed'||absent_reason==='error'||absent_reason==='masked'))
      return {status,value_text,unit_code,absent_reason};
  }
  throw Error('Invalid laboratory result');
}

export function sameLaboratoryValue(a:LaboratoryValue,b:LaboratoryValue):boolean{
  if(a.status==='reported_coded'&&b.status==='reported_coded'){
    const x=a.coded_result,y=b.coded_result;
    return x.system===y.system&&x.code===y.code&&x.version===y.version&&x.display===y.display;
  }
  return a.status===b.status&&a.value_text===b.value_text&&a.unit_code===b.unit_code&&a.absent_reason===b.absent_reason;
}
