/** View state only. Canonical originals and annotation history remain server-owned. */
export type Finding={key:string;state:string;quote:string;line:number};
export type Preview={filename:string;sha256:string;byte_count:number;media_type:string;text:string;lines:{line:number;text:string;page?:number;page_line?:number}[];extraction_sha256?:string;clinical_review:'not_performed'};
export type Summary={source_id:string;document_id:string;version:number;state:'current'|'superseded';sha256:string;filename:string};
export type Revision={revision_id:string;revision:number;findings:Finding[];reason:string;classification_origin:'user_selected';clinical_review:'not_performed'};
export type Document=Summary&{preview:Preview;revisions:Revision[]};
export type Saved={source_id:string;version:number;annotation_revision_id:string;duplicate:boolean};
export type DocumentReply={status:number;body:unknown;headers?:Headers};
export type DocumentRequest=(path:string,body?:string)=>Promise<DocumentReply>;
export type DocumentUpload={synthetic:true;filename:string;original_base64:string};
const hash=/^[a-f0-9]{64}$/, source=/^SRC-[A-F0-9]{32}$/, annotation=/^ANN-[A-F0-9]{32}$/;
const filename=/^[A-Za-z0-9][A-Za-z0-9._ ()-]*\.(txt|pdf)$/i;
const object=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
const integer=(x:unknown,min:number,max:number)=>Number.isSafeInteger(x)&&Number(x)>=min&&Number(x)<=max;
export async function documentByteHash(bytes:Uint8Array<ArrayBuffer>):Promise<string>{
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
}
export function parsePreview(x:unknown):Preview{
 if(!object(x)||typeof x.filename!=='string'||x.filename.length>120||!filename.test(x.filename)||x.filename.includes('..')||
    typeof x.sha256!=='string'||!hash.test(x.sha256)||!integer(x.byte_count,1,65536)||typeof x.text!=='string'||new TextEncoder().encode(x.text).length>65536||
    !['text/plain; charset=utf-8','application/pdf'].includes(String(x.media_type))||x.clinical_review!=='not_performed'||
    !Array.isArray(x.lines)||x.lines.length>512||x.lines.length<1)throw Error('Invalid document preview');
 const pdf=x.media_type==='application/pdf';
 if(pdf&&(typeof x.extraction_sha256!=='string'||!hash.test(x.extraction_sha256)))throw Error('Missing extraction identity');
 x.lines.forEach((line,i)=>{if(!object(line)||line.line!==i+1||typeof line.text!=='string'||
  (pdf&&(!integer(line.page,1,20)||!integer(line.page_line,1,512))))throw Error('Invalid extraction anchor');});
 return x as Preview;
}
function summary(x:unknown):Summary{
 if(!object(x)||typeof x.source_id!=='string'||!source.test(x.source_id)||typeof x.document_id!=='string'||
 !/^[A-Z][A-Z0-9-]{1,39}$/.test(x.document_id)||!integer(x.version,1,2147483647)||!['current','superseded'].includes(String(x.state))||
 typeof x.sha256!=='string'||!hash.test(x.sha256)||typeof x.filename!=='string'||!filename.test(x.filename)||x.filename.includes('..'))throw Error('Invalid document identity');
 return x as Summary;
}
function document(x:unknown,id:string):Document{
 const item=summary(x);if(!object(x)||item.source_id!==id)throw Error('Wrong source');
 const preview=parsePreview(x.preview);if(preview.sha256!==item.sha256||preview.filename!==item.filename)throw Error('Changed original');
 if(!Array.isArray(x.revisions)||x.revisions.length<1||x.revisions.length>64)throw Error('Missing selection history');
 for(const [i,rev] of x.revisions.entries()){
  if(!object(rev)||rev.revision!==i+1||typeof rev.revision_id!=='string'||!annotation.test(rev.revision_id)||
   rev.classification_origin!=='user_selected'||rev.clinical_review!=='not_performed'||typeof rev.reason!=='string'||!Array.isArray(rev.findings)||rev.findings.length>30)throw Error('Invalid revision');
  for(const f of rev.findings)if(!object(f)||typeof f.key!=='string'||typeof f.state!=='string'||typeof f.quote!=='string'||
    !integer(f.line,1,preview.lines.length)||!preview.lines[Number(f.line)-1].text.includes(f.quote))throw Error('Invalid selected passage');
 }
 return {...item,preview,revisions:x.revisions as Revision[]};
}
function saved(x:unknown):Saved{
 if(!object(x)||typeof x.source_id!=='string'||!source.test(x.source_id)||!integer(x.version,1,2147483647)||
  typeof x.annotation_revision_id!=='string'||!annotation.test(x.annotation_revision_id)||typeof x.duplicate!=='boolean')throw Error('Invalid save receipt');
 return x as Saved;
}
type State={phase:'idle'|'loading'|'saving'|'uncertain'|'error';message:string;preview:Preview|null;document:Document|null;documents:Summary[];receipt:Saved|null;pending:{path:string;body:string}|null};
const empty=():State=>({phase:'idle',message:'Choose a fictional text or PDF record. Files are sent only when you request a preview.',preview:null,document:null,documents:[],receipt:null,pending:null});
export class DocumentClient{
 #state=empty();#generation=0;#listeners=new Set<()=>void>();
 constructor(private request:DocumentRequest){}
 snapshot=()=>this.#state;
 subscribe=(fn:()=>void)=>{this.#listeners.add(fn);return()=>{this.#listeners.delete(fn);}};
 #set(patch:Partial<State>){this.#state={...this.#state,...patch};for(const fn of this.#listeners)fn();}
 dispose=()=>{this.#generation++;this.#state=empty();this.#listeners.clear();};
 discard=()=>{if(this.#state.phase==='saving')return;this.#generation++;this.#set({...empty(),documents:this.#state.documents,message:'Local intent discarded. A prior uncertain request may still have been saved.'});};
 async #read(path:string,payload:unknown,accept:(body:unknown)=>Partial<State>|Promise<Partial<State>>){
  if(this.#state.pending||this.#state.phase==='saving')return;
  const generation=++this.#generation;this.#set({phase:'loading',preview:null,document:null,receipt:null});
  try{const res=await this.request(path,payload===undefined?undefined:JSON.stringify(payload));if(generation!==this.#generation)return;
   if([401,403,404].includes(res.status)){this.#set({...empty(),phase:'error',message:'Document access unavailable. Recheck case access.'});return;}
   if(res.status!==200)throw Error('Document unavailable or unsupported. Nothing has been saved.');
   const accepted=await accept(res.body);
   if(generation!==this.#generation)return;
   this.#set({...accepted,phase:'idle',message:'Inspect the original text and exact selected passages. Clinical review has not been performed.'});
  }catch(e){if(generation===this.#generation)this.#set({phase:'error',message:e instanceof Error?e.message:'Document unavailable'});}
 }
 preview=(payload:DocumentUpload)=>{
  const {filename,original_base64}=payload;
  return this.#read('/preview',payload,async body=>{
   const preview=parsePreview(body);
   const pdf=filename.toLowerCase().endsWith('.pdf');
   const bytes=Uint8Array.from(atob(original_base64),c=>c.charCodeAt(0));
   if(preview.filename!==filename||preview.byte_count!==bytes.length||
      preview.media_type!==(pdf?'application/pdf':'text/plain; charset=utf-8')||
      !object(body)||body.extraction_method!==(pdf?'pypdf-text-v1':'utf8-plain-text-v1')||
      body.annotation_method!==(pdf?'manual-exact-extraction-line-selection':'manual-exact-line-selection')||
      preview.sha256!==await documentByteHash(bytes)){
    throw Error('The preview does not match the selected file. Select the original and preview it again.');
   }
   return {preview};
  });
 };
 load=()=>this.#read('',undefined,body=>{if(!object(body)||!Array.isArray(body.documents)||body.documents.length>512)throw Error('Invalid document listing');return{documents:body.documents.map(summary)};});
 open=(id:string)=>{if(!source.test(id))return Promise.resolve();return this.#read('/'+id,undefined,body=>({document:document(body,id)}));};
 async save(path:string,payload:unknown){if(this.#state.pending||this.#state.phase==='loading'||this.#state.phase==='saving')return;
  this.#set({pending:{path,body:JSON.stringify(payload)}});await this.retry();}
 async retry(){const pending=this.#state.pending;if(!pending||this.#state.phase==='saving')return;
  const generation=++this.#generation;this.#set({phase:'saving',message:'Saving the exact confirmed intent…'});
  try{const res=await this.request(pending.path,pending.body);if(generation!==this.#generation)return;
   if([401,403,404].includes(res.status)){this.#set({...empty(),phase:'error',message:'Access unavailable. Local document and intent cleared.'});return;}
   if(res.status>=400&&res.status<500&&![408,429].includes(res.status)){this.#set({phase:'error',pending:null,message:'The server rejected this request. Refresh before correcting or amending.'});return;}
   if(![200,201].includes(res.status))throw Error('uncertain');
   const receipt=saved(res.body);this.#set({phase:'idle',pending:null,preview:null,document:null,receipt,message:'Saved. Original bytes and earlier selection revisions remain preserved.'});
  }catch{if(generation===this.#generation)this.#set({phase:'uncertain',message:'Save outcome unknown. Retry the exact request to recover its receipt; no automatic retry occurs.'});}
 }
}
