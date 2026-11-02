"""Original fictional fixtures; no patient cell records are embedded."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import single_cell_probe as p


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.values = [[0.0, 2.0], [4.0, 0.0], [2.0, 3.0], [8.0, 0.0]]
        self.samples = ['whole', 'whole', 'whole', 'enriched']
        self.clusters = ['0', '0', '1', '0']
        self.labels = ['source-type-A', 'source-type-A', None, 'source-type-A']

    def run_summary(self, **kw):
        args = dict(values=self.values, genes=['GENE_A', 'GENE_B'], samples=self.samples,
                    clusters=self.clusters, labels=self.labels)
        args.update(kw)
        return p.summarize(**args)

    def test_enriched_capture_never_pooled_with_whole_sample(self):
        out = self.run_summary()
        groups = out['groups']
        a = [x for x in groups if x['sample']=='whole' and x['cluster']=='0'][0]
        b = [x for x in groups if x['sample']=='enriched'][0]
        self.assertEqual((a['n_cells'], b['n_cells']), (2, 1))
        self.assertEqual(a['genes']['GENE_A']['positive_cells'], 1)
        self.assertEqual(b['genes']['GENE_A']['positive_cells'], 1)

    def test_descriptive_statistics_have_hand_checked_denominators(self):
        a = self.run_summary()['groups'][0]
        self.assertEqual(a['sample'], 'enriched')
        row = [g for g in self.run_summary()['groups'] if g['sample']=='whole' and g['cluster']=='0'][0]
        self.assertEqual(row['genes']['GENE_A'], {'positive_cells':1,'fraction_positive':0.5,'mean_stored_value':2.0})
        self.assertEqual(row['genes']['GENE_B']['mean_stored_value'], 1.0)
        self.assertEqual(self.run_summary()['sample_sizes'], {'enriched':1, 'whole':3})

    def test_missing_cell_annotation_stays_unassigned(self):
        rows = self.run_summary()['groups']
        row = [g for g in rows if g['cluster']=='1'][0]
        self.assertIsNone(row['source_predicted_label'])
        self.assertEqual(row['n_cells'], 1)

    def test_same_label_different_clusters_not_silently_collapsed(self):
        out = self.run_summary(labels=['same']*4)
        self.assertEqual(len(out['groups']), 3)

    def test_cell_metadata_length_mismatch_is_rejected(self):
        with self.assertRaises(ValueError): self.run_summary(samples=['whole'])

    def test_missing_sample_identity_is_rejected(self):
        with self.assertRaises(ValueError): self.run_summary(samples=[None]*4)

    def test_expression_width_mismatch_is_rejected(self):
        with self.assertRaises(ValueError): self.run_summary(values=[[1.0]]*4)

    def test_negative_nonfinite_and_boolean_values_not_detection(self):
        for bad in (-1, float('nan'), float('inf'), True):
            values=copy.deepcopy(self.values); values[1][0]=bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.run_summary(values=values)

    def test_fractional_normalized_values_remain_stored_scale(self):
        out=self.run_summary(values=[[0.0,0.25],[0.5,0.0],[1.25,1.0],[0.1,0.0]])
        self.assertEqual(out['measurement'], 'nonnegative_stored_expression')
        self.assertFalse(out['counts_or_tpm_established'])
        self.assertFalse(out['malignancy_established'])

    def test_empty_or_duplicate_gene_names_are_rejected(self):
        for genes in ([], ['GENE_A','GENE_A'], ['GENE_A','']):
            with self.subTest(genes=genes), self.assertRaises(ValueError): self.run_summary(genes=genes)

    def test_empty_cells_are_not_a_negative_result(self):
        with self.assertRaises(ValueError):
            self.run_summary(values=[],samples=[],clusters=[],labels=[])

    def test_aggregate_outputs_do_not_contain_per_cell_records(self):
        before=copy.deepcopy(self.values)
        out=self.run_summary()
        self.assertEqual(self.values,before)
        self.assertNotIn('values',out)
        self.assertNotIn('barcodes',out)
        self.assertEqual(sum(x['n_cells'] for x in out['groups']),4)
        json.dumps(out,allow_nan=False)


H5_AVAILABLE = importlib.util.find_spec('h5py') is not None and importlib.util.find_spec('numpy') is not None

@unittest.skipUnless(H5_AVAILABLE, 'isolated HDF5 research dependencies absent; scientific job runs these tests')
class H5Tests(unittest.TestCase):
    def setUp(self):
        import h5py
        import numpy as np
        self.h5py,self.np=h5py,np
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'fixture.h5ad'
        self.f=h5py.File(self.path,'w')
        self.obs=self.f.create_group('obs')

    def tearDown(self):
        self.f.close(); self.tmp.cleanup()

    def cat(self, key, codes=(0,1,-1), categories=('A','B')):
        x=self.obs.create_group(key);x.attrs['encoding-type']='categorical'
        x.create_dataset('codes',data=codes)
        x.create_dataset('categories',data=list(categories),dtype=self.h5py.string_dtype())
        return x

    def csr(self, key='X', indices=(1,0,1,2), ptr=(0,1,3,4), data=(2.0,3.0,4.0,5.0)):
        x=self.f.create_group(key); x.attrs['encoding-type']='csr_matrix';x.attrs['shape']=[3,3]
        x.create_dataset('data',data=data);x.create_dataset('indices',data=indices);x.create_dataset('indptr',data=ptr)
        return x

    def test_missing_category_minus_one_not_last_label(self):
        self.cat('annotation')
        self.assertEqual(p.read_column(self.obs,'annotation'),['A','B',None])

    def test_bad_category_code_is_rejected(self):
        for code in (-2,2):
            self.cat(str(code),codes=(code,))
            with self.subTest(code=code),self.assertRaises(ValueError): p.read_column(self.obs,str(code))

    def test_plain_string_column_decoded(self):
        self.obs.create_dataset('sample',data=['SYN-A','SYN-B'],dtype=self.h5py.string_dtype())
        self.assertEqual(p.read_column(self.obs,'sample'),['SYN-A','SYN-B'])

    def test_external_links_are_rejected_before_dereference(self):
        self.obs['remote']=self.h5py.ExternalLink('/unavailable/not_allowed.h5','/secret')
        with self.assertRaises(ValueError):p.read_column(self.obs,'remote')

    def test_dense_selected_columns_preserve_requested_order(self):
        x=self.f.create_dataset('X',data=[[0.,2.,0.],[3.,4.,0.],[0.,0.,5.]])
        actual=p.read_selected_matrix(x,[2,0],3,3)
        self.np.testing.assert_array_equal(actual,[[0,0],[0,3],[5,0]])

    def test_csr_sparse_zeros_and_order_match_dense(self):
        actual=p.read_selected_matrix(self.csr(),[2,0],3,3)
        self.np.testing.assert_array_equal(actual,[[0,0],[0,3],[5,0]])

    def test_csr_invalid_pointer_or_column_is_rejected(self):
        for key,indices,ptr in [('a',(3,0,1,2),(0,1,3,4)),('b',(1,0,1,2),(1,1,3,4)),('c',(1,0,1,2),(0,3,2,4))]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.read_selected_matrix(self.csr(key,indices,ptr),[0],3,3)

    def test_duplicate_sparse_entry_is_not_summed_silently(self):
        x=self.csr(indices=(1,0,0,2))
        with self.assertRaises(ValueError):p.read_selected_matrix(x,[0],3,3)

    def test_matrix_shape_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):p.read_selected_matrix(self.csr(),[0],4,3)

    def test_negative_matrix_values_cannot_be_called_absence(self):
        with self.assertRaises(ValueError):p.read_selected_matrix(self.csr(data=(2.,-3.,4.,5.)),[0],3,3)

    def test_gene_mapping_missing_differs_from_measured_zero(self):
        var=self.f.create_group('var');var.attrs['_index']='gene'
        var.create_dataset('gene',data=['GENE_A','GENE_B'],dtype=self.h5py.string_dtype())
        mapping=p.resolve_genes(var,['GENE_B','ABSENT'])
        self.assertEqual(mapping, {'GENE_B':1,'ABSENT':None})

    def test_duplicate_gene_symbols_are_not_merged(self):
        var=self.f.create_group('var');var.attrs['_index']='gene'
        var.create_dataset('gene',data=['GENE_A','GENE_A'],dtype=self.h5py.string_dtype())
        with self.assertRaises(ValueError):p.resolve_genes(var,['GENE_A'])

    def test_declared_count_layer_rejects_fractional_values(self):
        x=self.csr(data=(2.,0.5,4.,5.))
        with self.assertRaises(ValueError):p.read_selected_matrix(x,[0],3,3,require_integer=True)

    def full_fixture(self):
        self.f.attrs['oi_input_kind']='original-synthetic-fixture'
        self.obs.create_dataset('_index',data=['CELL-SYN-1','CELL-SYN-2','CELL-SYN-3'],dtype=self.h5py.string_dtype())
        for name,values in [('sample_id',['SYN-CAPTURE-A','SYN-CAPTURE-A','SYN-CAPTURE-B']),('date',['2001-01-01','2001-01-01','2001-02-01'])]:
            self.obs.create_dataset(name,data=values,dtype=self.h5py.string_dtype())
        for res in ('0.5','1.0','1.5'):
            self.obs.create_dataset('leiden_res'+res,data=['0','1','0'],dtype=self.h5py.string_dtype())
            self.obs.create_dataset('celltype_res'+res,data=['hypothesis-A','hypothesis-B','hypothesis-A'],dtype=self.h5py.string_dtype())
        var=self.f.create_group('var');var.attrs['_index']='_index'
        var.create_dataset('_index',data=['GENE_A','GENE_B','GENE_C','GENE_D'],dtype=self.h5py.string_dtype())
        counts=self.np.array([[0.,2.,1.,0.],[3.,0.,2.,0.],[0.,0.,0.,0.]])
        self.f.create_group('layers').create_dataset('counts',data=counts)
        self.f.create_dataset('X',data=self.np.log1p(counts))
        self.f.flush()

    def test_end_to_end_aggregates_with_no_cell_ids_published(self):
        self.full_fixture();out=p.inspect_synthetic_fixture(self.path, sample_dates={'SYN-CAPTURE-A':'2001-01-01','SYN-CAPTURE-B':'2001-02-01'}, targets=('GENE_A','GENE_B','GENE_C','GENE_D'), controls=('CONTROL_A',))
        self.assertEqual(out['n_cells'],3)
        self.assertEqual(out['sample_sizes'],{'SYN-CAPTURE-A':2,'SYN-CAPTURE-B':1})
        self.assertEqual(out['count_vs_X_positive_disagreements'],0)
        self.assertIn('CONTROL_A',out['genes_not_measured'])
        self.assertEqual(out['sample_target_summaries']['SYN-CAPTURE-A']['GENE_C']['positive_cells'],2)
        self.assertEqual(out['sample_target_summaries']['SYN-CAPTURE-B']['GENE_A']['positive_cells'],0)
        self.assertNotIn('CELL-SYN-1',json.dumps(out))
        self.assertFalse(out['malignancy_established'])

    def test_missing_counts_layer_does_not_fall_back_to_scaled_X(self):
        self.full_fixture();del self.f['layers/counts'];self.f.flush()
        with self.assertRaises(ValueError):p.inspect_synthetic_fixture(self.path, sample_dates={'SYN-CAPTURE-A':'2001-01-01','SYN-CAPTURE-B':'2001-02-01'}, targets=('GENE_A','GENE_B','GENE_C','GENE_D'), controls=('CONTROL_A',))

    def test_unexpected_sample_cannot_be_pooled_as_another_timepoint(self):
        self.full_fixture();self.obs['sample_id'][0]='UNEXPECTED-DONOR';self.f.flush()
        with self.assertRaises(ValueError):p.inspect_synthetic_fixture(self.path, sample_dates={'SYN-CAPTURE-A':'2001-01-01','SYN-CAPTURE-B':'2001-02-01'}, targets=('GENE_A','GENE_B','GENE_C','GENE_D'), controls=('CONTROL_A',))

    def test_wrong_sample_date_requires_resolution(self):
        self.full_fixture();self.obs['date'][0]='2001-02-01';self.f.flush()
        with self.assertRaises(ValueError):p.inspect_synthetic_fixture(self.path, sample_dates={'SYN-CAPTURE-A':'2001-01-01','SYN-CAPTURE-B':'2001-02-01'}, targets=('GENE_A','GENE_B','GENE_C','GENE_D'), controls=('CONTROL_A',))

    def test_duplicate_cell_identity_requires_resolution(self):
        self.full_fixture();self.obs['_index'][1]='CELL-SYN-1';self.f.flush()
        with self.assertRaises(ValueError):p.inspect_synthetic_fixture(self.path, sample_dates={'SYN-CAPTURE-A':'2001-01-01','SYN-CAPTURE-B':'2001-02-01'}, targets=('GENE_A','GENE_B','GENE_C','GENE_D'), controls=('CONTROL_A',))

    def test_missing_synthetic_declaration_is_rejected(self):
        self.full_fixture();del self.f.attrs['oi_input_kind'];self.f.flush()
        with self.assertRaises(ValueError):
            p.inspect_synthetic_fixture(self.path, sample_dates={'SYN-CAPTURE-A':'2001-01-01'}, targets=('GENE_A',), controls=())

    def test_non_synthetic_context_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            p.inspect_synthetic_fixture(self.path, sample_dates={'ACTUAL-SUBJECT':'2001-01-01'}, targets=('GENE_A',), controls=())

if __name__=='__main__':unittest.main()
