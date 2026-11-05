import type {LaboratoryCoding} from './laboratory-result';

// Text nodes only. Neither the label nor a familiar-looking code is a clinical conclusion.
export function codedResultLabel(coding:LaboratoryCoding):string{
  return 'Coded result: '+coding.code+(coding.display===undefined?'':' · Source label: '+coding.display);
}
export function CodingProvenance({coding}:{coding:LaboratoryCoding}){
  return <p>Result code system: <code>{coding.system}</code>
    {coding.version===undefined?null:<> · Code system version: <code>{coding.version}</code></>}</p>;
}
