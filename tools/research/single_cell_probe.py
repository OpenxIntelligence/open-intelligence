"""Offline single-cell reducers for independently invented synthetic fixtures.

Personal-case acquisition and local analysis entrypoints are retired. The
fixture-only inspector requires explicit invented context and a fixture marker;
that declaration does not prove privacy or independent authorship. This is not
a clinical model, patient dataset loader or validated annotation system.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import tempfile
from datetime import datetime, timezone
import urllib.request

TARGETS = ('GENE_A', 'GENE_B', 'GENE_C', 'GENE_D')
CONTROLS = ('CONTROL_A',)
BASE = 'https://fixtures.example.invalid/'
H5_URL = BASE + 'independent-synthetic-fixture.h5ad'
CATALOG_URL = 'https://catalog.example.invalid/data/catalog/datasets.json'
H5_LIMIT = 2_000_000_000
EXPECTED_H5_SHA256 = None  # No personal-case asset is accepted.
SAMPLE_DATES = {'SYN-CAPTURE-A':'2001-01-01','SYN-CAPTURE-B':'2001-02-01'}


def _text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def _safe(parent, key):
    """Do not follow an HDF5 external or soft link supplied by an input file."""
    import h5py
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


def acquire(url, path, limit):
    """Retired personal-case entrypoint; reject before network or data access."""
    raise PermissionError('Personal-case acquisition and analysis are retired. Public narratives inform workflow research only; use independently authored synthetic fixtures. No manual opt-in exception.')


def inspect_and_analyze(path):
    """Retired personal-case entrypoint; reject before network or data access."""
    raise PermissionError('Personal-case acquisition and analysis are retired. Public narratives inform workflow research only; use independently authored synthetic fixtures. No manual opt-in exception.')



def inspect_synthetic_fixture(path, *, sample_dates, targets, controls):
    """Preserve generic count-layer checks on declared, invented fixtures only.

    This marker is a development contract, not proof of data provenance or consent.
    The retired personal-case runner must never call this helper.
    """
    if (not isinstance(sample_dates, dict) or not sample_dates or
            any(not isinstance(key, str) or not key.startswith('SYN-') for key in sample_dates)):
        raise ValueError('Only independently authored synthetic sample identifiers are supported')
    if (not isinstance(targets, tuple) or not targets or not isinstance(controls, tuple)
            or any(not isinstance(gene, str) or not gene.startswith(('GENE_', 'CONTROL_'))
                   for gene in (*targets, *controls))
            or len(set((*targets, *controls))) != len((*targets, *controls))):
        raise ValueError('Only unique synthetic feature labels are supported')
    import h5py
    import numpy as np
    with h5py.File(path, 'r') as f:
        if _text(f.attrs.get('oi_input_kind', '')) != 'original-synthetic-fixture':
            raise ValueError('Original synthetic fixture declaration is required')
        obs=_safe(f,'obs');var=_safe(f,'var')
        samples=read_column(obs,'sample_id');dates=read_column(obs,'date')
        ids=read_column(obs,_text(obs.attrs.get('_index','_index')))
        if not samples or len(samples)!=len(dates) or len(ids)!=len(samples) or len(ids)!=len(set(ids)):
            raise ValueError('cell identity/date alignment unresolved')
        if any(sample not in sample_dates or sample_dates[sample]!=day for sample,day in zip(samples,dates)):
            raise ValueError('sample/date outside the declared synthetic fixture context')
        symbols=read_column(var,_text(var.attrs.get('_index','_index')))
        mapping=resolve_genes(var,(*targets,*controls))
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
        for resolution in ('0.5','1.0','1.5'):
            clusters=read_column(obs,'leiden_res'+resolution)
            labels=read_column(obs,'celltype_res'+resolution)
            resolutions[resolution]=summarize(values=values,genes=genes,samples=samples,clusters=clusters,labels=labels)
        summary=summarize(values=values,genes=genes,samples=samples,clusters=['all']*n,labels=[None]*n)
        per_sample={g['sample']:g['genes'] for g in summary['groups']}
        counts_by_res={r:{gene:sum(group['genes'][gene]['positive_cells'] for group in item['groups']) for gene in genes}
                       for r,item in resolutions.items()}
        if len({json.dumps(v,sort_keys=True) for v in counts_by_res.values()}) != 1:
            raise ValueError('grouping changed source detection totals')
        return {
            'question':'Do declared synthetic count-layer fixtures preserve per-sample counts and annotations?',
            'n_cells':n,'n_source_features':m,'real_patient_data_permitted':False,'capture_count':len(set(samples)),
            'sample_sizes':summary['sample_sizes'],'sample_collection_dates':{x:sample_dates[x] for x in sorted(set(samples))},
            'input_kind':'original-synthetic-fixture','separate_captures_preserved':True,
            'matrix_path':'/layers/counts','matrix_encoding':_text(counts_node.attrs.get('encoding-type','dense')),
            'measurement':'source_declared_counts_validated_nonnegative_integers',
            'umi_authenticity_independently_established':False,
            'genes_examined':genes,'genes_not_measured':missing,
            'count_vs_X_positive_disagreements':mismatch,'sample_target_summaries':per_sample,
            'source_annotation_resolutions':resolutions,'grouping_conservation_passed':True,
            'malignancy_established':False,'normal_tissue_specificity_established':False,
            'clinical_recommendation':None,'p_values':None,'historical_replay':False,
            'limitations':[
                'Invented engineering fixtures only; no patient-specific result or external clinical inference.',
                'Use source annotation labels as hypotheses, not independently adjudicated cell identities.',
                'Labels may use the same expression markers; localization is not independent validation of the labels.',
                'Different declared capture preparations must remain separate.',
                'Positive count-layer entries mean detected in this processed assay; zero does not prove biological absence.',
                'Mean counts depend on sequencing depth and preparation; no between-time differential-expression or response inference.',
                'Three existing clustering resolutions are examined; no new annotation model was trained or run.',
                'No normal reference, protein assay, copy-number or somatic-genotype corroboration was performed.'
            ]
        }

def main():
    raise SystemExit("Retired personal-case runner. Use only independent synthetic parser unit tests.")

if __name__=='__main__':main()
