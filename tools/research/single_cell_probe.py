"""Offline matrix and aggregation helpers for independently authored fixtures.

No named-person endpoints, collection dates, file fingerprints or case-specific
analysis remain. Helpers preserve missingness, sample context and source labels;
these numerical checks do not establish malignancy or clinical validity.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import math
if __package__:
    from .data_policy import deny_personal_data_use, disabled_cli
else:
    from data_policy import deny_personal_data_use, disabled_cli


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


def acquire(url, path, limit):
    deny_personal_data_use()


def inspect_and_analyze(path):
    """Retired case-specific analysis cannot be used on cached local files."""
    deny_personal_data_use()


def main() -> None:
    disabled_cli()


if __name__ == '__main__':
    main()
