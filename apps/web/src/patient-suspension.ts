import type {Patient} from './registry-client.js';

export type SuspensionReceipt = Readonly<{
  patient_id:string; revision:number; status:'suspended';
}>;
export type SuspensionState = Readonly<{
  suspensionPhase:'idle'|'sending'|'unknown'|'confirmed'|'rejected';
  suspensionTarget:Readonly<{patient_id:string;revision:number}>|null;
  suspensionReceipt:SuspensionReceipt|null;
  suspensionMessage:string;
}>;
export const emptySuspension = ():SuspensionState => ({
  suspensionPhase:'idle',suspensionTarget:null,suspensionReceipt:null,suspensionMessage:'',
});
export function readSuspensionReceipt(value:unknown,target:Patient):SuspensionReceipt {
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('contract');
  const v=value as Record<string,unknown>;
  if(Object.keys(v).length!==3||v.patient_id!==target.patient_id||v.status!=='suspended'||
     !Number.isSafeInteger(v.revision)||v.revision!==target.revision+1)throw Error('contract');
  return Object.freeze(v as SuspensionReceipt);
}
