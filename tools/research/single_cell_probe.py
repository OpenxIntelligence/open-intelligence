"""Bounded descriptive logic for independently authored synthetic single-cell input.

This is a research adapter, not a clinical model or an independent annotation.
Never equate AnnData.raw with raw counts, a source label with malignancy, or cells
with independent patient replicates. Only aggregates leave RAM. Historical
case acquisition and its case-configured inspection entrypoint are retired.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import tempfile
from datetime import date, datetime, timezone
import urllib.request

TARGETS = ('FAP', 'CD276', 'PANX3', 'MDM2')
CONTROLS = ('PTPRC', 'CD3D', 'LST1', 'COL1A1', 'COL1A2')
BASE = 'https://sid-sijbrandij-osteosarc-dataset.s3.us-west-2.amazonaws.com/'
H5_URL = BASE + 'kamil/tumor/analysis/run2/tumor_run2_analyzed.h5ad'
CATALOG_URL = 'https://osteosarc.com/data/catalog/datasets.json'
H5_LIMIT = 2_000_000_000
EXPECTED_H5_SHA256 = '9ac4f1c24bd2ea4ce194cb8cc069b7bbbdc8169dc416e668e25be8168507d62e'
SAMPLE_DATES = {'T1':'2024-06-06','T2':'2025-01-28','T3':'2025-04-17','T3_CD45neg':'2025-04-17'}


def _text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def _safe(parent, key):
    """Do not follow an HDF5 external or soft link supplied by an input file."""
    import h5py
    if not isinstance(key, str) or not key or '/' in key or key in ('.', '..'):
        raise ValueError('only direct child HDF5 fields are supported')
    if key not in parent or not isinstance(parent.get(key, getlink=True), h5py.HardLink):
        raise ValueError('required field missing or indirect HDF5 link')
    node = parent[key]
    if isinstance(node, h5py.Dataset) and (node.is_virtual or node.external):
        raise ValueError('external/virtual dataset not supported')
    return node


def read_column(parent, key):
    """Decode AnnData string or categorical column; -1 is missing, not last label."""
    import h5py
    import numpy as np
    node = _safe(parent, key)
    if isinstance(node, h5py.Dataset):
        if len(node.shape) != 1 or len(node) > 100_000:
            raise ValueError('column exceeds bounded one-dimensional schema')
        return [_text(x) for x in node[:]]
    if _text(node.attrs.get('encoding-type','')) != 'categorical':
        raise ValueError('unsupported column encoding')
    codes = _safe(node, 'codes')[:]
    categories = _safe(node, 'categories')[:]
    if codes.ndim != 1 or categories.ndim != 1 or len(codes) > 100_000:
        raise ValueError('unsupported categorical shape')
    if not np.issubdtype(codes.dtype, np.integer) or np.any(codes < -1) or np.any(codes >= len(categories)):
        raise ValueError('invalid categorical index')
    decoded = [_text(x) for x in categories]
    return [None if int(x) == -1 else decoded[int(x)] for x in codes]


def resolve_genes(var, genes):
    """Exact symbols only. Absent is None; ambiguity is not silently collapsed."""
    key = _text(var.attrs.get('_index', '_index'))
    names = read_column(var, key)
    result = {}
    for gene in genes:
        found = [i for i,name in enumerate(names) if name == gene]
        if len(found) > 1:
            raise ValueError('ambiguous gene symbol')
        result[gene] = found[0] if found else None
    return result


def matrix_shape(node):
    import h5py
    shape = node.shape if isinstance(node, h5py.Dataset) else node.attrs.get('shape', ())
    if len(shape) != 2 or any(int(n) <= 0 or int(n) > 100_000 for n in shape):
        raise ValueError('unsupported expression matrix dimensions')
    return tuple(int(n) for n in shape)


def read_selected_matrix(node, columns, n_rows, n_cols, *, require_integer=False):
    """Read bounded dense or canonical CSR data without densifying full matrix.

    Reject nonfinite or negative stored values: a centered/scaled matrix cannot
    define detection as value > 0. Unselected entries are validated too.
    """
    import h5py
    import numpy as np
    if matrix_shape(node) != (n_rows, n_cols):
        raise ValueError('matrix and metadata dimensions disagree')
    if not columns or len(columns) != len(set(columns)) or any(type(i) is not int or i<0 or i>=n_cols for i in columns):
        raise ValueError('invalid selected feature indices')
    result = np.zeros((n_rows, len(columns)), dtype=np.float64)
    def check(values):
        if values.dtype.kind not in 'iuf' or not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError('nonnegative finite expression required; centered/invalid scale held')
        if require_integer and np.any(values != np.floor(values)):
            raise ValueError('source count layer contains fractional values')
    if isinstance(node, h5py.Dataset):
        if node.is_virtual or node.external:
            raise ValueError('indirect expression storage denied')
        for start in range(0,n_rows,128):
            values = node[start:start+128,:]
            check(values)
            result[start:start+len(values),:] = values[:,columns]
        return result
    if _text(node.attrs.get('encoding-type','')) != 'csr_matrix':
        raise ValueError('only dense and CSR expression are supported by this adapter')
    ptr = _safe(node,'indptr')[:]
    idx = _safe(node,'indices'); data = _safe(node,'data')
    if ptr.ndim != 1 or ptr.dtype.kind not in 'iu' or len(ptr)!=n_rows+1 or ptr[0]!=0 or np.any(ptr[1:]<ptr[:-1]):
        raise ValueError('invalid CSR row pointers')
    if len(idx.shape)!=1 or len(data.shape)!=1 or ptr[-1]!=len(data) or len(idx)!=len(data):
        raise ValueError('CSR data length mismatch')
    for start in range(0,n_rows,256):
        end=min(start+256,n_rows); lo=int(ptr[start]); hi=int(ptr[end])
        if hi-lo > 12_000_000:
            raise ValueError('CSR chunk exceeds bound')
        inds=idx[lo:hi]; vals=data[lo:hi]; check(vals)
        if inds.dtype.kind not in 'iu' or np.any(inds>=n_cols) or np.any(inds<0):
            raise ValueError('invalid CSR column index')
        for row in range(start,end):
            a=int(ptr[row])-lo;b=int(ptr[row+1])-lo
            if b-a>1 and np.any(inds[a+1:b]<=inds[a:b-1]):
                raise ValueError('noncanonical/duplicate CSR indices require explicit preprocessing')
        row_ids=np.repeat(np.arange(start,end),np.diff(ptr[start:end+1]).astype(np.int64))
        for j,col in enumerate(columns):
            mask=(inds==col); result[row_ids[mask],j]=vals[mask]
    return result


def summarize(*, values, genes, samples, clusters, labels):
    """Describe measured cells; never pool captures or infer malignant identity."""
    if not genes or len(genes)!=len(set(genes)) or any(not isinstance(g,str) or not g for g in genes):
        raise ValueError('unique nonempty gene labels required')
    n=len(values)
    if n==0 or n>100_000 or any(len(x)!=n for x in (samples,clusters,labels)):
        raise ValueError('empty or mismatched cell metadata')
    if any(not isinstance(s,str) or not s.strip() for s in samples):
        raise ValueError('every cell needs explicit capture identity')
    groups=defaultdict(list)
    for i,row in enumerate(values):
        if len(row)!=len(genes):raise ValueError('gene width mismatch')
        numbers=[]
        for x in row:
            if isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<0:
                raise ValueError('finite nonnegative numeric expression required')
            numbers.append(float(x))
        label=labels[i] or None
        cluster=clusters[i] or None
        if (label is not None and not isinstance(label,str)) or (cluster is not None and not isinstance(cluster,str)):
            raise ValueError('source annotations must be text or missing')
        groups[(samples[i],cluster,label)].append(numbers)
    rows=[]
    for (sample,cluster,label),records in sorted(groups.items(),key=lambda item:tuple('' if x is None else x for x in item[0])):
        count=len(records);gs={}
        for j,g in enumerate(genes):
            measured=[row[j] for row in records]
            positive=sum(v>0 for v in measured)
            gs[g]={'positive_cells':positive,'fraction_positive':positive/count,'mean_stored_value':math.fsum(measured)/count}
        rows.append({'sample':sample,'cluster':cluster,'source_predicted_label':label,'n_cells':count,'genes':gs})
    return {'measurement':'nonnegative_stored_expression','counts_or_tpm_established':False,
            'malignancy_established':False,
            'n_cells':n,'sample_sizes':dict(sorted(Counter(samples).items())), 'groups':rows}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('redirect denied for fixed research asset')


def acquire(url,path,limit):
    """Historical adapter retained for code traceability; live patient file acquisition forbidden."""
    raise PermissionError('Sid patient dataset access is disabled: Open Intelligence studies public narratives and uses independent synthetic fixtures, not these records.')
    allowed={H5_URL,CATALOG_URL}
    if url not in allowed:raise ValueError('source outside declared scope')
    opener=urllib.request.build_opener(NoRedirect)
    total=0;digest=hashlib.sha256()
    with opener.open(urllib.request.Request(url,headers={'User-Agent':'Open-Intelligence-research/1'}),timeout=120) as response,Path(path).open('wb') as f:
        expected=response.headers.get('Content-Length')
        if expected and int(expected)>limit:raise ValueError('source exceeds byte cap')
        while True:
            block=response.read(8*1024*1024)
            if not block:break
            total+=len(block)
            if total>limit:raise ValueError('source exceeds byte cap')
            digest.update(block);f.write(block)
        if expected and int(expected)!=total:raise ValueError('incomplete source response')
    return {'url':url,'bytes':total,'sha256':digest.hexdigest(),'retrieved_at':datetime.now(timezone.utc).isoformat()}


def inspect_and_analyze(path):
    """Retired case-configured entrypoint; use the explicit synthetic helper."""
    raise PermissionError('Case-configured single-cell inspection is retired; use independently authored synthetic inputs with explicit configuration.')


def analyze_synthetic_h5ad(path, *, sample_dates, targets, controls, capture_types,
                          annotation_columns):
    """Describe a caller-authored fixture without case-derived defaults.

    All sample dates, selected features, capture types and annotation column pairs
    are explicit. No identity, patient count, clinical meaning or fixture origin
    is inferred from these caller declarations. Input provenance remains the
    caller's responsibility; this parser does not authorize real-patient inputs.
    """
    if (not isinstance(sample_dates, Mapping) or not sample_dates
            or any(not isinstance(sample, str) or not sample.strip()
                   or not isinstance(day, str) for sample, day in sample_dates.items())):
        raise ValueError('explicit sample identities and collection dates required')
    for day in sample_dates.values():
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('collection dates must use YYYY-MM-DD')
    if (not isinstance(capture_types, Mapping) or set(capture_types) != set(sample_dates)
            or any(not isinstance(kind, str) or not kind.strip() for kind in capture_types.values())):
        raise ValueError('every declared sample needs an explicit capture type')
    if (not isinstance(targets, (list, tuple)) or not targets
            or not isinstance(controls, (list, tuple))):
        raise ValueError('explicit target and control sequences required')
    selected = (*targets, *controls)
    if (any(not isinstance(gene, str) or not gene.strip() for gene in selected)
            or len(selected) != len(set(selected))):
        raise ValueError('target and control features must be unique nonempty symbols')
    if not isinstance(annotation_columns, Mapping) or not annotation_columns:
        raise ValueError('explicit annotation column pairs required')
    for resolution, columns in annotation_columns.items():
        if (not isinstance(resolution, str) or not resolution.strip()
                or not isinstance(columns, (list, tuple)) or len(columns) != 2
                or any(not isinstance(column, str) or not column
                       or '/' in column or column in ('.', '..') for column in columns)):
            raise ValueError('annotation configuration requires direct child column names')
    import h5py
    import numpy as np
    with h5py.File(path, 'r') as f:
        obs=_safe(f,'obs');var=_safe(f,'var')
        samples=read_column(obs,'sample_id');dates=read_column(obs,'date')
        ids=read_column(obs,_text(obs.attrs.get('_index','_index')))
        if (not samples or len(samples)!=len(dates) or len(ids)!=len(samples)
                or any(not isinstance(cell, str) or not cell.strip() for cell in ids)
                or len(ids)!=len(set(ids))):
            raise ValueError('cell identity/date alignment unresolved')
        if any(sample not in sample_dates or sample_dates[sample]!=day for sample,day in zip(samples,dates)):
            raise ValueError('sample/date outside the explicitly configured fixture scope')
        symbols=read_column(var,_text(var.attrs.get('_index','_index')))
        mapping=resolve_genes(var,selected)
        genes=[g for g,i in mapping.items() if i is not None]
        missing=[g for g,i in mapping.items() if i is None]
        if any(mapping[g] is None for g in targets):
            raise ValueError('a required target is not represented; do not report it as zero')
        n=len(samples);m=len(symbols);indices=[mapping[g] for g in genes]
        counts_node=_safe(_safe(f,'layers'),'counts')
        counts=read_selected_matrix(counts_node,indices,n,m,require_integer=True)
        normalized=read_selected_matrix(_safe(f,'X'),indices,n,m)
        mismatch=int(np.count_nonzero((counts>0)!=(normalized>0)))
        if mismatch:
            raise ValueError('count and processed X detection disagree for selected features')
        values=counts.tolist()
        resolutions={}
        for resolution, (cluster_column, label_column) in annotation_columns.items():
            clusters=read_column(obs,cluster_column)
            labels=read_column(obs,label_column)
            resolutions[resolution]=summarize(values=values,genes=genes,samples=samples,clusters=clusters,labels=labels)
        summary=summarize(values=values,genes=genes,samples=samples,clusters=['all']*n,labels=[None]*n)
        per_sample={g['sample']:g['genes'] for g in summary['groups']}
        counts_by_res={r:{gene:sum(group['genes'][gene]['positive_cells'] for group in item['groups']) for gene in genes}
                       for r,item in resolutions.items()}
        if len({json.dumps(v,sort_keys=True) for v in counts_by_res.values()}) != 1:
            raise ValueError('grouping changed source detection totals')
        return {
            'question':'How are explicitly selected fixture features distributed within separately declared captures?',
            'n_cells':n,'n_source_features':m,'patient_count':None,'capture_count':len(set(samples)),
            'sample_sizes':summary['sample_sizes'],'sample_collection_dates':{x:sample_dates[x] for x in sorted(set(samples))},
            'capture_types':{x:capture_types[x] for x in sorted(set(samples))},
            'separate_captures_preserved':True,
            'matrix_path':'/layers/counts','matrix_encoding':_text(counts_node.attrs.get('encoding-type','dense')),
            'measurement':'source_declared_counts_validated_nonnegative_integers',
            'umi_authenticity_independently_established':False,
            'genes_examined':genes,'genes_not_measured':missing,
            'count_vs_X_positive_disagreements':mismatch,'sample_target_summaries':per_sample,
            'source_annotation_resolutions':resolutions,'grouping_conservation_passed':True,
            'malignancy_established':False,'normal_tissue_specificity_established':False,
            'clinical_recommendation':None,'p_values':None,'historical_replay':False,
            'limitations':[
                'No patient count or population inference is established; cells are not independent patient replicates.',
                'Use source annotation labels as hypotheses, not independently adjudicated cell identities.',
                'Labels may use the same expression markers; localization is not independent validation of the labels.',
                'Caller-declared capture types are not independently validated or interchangeable tissue-composition samples.',
                'Positive count-layer entries mean detected in this processed assay; zero does not prove biological absence.',
                'Mean counts depend on sequencing depth and preparation; no between-time differential-expression or response inference.',
                'Only caller-selected annotation columns are examined; no new annotation model was trained or run.',
                'No normal reference, protein assay, copy-number or somatic-genotype corroboration was performed.'
            ]
        }


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();outpath=Path(args.output);outpath.parent.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            cat=Path(tmp)/'catalog.json';source=Path(tmp)/'source.h5ad'
            cat_receipt=acquire(CATALOG_URL,cat,4_000_000)
            from public_case_intake import build_manifest
            manifest=build_manifest(cat.read_bytes(),cat_receipt['retrieved_at'])
            if not any('kamil/tumor/analysis/' in json.dumps(row) for row in manifest['entries']):
                raise ValueError('fixed analyzed object catalog context unavailable')
            receipt=acquire(H5_URL,source,H5_LIMIT)
            if receipt['sha256'] != EXPECTED_H5_SHA256:
                raise ValueError('processed source revision changed; repeat source review')
            result=inspect_and_analyze(source)
            result.update(status='executed',analysis_executed=True,source_receipt=receipt,catalog_receipt=cat_receipt,
                          clinical_validation=False,learned_model_executed=False,
                          dependencies={x:importlib.metadata.version(x) for x in ('numpy','h5py')})
            outpath.write_text(json.dumps(result,indent=2,allow_nan=False))
            print(json.dumps({'status':'executed','cells':result['n_cells'],'source_sha256':receipt['sha256']}))
    except Exception as exc:
        outpath.write_text(json.dumps({'status':'failed','analysis_executed':False,'error_type':type(exc).__name__,'error':str(exc)[:300]},indent=2))
        raise

if __name__=='__main__':main()
