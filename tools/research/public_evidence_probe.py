"""Bounded public-data research, NOT a clinical importer or patient application.

Only fixed public endpoints are queried. Raw data remains in memory; reports
contain aggregate counts/schema and hashes, never subject identifiers or rows.
TCIA: Bakr et al., doi:10.7937/K9/TCIA.2017.7hs46erv (CC BY 3.0),
doi:10.1038/sdata.2018.202; Clark et al. doi:10.1007/s10278-013-9622-7.
GDC: public TCGA-LUAD case data only, no controlled files, reidentification,
external linkage, model training or clinical inference.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, re, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TCIA_CSV = ('https://wiki.cancerimagingarchive.net/download/attachments/28672347/'
 'NSCLCR01Radiogenomic_DATA_LABELS_2018-05-22_1500-shifted.csv?api=v2&modificationDate=1531967714295&version=1')
TCIA_AIM = ('https://wiki.cancerimagingarchive.net/download/attachments/28672347/'
 'AIM_files_updated-11-10-2020.zip?api=v2&modificationDate=1605631114167&version=1')
MISSING = {'', 'na', 'n/a', 'nan', 'null', 'none', 'unknown', 'not collected',
 'not available', 'not reported', '[not available]', '[not reported]', '--'}
LIMIT = 32 * 1024 * 1024

def read_csv(raw: bytes) -> tuple[list[str], list[dict[str,str]]]:
    text=raw.decode('utf-8-sig')
    reader=csv.DictReader(io.StringIO(text))
    columns=reader.fieldnames or []
    if not columns or any(c is None for c in columns):
        raise ValueError('Missing CSV header')
    rows=list(reader)
    if any(None in row for row in rows):
        raise ValueError('Unexpected extra CSV columns')
    return columns, rows

def identifier_column(columns: list[str]) -> str:
    return next((c for c in columns if re.sub(r'[^a-z0-9]','',c.lower())
                 in {'patientid','patientidentifier','subjectid','caseid'}), columns[0])

def profile_csv(raw: bytes) -> dict:
    columns, rows=read_csv(raw)
    key=identifier_column(columns)
    ids=[str(r.get(key) or '').strip() for r in rows]
    return {'rows':len(rows), 'columns':len(columns), 'column_names':columns,
        'identifier_column':key, 'unique_identifiers':len(set(ids)-{''}),
        'duplicate_identifiers':len([i for i in ids if i])-len(set(ids)-{''}),
        'blank_identifiers':ids.count(''),
        'missing_by_column':{c:sum(str(r.get(c) or '').strip().lower() in MISSING for r in rows) for c in columns},
        'missingness_rule':sorted(MISSING),
        'clinical_inference_performed':False}

def profile_gdc(cases: list[dict]) -> dict:
    diagnoses=[d for c in cases for d in c.get('diagnoses',[])]
    samples=[s for c in cases for s in c.get('samples',[])]
    treatments=[t for d in diagnoses for t in d.get('treatments',[])]
    followups=[f for d in diagnoses for f in d.get('follow_ups',[])]
    aliquots=[a for s in samples for p in s.get('portions',[]) for n in p.get('analytes',[]) for a in n.get('aliquots',[])]
    numbers=lambda v: isinstance(v,(int,float)) and not isinstance(v,bool)
    ids=[c.get('case_id') for c in cases]
    return {'cases':len(cases), 'unique_case_ids':len(set(ids)-{None}),
        'diagnoses':len(diagnoses), 'samples':len(samples), 'aliquots':len(aliquots),
        'treatments':len(treatments), 'follow_ups':len(followups),
        'cases_with_multiple_samples':sum(len(c.get('samples',[]))>1 for c in cases),
        'cases_with_diagnosis_records':sum(bool(c.get('diagnoses')) for c in cases),
        'cases_with_treatment_records':sum(any(d.get('treatments') for d in c.get('diagnoses',[])) for c in cases),
        'cases_with_followup_records':sum(any(d.get('follow_ups') for d in c.get('diagnoses',[])) for c in cases),
        'treatments_with_numeric_start_offset':sum(numbers(t.get('days_to_treatment_start')) for t in treatments),
        'treatments_with_numeric_end_offset':sum(numbers(t.get('days_to_treatment_end')) for t in treatments),
        'naive_diagnosis_sample_inner_join_rows':sum(len(c.get('diagnoses',[]))*len(c.get('samples',[])) for c in cases),
        'case_fields':sorted({k for c in cases for k in c}),
        'diagnosis_fields':sorted({k for d in diagnoses for k in d}),
        'treatment_fields':sorted({k for t in treatments for k in t}),
        'absence_interpreted_as_no_treatment':False,
        'clinical_inference_performed':False}

def fetch_bytes(url: str, attempts: int=2) -> tuple[bytes,dict]:
    last=None
    for attempt in range(attempts):
        try:
            req=Request(url,headers={'User-Agent':'OpenIntelligence-PublicResearch/1.0','Accept':'*/*'})
            with urlopen(req, timeout=35) as r:
                raw=r.read(LIMIT+1)
                if len(raw)>LIMIT: raise ValueError('Response exceeds bounded research limit')
                return raw, {'url':url,'final_url':r.geturl(),'bytes':len(raw),
                    'sha256':hashlib.sha256(raw).hexdigest(),
                    'retrieved_at':datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            last=exc
            if attempt+1<attempts: time.sleep(1)
    raise RuntimeError(type(last).__name__) from last

def tcia_probe() -> dict:
    raw, receipt=fetch_bytes(TCIA_CSV)
    columns,rows=read_csv(raw)
    ids={str(r.get(identifier_column(columns)) or '').strip() for r in rows}-{''}
    result={'status':'tested','source':'TCIA NSCLC Radiogenomics clinical CSV',
        'rights':'Collection lists CC BY 3.0; TCIA no-reidentification and citation policy applies',
        'data_doi':'10.7937/K9/TCIA.2017.7hs46erv', 'receipt':receipt,'clinical':profile_csv(raw)}
    try:
        data,zreceipt=fetch_bytes(TCIA_AIM)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos=[i for i in z.infolist() if i.filename.lower().endswith('.xml') and not i.filename.startswith('__MACOSX/')]
            if sum(i.file_size for i in infos)>LIMIT: raise ValueError('Archive expands beyond limit')
            linked=set(); unlinked=set(); counts=[]
            for info in infos:
                # Match only published aliases within this same collection, never identities.
                text=z.read(info).decode('utf-8-sig')
                found=set(re.findall(r'(?:R01|AMC)-\d{3}',text))
                linked.update(found & ids); unlinked.update(found-ids)
                counts.append(len(found))
            result['annotations']={'receipt':zreceipt,'xml_files':len(infos),
                'unique_aliases_matching_clinical':len(linked), 'unique_aliases_not_matching_clinical':len(unlinked),
                'files_with_no_alias_match':sum(n==0 for n in counts),
                'clinical_subjects_without_matched_annotation':len(ids-linked),
                'join_scope':'Within-collection published aliases only; no reidentification or cross-cohort linkage',
                'image_pixels_downloaded':False, 'rna_data_downloaded':False}
    except Exception as exc:
        result['annotations']={'status':'retrieval_failed','error_type':type(exc).__name__}
    return result

def gdc_probe() -> dict:
    filters={'op':'in','content':{'field':'project.project_id','value':['TCGA-LUAD']}}
    params={'filters':json.dumps(filters,separators=(',',':')), 'size':100,'sort':'case_id:asc',
        'expand':'diagnoses,diagnoses.treatments,diagnoses.follow_ups,samples,samples.portions,samples.portions.analytes,samples.portions.analytes.aliquots'}
    raw,receipt=fetch_bytes('https://api.gdc.cancer.gov/cases?'+urlencode(params))
    data=json.loads(raw)['data']; cases=data['hits']; total=data['pagination']['total']
    if len(cases)!=min(100,total): raise ValueError('Incomplete bounded API response')
    return {'status':'tested','source':'GDC open TCGA-LUAD cases endpoint',
        'sampling':'First 100 case_id ascending, not random; one cancer project, not population-representative',
        'population_in_response':total,'query':params,'receipt':receipt,
        'rights':'Public clinical/biospecimen data; GDC no-reidentification and study-specific policies apply',
        'profile':profile_gdc(cases)}

def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    results={'purpose':'Public research feasibility/structure audit, not diagnosis, treatment or clinical validation',
        'raw_subject_rows_published':False,'experiments':{}}
    for name,func in [('tcia_multimodal',tcia_probe),('gdc_case_structure',gdc_probe)]:
        try: results['experiments'][name]=func()
        except Exception as exc: results['experiments'][name]={'status':'failed','error_type':type(exc).__name__,'reason':str(exc)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))
    if not any(r['status']=='tested' for r in results['experiments'].values()): raise SystemExit(2)
if __name__=='__main__':main()
