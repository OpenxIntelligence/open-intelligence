import type {Encounter,VisitState} from './encounter-client';

export type StatusFilter='all'|VisitState;
export function matchingVisits(visits:readonly Encounter[],query:string,status:StatusFilter){
  const words=query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return visits.filter(visit=>{
    if(status!=='all'&&visit.status!==status)return false;
    const text=[visit.external_key,visit.kind,visit.service_date,visit.status.replaceAll('_',' ')].join(' ').toLowerCase();
    return words.every(word=>text.includes(word));
  });
}
