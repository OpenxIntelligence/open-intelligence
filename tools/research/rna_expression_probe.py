"""Actual processed-RNA research, not clinical interpretation or a model call.

Question: are four previously nominated genes represented across the selected
bulk-RNA libraries, and how sensitive is that view to sample composition?
No raw reads, full matrices, genotypes or treatment recommendations are emitted.
Five fixed libraries, one subject, four specimens spanning three timepoint labels;
not biological replicates. No differential-expression p-values or causal claims.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener
from public_case_intake import build_manifest, CATALOG_URL

BASE='https://sid-sijbrandij-osteosarc-dataset.s3.us-west-2.amazonaws.com/'
SAMPLES=('BG003082','P116686_3','BG009368','SARC0277_T1','SARC0277')
TARGETS=('FAP','CD276','PANX3','MDM2')  # Nominated before reading quantitative values.
CONTEXT=('PTPRC','CD3D','CD3E','COL1A1','COL1A2','ALPL','SPARC')
MAX_EXPANDED=16_000_000


def validate_key(sample: str, suffix: str) -> str:
    if sample not in SAMPLES or suffix not in ('.gene_tpm.gct.gz','.metrics.tsv'):
        raise ValueError('Only fixed processed RNA/QC assets are permitted')
    return f'rna-seq/reprocessed/{sample}/{sample}{suffix}'


def parse_gct(raw: bytes, expected_sample: str) -> dict:
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_EXPANDED:
        raise ValueError('Input size/type')
    if raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
            raw=f.read(MAX_EXPANDED+1)
    if len(raw)>MAX_EXPANDED: raise ValueError('Expanded size cap')
    lines=raw.decode('utf-8').splitlines()
    if len(lines)<4 or lines[0]!='#1.2': raise ValueError('Expected GCT 1.2')
    dims=lines[1].split('\t')
    if len(dims)!=2 or not dims[0].isdigit() or dims[1]!='1':
        raise ValueError('Expected one declared sample column')
    n=int(dims[0])
    if not 0<n<=100000 or len(lines)!=n+3: raise ValueError('Row count mismatch')
    header=lines[2].split('\t')
    if header!=['Name','Description',expected_sample]: raise ValueError('Header/sample mismatch')
    genes={}
    for line in lines[3:]:
        row=line.split('\t')
        if len(row)!=3 or not row[0] or not row[1] or row[0] in genes:
            raise ValueError('Invalid/duplicate gene identity or row shape')
        v=float(row[2])
        if not math.isfinite(v) or v<0: raise ValueError('Invalid expression value')
        genes[row[0]]={'symbol':row[1],'tpm':v}
    total=math.fsum(g['tpm'] for g in genes.values())
    if not math.isfinite(total) or total<=0: raise ValueError('No valid expression mass')
    mt=math.fsum(g['tpm'] for g in genes.values() if g['symbol'].startswith('MT-'))
    positive=sorted(g['tpm'] for g in genes.values() if g['tpm']>0)
    return {'sample':expected_sample,'genes':genes,'metrics':{
        'gene_count':n,'positive_gene_count':len(positive),'tpm_sum':total,
        'mitochondrial_symbol_tpm_fraction':mt/total,
        'top10_tpm_fraction':math.fsum(positive[-10:])/total,
        'decoded_sha256':hashlib.sha256(raw).hexdigest()}}


def gene_summary(matrix: dict, symbol: str) -> dict:
    selected=[(k,v) for k,v in matrix['genes'].items() if v['symbol']==symbol]
    result={'symbol':symbol,'status':'not_in_matrix','tpm':None,
            'positive_gene_percentile':None,'rank_descending':None,
            'positive_gene_denominator':matrix['metrics']['positive_gene_count']}
    if not selected: return result
    if len(selected)!=1: result['status']='ambiguous_symbol';return result
    identifier,row=selected[0]; v=row['tpm']
    result.update(gene_id=identifier,tpm=v,status='reported_zero' if v==0 else 'quantified')
    if v>0:
        a=[g['tpm'] for g in matrix['genes'].values() if g['tpm']>0]
        result['positive_gene_percentile']=100*(sum(x<v for x in a)+.5*sum(x==v for x in a))/len(a)
        result['rank_descending']=1+sum(x>v for x in a)
    return result


def _ranks(values: list[float]) -> list[float]:
    order=sorted(range(len(values)),key=values.__getitem__);out=[0.0]*len(values);i=0
    while i<len(order):
        j=i+1
        while j<len(order) and values[order[j]]==values[order[i]]:j+=1
        for k in range(i,j):out[order[k]]=(i+j+1)/2
        i=j
    return out


def compare_profiles(left: dict, right: dict) -> dict:
    a,b=left['genes'],right['genes'];common=set(a)&set(b)
    ids=sorted(k for k in common if a[k]['symbol']==b[k]['symbol'])
    active=[k for k in ids if a[k]['tpm']>0 or b[k]['tpm']>0]
    x=_ranks([a[k]['tpm'] for k in active]);y=_ranks([b[k]['tpm'] for k in active]);corr=None
    if len(x)>1:
        mx,my=math.fsum(x)/len(x),math.fsum(y)/len(y)
        den=math.sqrt(math.fsum((v-mx)**2 for v in x)*math.fsum((v-my)**2 for v in y))
        if den:corr=math.fsum((u-mx)*(v-my) for u,v in zip(x,y))/den
    return {'left':left['sample'],'right':right['sample'],'matched_gene_ids':len(ids),
            'left_only':len(set(a)-set(b)),'right_only':len(set(b)-set(a)),
            'symbol_disagreements':len(common)-len(ids),'ranked_gene_count':len(active),
            'spearman':corr,'population_or_clinical_inference':False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')


def fetch(url: str, limit: int) -> tuple[bytes,dict]:
    # Disabled per issue 122: case-specific dataset acquisition is not permitted.
    # This matches public_case_intake.fetch_catalog() and single_cell_probe.acquire(),
    # which fail closed with PermissionError. Parser utilities below (parse_gct,
    # gene_summary, compare_profiles, validate_key) are unchanged and are tested
    # only with fictional fixtures.
    raise PermissionError('Sid patient dataset access is disabled: Open Intelligence studies public narratives and uses independent synthetic fixtures, not these records.')
    allowed={CATALOG_URL,BASE+'rna-seq/reprocessed/README.md'}|{
        BASE+validate_key(s,x) for s in SAMPLES for x in ('.gene_tpm.gct.gz','.metrics.tsv')}
    if url not in allowed:raise ValueError('URL outside fixed read scope')
    for attempt in range(2):
        try:
            with build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':'OpenIntelligence-RNA-research/1'}),timeout=45) as r:
                raw=r.read(limit+1)
                if len(raw)>limit:raise ValueError('Download cap')
                receipt={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                         'retrieved_at':datetime.now(timezone.utc).isoformat(),
                         'etag':r.headers.get('ETag'),'last_modified':r.headers.get('Last-Modified')}
                return raw,receipt
        except (OSError,TimeoutError):
            if attempt:raise
            time.sleep(1)
    raise RuntimeError('Unreachable')


def run() -> dict:
    started=datetime.now(timezone.utc).isoformat()
    raw,receipt=fetch(CATALOG_URL,2_000_000)
    manifest=build_manifest(raw,started)
    method,method_receipt=fetch(BASE+'rna-seq/reprocessed/README.md',30000)
    if not all(x in method.decode() for x in ('GTEx V11','GENCODE v47','gene_tpm.gct.gz')):
        raise ValueError('Method declaration changed; re-review required')
    matrices=[];profiles=[]
    for s in SAMPLES:
        prefix=f'rna-seq/reprocessed/{s}'
        matches=[e for e in manifest['entries'] if e['source_record']['path'].rstrip('/')==prefix]
        if len(matches)!=1:raise ValueError('Nonunique or missing catalog binding')
        e=matches[0];r=e['source_record']
        if r['status'] not in ('ok','caution') or r.get('other_donors','').strip().lower() not in ('','no'):
            raise ValueError('Source scope not suitable')
        if len(r['specimen_id'])!=1 or len(r['collection_date'])!=1 or r['reference']!='GRCh38':
            raise ValueError('Unresolved specimen/date/reference')
        b,br=fetch(BASE+validate_key(s,'.gene_tpm.gct.gz'),2_000_000)
        m=parse_gct(b,s);matrices.append(m)
        qc,qr=fetch(BASE+validate_key(s,'.metrics.tsv'),30000)
        qrows=list(csv.reader(io.StringIO(qc.decode()),delimiter='\t'))
        if not qrows or qrows[0]!=['Sample',s]:raise ValueError('QC sample mismatch')
        qdict={line[0]:line[1] for line in qrows[1:] if len(line)==2}
        profiles.append({'sample':s,'catalog_pointer':e['source_pointer'],
            'catalog_row_sha256':e['record_sha256'],'specimen_ids':r['specimen_id'],
            'collection_dates':r['collection_date'],'provider':r['provider'],
            'source_caveat':r.get('caveat',''),'reference':r['reference'],
            'expression_receipt':br,'qc_receipt':qr,'matrix_metrics':m['metrics'],
            'qc_selected':{k:qdict.get(k) for k in ('Mapping Rate','Exonic Rate','Intronic Rate','Duplicate Rate of Mapped','Mapped Unique Reads')},
            'targets':[gene_summary(m,g) for g in TARGETS],
            'context_markers':[gene_summary(m,g) for g in CONTEXT]})
    pairs=[compare_profiles(a,b) for i,a in enumerate(matrices) for b in matrices[i+1:]]
    summary={g:{'quantified_libraries':sum(gene_summary(m,g)['status']=='quantified' for m in matrices),
                'library_count':len(matrices)} for g in TARGETS}
    return {'status':'analyzed','question':'Do previously nominated target-gene RNA signals recur across five selected libraries, and what limits comparison?',
            'started_at':started,'completed_at':datetime.now(timezone.utc).isoformat(),
            'catalog_receipt':receipt,'method_receipt':method_receipt,'library_count':len(profiles),
            'specimen_count':len({v for p in profiles for v in p['specimen_ids']}),
            'collection_date_count':len({v for p in profiles for v in p['collection_dates']}),
            'profiles':profiles,'pairwise_profiles':pairs,'target_recurrence':summary,
            'scope':{'method':'RNA-SeQC gene TPM; supplied GTEx V11 reprocessing, GRCh38/GENCODE v47',
                     'analysis_executed':True,'ml_model_executed':False,'raw_read_alignment_executed':False,
                     'clinical_interpretation_authorized':False,'historical_replay':False,
                     'targets_selected_from_prior_case_narrative_not_discovered':True},
            'limits':['One person; five libraries are not five independent patients or biological replicates.',
                      'Rank percentile is within positive genes in this library, not a normal-tissue or cancer-population percentile.',
                      'TPM is compositional. Common reprocessing does not remove library, sampling or cell-composition differences.',
                      'Bulk RNA does not localize expression to malignant cells or establish surface protein, safety, efficacy, or treatment response.',
                      'No normal-tissue comparison, differential-expression testing, causal attribution or therapy ranking was performed.',
                      'Current reprocessing cannot establish what was known at the historical collection date.'],
            'reviewable_followup':['Check cell-type-resolved expression and orthogonal protein evidence for any proposed target.',
                                   'Use appropriately processed normal-tissue references before any specificity claim.',
                                   'Separate sampling/library effects from genuine biological change.']}


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=run()
    except Exception as exc:
        result={'status':'failed','error_type':type(exc).__name__,'error':str(exc),
                'analysis_complete':False,'clinical_interpretation_authorized':False}
    result['python']=platform.python_version()
    result['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('test_rna_expression_probe.py'))}
    result['checkout']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    out.write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps({'status':result['status'],'libraries':result.get('library_count')}))
    if result['status']!='analyzed':raise SystemExit(1)

if __name__=='__main__':main()
