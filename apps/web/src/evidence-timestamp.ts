/** Validate evidence wire dates without Date.parse rollover or normalization.
 * The authored and citation APIs have distinct, existing precision contracts.
 */
export function evidenceCalendarDate(value:unknown):value is string{
 if(typeof value!=='string'||value.length!==10||!/[0-9]{4}-[0-9]{2}-[0-9]{2}/.test(value))return false;
 const year=Number(value.slice(0,4)),month=Number(value.slice(5,7)),day=Number(value.slice(8,10));
 const leap=year%4===0&&(year%100!==0||year%400===0);
 const days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
 return year>=1&&month>=1&&month<=12&&day>=1&&day<=days[month-1];
}

export function authoredEvidenceTimestamp(value:unknown):value is string{
 if(typeof value!=='string'||value.length>64)return false;
 const parts=/^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]+))?)?(Z|[+-]([0-9]{2}):([0-9]{2}))$/.exec(value);
 // JavaScript's $ also matches before a final newline; the wire must match whole.
 if(!parts||parts[0]!==value)return false;
 return evidenceCalendarDate(value.slice(0,10))&&
  Number(parts[4])<=23&&Number(parts[5])<=59&&Number(parts[6]??0)<=59&&
  (parts[8]==='Z'||Number(parts[9])<=23&&Number(parts[10])<=59);
}

export function citationEvidenceTimestamp(value:unknown):value is string{
 return authoredEvidenceTimestamp(value)&&
  /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(value);
}
