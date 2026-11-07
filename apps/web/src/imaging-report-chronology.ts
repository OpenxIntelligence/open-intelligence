import type {SourceVersion} from './source-contracts.js';

export type ImagingDateGroup=Readonly<{date:string;reports:readonly SourceVersion[]}>;

/** Read-only chronology of the source records this case has already authorized.
 * No image matching, clinical comparison, or historical image read is implied. */
export function buildImagingChronology(sources:readonly SourceVersion[]):readonly ImagingDateGroup[]{
 const dates=new Map<string,SourceVersion[]>();
 for(const source of sources){
  if(source.kind!=='imaging')continue;
  const records=dates.get(source.event_date);
  if(records)records.push(source);
  else dates.set(source.event_date,[source]);
 }
 return Object.freeze(Array.from(dates.keys()).sort((a,b)=>b.localeCompare(a)).map(date=>
  Object.freeze({date,reports:Object.freeze(dates.get(date)!)})));
}
