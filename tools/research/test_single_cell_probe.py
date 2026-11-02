"""Hand-authored fixture arithmetic, independent of archived case configuration.

The full HDF5 example uses five invented cells, four invented feature symbols,
two arbitrary 2001 dates and explicit capture/annotation configuration. Its
literal counts and expected aggregates were authored together for these tests.
"""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
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

    def test_case_configured_inspection_is_retired_before_file_access(self):
        with patch('builtins.open', side_effect=AssertionError('File access forbidden')) as opener:
            with self.assertRaises(PermissionError):
                p.inspect_and_analyze('/never-opened/case.h5ad')
            opener.assert_not_called()


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

    def test_nested_link_path_is_rejected_before_traversal(self):
        self.obs['remote']=self.h5py.ExternalLink('/unavailable/not_allowed.h5','/secret')
        with self.assertRaisesRegex(ValueError, 'direct child'):
            p.read_column(self.obs,'remote/column')

    def test_soft_links_and_external_storage_are_rejected(self):
        self.obs.create_dataset('local',data=['SYN'],dtype=self.h5py.string_dtype())
        self.obs['alias']=self.h5py.SoftLink('/obs/local')
        with self.assertRaises(ValueError):p.read_column(self.obs,'alias')
        self.obs.create_dataset('external_storage',shape=(1,),dtype='i',
                                external=[('/unavailable/not_allowed.bin',0,4)])
        with self.assertRaises(ValueError):p.read_column(self.obs,'external_storage')

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
        self.obs.create_dataset('_index',data=['SYN-CELL-A1','SYN-CELL-A2','SYN-CELL-A3','SYN-CELL-B1','SYN-CELL-B2'],dtype=self.h5py.string_dtype())
        for name,values in [('sample_id',['SYN-SAMPLE-A']*3+['SYN-SAMPLE-B']*2),
                            ('date',['2001-02-03']*3+['2001-03-04']*2)]:
            self.obs.create_dataset(name,data=values,dtype=self.h5py.string_dtype())
        for name,values in [('cluster_coarse',['red','red','blue','red','blue']),
                            ('cluster_fine',['a','b','c','a','b'])]:
            self.obs.create_dataset(name,data=values,dtype=self.h5py.string_dtype())
        for name in ('label_coarse','label_fine'):
            self.cat(name,codes=(0,0,-1,0,1),categories=('fixture-type-X','fixture-type-Y'))
        var=self.f.create_group('var');var.attrs['_index']='_index'
        var.create_dataset('_index',data=['GENE_A','GENE_B','GENE_C','GENE_ZERO'],dtype=self.h5py.string_dtype())
        # By hand: A has sums (6,9,6,0), B has sums (8,0,8,0).
        # Detection counts are A=(2,2,2,0), B=(1,0,2,0).
        counts=self.np.array([[1,0,4,0],[0,3,0,0],[5,6,2,0],[0,0,7,0],[8,0,1,0]])
        self.f.create_group('layers').create_dataset('counts',data=counts)
        self.f.create_dataset('X',data=self.np.log1p(counts))
        self.f.flush()

    def analyze(self, **overrides):
        config = dict(sample_dates={'SYN-SAMPLE-A':'2001-02-03','SYN-SAMPLE-B':'2001-03-04'},
                      targets=('GENE_A','GENE_B','GENE_ZERO'),
                      controls=('GENE_C','GENE_MISSING'),
                      capture_types={'SYN-SAMPLE-A':'fixture-capture-left','SYN-SAMPLE-B':'fixture-capture-right'},
                      annotation_columns={'coarse':('cluster_coarse','label_coarse'),
                                          'fine':('cluster_fine','label_fine')})
        config.update(overrides)
        return p.analyze_synthetic_h5ad(self.path, **config)

    def test_end_to_end_aggregates_with_no_cell_ids_published(self):
        self.full_fixture();out=self.analyze()
        self.assertEqual(out['n_cells'],5)
        self.assertEqual(out['sample_sizes'],{'SYN-SAMPLE-A':3,'SYN-SAMPLE-B':2})
        self.assertEqual(out['sample_collection_dates'],{'SYN-SAMPLE-A':'2001-02-03','SYN-SAMPLE-B':'2001-03-04'})
        self.assertEqual(out['capture_types'],{'SYN-SAMPLE-A':'fixture-capture-left','SYN-SAMPLE-B':'fixture-capture-right'})
        self.assertEqual(out['count_vs_X_positive_disagreements'],0)
        self.assertEqual(out['genes_not_measured'],['GENE_MISSING'])
        expected = {
            'SYN-SAMPLE-A':{'GENE_A':(2,2/3,2),'GENE_B':(2,2/3,3),'GENE_C':(2,2/3,2),'GENE_ZERO':(0,0,0)},
            'SYN-SAMPLE-B':{'GENE_A':(1,0.5,4),'GENE_B':(0,0,0),'GENE_C':(2,1,4),'GENE_ZERO':(0,0,0)}}
        for sample, features in expected.items():
            for gene, (positive, fraction, mean) in features.items():
                self.assertEqual(out['sample_target_summaries'][sample][gene],
                                 {'positive_cells':positive,'fraction_positive':fraction,'mean_stored_value':mean})
        self.assertNotIn('SYN-CELL-',json.dumps(out))
        self.assertIsNone(out['patient_count'])
        self.assertFalse(out['malignancy_established'])
        self.assertFalse(out['normal_tissue_specificity_established'])
        self.assertIsNone(out['clinical_recommendation'])
        self.assertIsNone(out['p_values'])
        coarse=out['source_annotation_resolutions']['coarse']['groups']
        self.assertTrue(any(row['source_predicted_label'] is None for row in coarse))

    def test_generic_analysis_does_not_depend_on_archival_case_globals(self):
        self.full_fixture()
        with patch.object(p,'SAMPLE_DATES',{}), patch.object(p,'TARGETS',()), patch.object(p,'CONTROLS',()):
            self.assertEqual(self.analyze()['sample_sizes'],{'SYN-SAMPLE-A':3,'SYN-SAMPLE-B':2})

    def test_configuration_is_required_and_validated(self):
        self.full_fixture()
        with self.assertRaises(TypeError):p.analyze_synthetic_h5ad(self.path)
        for config in (dict(sample_dates={}), dict(sample_dates={'SYN-SAMPLE-A':'2001-02-30'}),
                       dict(targets=()), dict(controls=('GENE_A',)), dict(capture_types={}),
                       dict(annotation_columns={}),
                       dict(annotation_columns={'bad':('outside/cluster','label_coarse')})):
            with self.subTest(config=config),self.assertRaises(ValueError):self.analyze(**config)

    def test_count_and_X_detection_disagreement_is_rejected(self):
        self.full_fixture();self.f['X'][0,0]=0;self.f.flush()
        with self.assertRaisesRegex(ValueError,'detection disagree'):self.analyze()

    def test_missing_required_feature_is_not_reported_as_zero(self):
        self.full_fixture()
        with self.assertRaisesRegex(ValueError,'required target'):
            self.analyze(targets=('GENE_ABSENT',))

    def test_missing_counts_layer_does_not_fall_back_to_scaled_X(self):
        self.full_fixture();del self.f['layers/counts'];self.f.flush()
        with self.assertRaises(ValueError):self.analyze()

    def test_unexpected_sample_cannot_be_pooled_as_another_timepoint(self):
        self.full_fixture();self.obs['sample_id'][0]='UNEXPECTED-DONOR';self.f.flush()
        with self.assertRaises(ValueError):self.analyze()

    def test_wrong_sample_date_requires_resolution(self):
        self.full_fixture();self.obs['date'][0]='2001-03-04';self.f.flush()
        with self.assertRaises(ValueError):self.analyze()

    def test_duplicate_cell_identity_requires_resolution(self):
        self.full_fixture();self.obs['_index'][1]='SYN-CELL-A1';self.f.flush()
        with self.assertRaises(ValueError):self.analyze()

if __name__=='__main__':unittest.main()
