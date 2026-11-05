"""Offline RNA format and descriptive-statistics helpers for synthetic fixtures.

No patient endpoints, sample identifiers or data download workflow are included.
Calculations are engineering helpers, not qualified clinical interpretations.
"""
from __future__ import annotations
import gzip
import hashlib
import io
import math
if __package__:
    from .data_policy import deny_personal_data_use, disabled_cli
else:
    from data_policy import deny_personal_data_use, disabled_cli

MAX_EXPANDED = 16_000_000


def validate_key(sample: str, suffix: str) -> str:
    """Legacy remote-asset keys no longer authorize any retrieval."""
    deny_personal_data_use()


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


def fetch(url: str, limit: int) -> tuple[bytes, dict]:
    deny_personal_data_use()


def run() -> dict:
    deny_personal_data_use()


def main() -> None:
    disabled_cli()


if __name__ == '__main__':
    main()
