export type AnimalSpecies = 'dog' | 'cat';
export type VeterinaryIntent =
  | { kind: 'register'; species: AnimalSpecies; system: string; reference: string; key: string }
  | { kind: 'open'; animal: string; key: string }
  | { kind: 'read'; animal: string; caseId?: string };
export type VeterinaryResult =
  | { kind: 'receipt'; animal: string; caseId?: string; duplicate: boolean }
  | { kind: 'record'; animal: string; caseId?: string; species: AnimalSpecies; org: string; created: string };

const animalId = /^ANM-[0-9A-F]{32}$/;
const caseId = /^VCASE-[0-9A-F]{32}$/;
const key = /^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$/;

export class VeterinaryRequestError extends Error {
  constructor(readonly status: number) { super('Veterinary request declined'); }
}

export async function requestVeterinary(token: string, intent: VeterinaryIntent, signal: AbortSignal,
  transport: typeof fetch = fetch): Promise<VeterinaryResult> {
  let path = '/v1/veterinary/animals';
  let payload;
  if (intent.kind === 'register') {
    payload = {synthetic: true, species: intent.species, source_system: intent.system,
      source_subject_ref: intent.reference, request_key: intent.key};
  } else {
    if (!animalId.test(intent.animal)) throw new Error('Invalid animal ID');
    path += '/' + intent.animal;
    if (intent.kind === 'open') {
      path += '/cases';
      payload = {synthetic: true, request_key: intent.key};
    } else if (intent.caseId) {
      if (!caseId.test(intent.caseId)) throw new Error('Invalid case ID');
      path += '/cases/' + intent.caseId;
    }
  }
  const response = await transport(path, {
    method: payload ? 'POST' : 'GET', body: payload ? JSON.stringify(payload) : undefined,
    headers: {Authorization: 'Bearer ' + token, ...(payload && {'Content-Type': 'application/json'})},
    signal, cache: 'no-store', credentials: 'omit', redirect: 'error', mode: 'same-origin',
  });
  if (!response.ok) throw new VeterinaryRequestError(response.status);
  const data = await response.json();
  const expectsCase = intent.kind === 'open' || (intent.kind === 'read' && !!intent.caseId);
  if (!data || typeof data.animal_id !== 'string' || !animalId.test(data.animal_id) ||
      (intent.kind !== 'register' && data.animal_id !== intent.animal) ||
      (expectsCase ? typeof data.case_id !== 'string' || !caseId.test(data.case_id) : 'case_id' in data))
    throw new Error('Unexpected veterinary subject');
  if (intent.kind !== 'read') {
    if (typeof data.duplicate !== 'boolean' || response.status !== (data.duplicate ? 200 : 201))
      throw new Error('Unexpected registration receipt');
    return {kind: 'receipt', animal: data.animal_id, caseId: data.case_id, duplicate: data.duplicate};
  }
  if (response.status !== 200 || data.case_id !== intent.caseId || !['dog','cat'].includes(data.species) ||
      typeof data.origin_org !== 'string' || !key.test(data.origin_org) ||
      typeof data.created_at !== 'string' || !Number.isFinite(Date.parse(data.created_at)))
    throw new Error('Unexpected veterinary record');
  return {kind: 'record', animal: data.animal_id, caseId: data.case_id, species: data.species,
    org: data.origin_org, created: data.created_at};
}
