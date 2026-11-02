"""Original fictional data. Expectations are independent of real-case values."""
import gzip
import unittest
from unittest.mock import patch
import rna_expression_probe as p


def gct(rows, sample='TEST', declared=None):
    n=len(rows) if declared is None else declared
    return ('#1.2\n%d\t1\nName\tDescription\t%s\n' % (n,sample) + ''.join('%s\t%s\t%s\n' % r for r in rows)).encode()

class ExpressionTests(unittest.TestCase):
    def test_preserves_gene_ids_symbols_and_values(self):
        m=p.parse_gct(gct([('ID.1','AAA','0'),('ID2.7','BBB','10')]),'TEST')
        self.assertEqual(m['genes']['ID.1'],{'symbol':'AAA','tpm':0.0})
        self.assertEqual(m['genes']['ID2.7']['tpm'],10)
    def test_reads_gzip(self):
        self.assertEqual(p.parse_gct(gzip.compress(gct([('I','A','3')])), 'TEST')['genes']['I']['tpm'],3)
    def test_rejects_wrong_sample(self):
        with self.assertRaises(ValueError): p.parse_gct(gct([('I','A','3')]),'OTHER')
    def test_rejects_wrong_dimensions(self):
        with self.assertRaises(ValueError): p.parse_gct(gct([('I','A','3')],declared=2),'TEST')
    def test_rejects_duplicate_gene_id(self):
        with self.assertRaises(ValueError): p.parse_gct(gct([('I','A','1'),('I','B','2')]),'TEST')
    def test_rejects_nonfinite_negative_and_missing(self):
        for v in ['NaN','inf','-1','','true','1e1000']:
            with self.subTest(v=v), self.assertRaises(ValueError): p.parse_gct(gct([('I','A',v)]),'TEST')
    def test_does_not_strip_gene_versions(self):
        m=p.parse_gct(gct([('I.1','A','1'),('I.2','A','2')]),'TEST')
        self.assertEqual(len(m['genes']),2)
    def test_missing_gene_not_negative(self):
        r=p.gene_summary(p.parse_gct(gct([('I','A','1')]),'TEST'),'MISSING')
        self.assertEqual(r['status'],'not_in_matrix'); self.assertIsNone(r['tpm'])
    def test_ambiguous_symbol_not_merged(self):
        r=p.gene_summary(p.parse_gct(gct([('I.1','A','1'),('I.2','A','2')]),'TEST'),'A')
        self.assertEqual(r['status'],'ambiguous_symbol'); self.assertIsNone(r['tpm'])
    def test_numeric_zero_not_biological_absence(self):
        r=p.gene_summary(p.parse_gct(gct([('I','A','0'),('J','B','10')]),'TEST'),'A')
        self.assertEqual(r['status'],'reported_zero'); self.assertEqual(r['tpm'],0)
        self.assertIsNone(r['positive_gene_percentile'])
    def test_positive_rank_and_ties(self):
        m=p.parse_gct(gct([('I','A','5'),('J','B','5'),('K','C','10'),('L','D','0')]),'TEST')
        r=p.gene_summary(m,'A')
        self.assertAlmostEqual(r['positive_gene_percentile'],100/3)
        self.assertEqual(r['rank_descending'],2)
        self.assertEqual(r['positive_gene_denominator'],3)
    def test_matrix_metrics_are_calculated(self):
        m=p.parse_gct(gct([('I','MT-CO1','3'),('J','A','1'),('K','B','0')]),'TEST')
        self.assertEqual(m['metrics']['gene_count'],3)
        self.assertEqual(m['metrics']['positive_gene_count'],2)
        self.assertAlmostEqual(m['metrics']['mitochondrial_symbol_tpm_fraction'],.75)
    def test_same_profile_has_unit_correlation(self):
        m=p.parse_gct(gct([('I','A','1'),('J','B','2'),('K','C','3')]),'TEST')
        r=p.compare_profiles(m,m)
        self.assertAlmostEqual(r['spearman'],1)
        self.assertEqual(r['matched_gene_ids'],3)
    def test_reversed_profile(self):
        a=p.parse_gct(gct([('I','A','1'),('J','B','2'),('K','C','3')]),'TEST')
        b=p.parse_gct(gct([('I','A','3'),('J','B','2'),('K','C','1')]),'TEST')
        self.assertAlmostEqual(p.compare_profiles(a,b)['spearman'],-1)
    def test_no_variation_no_correlation(self):
        m=p.parse_gct(gct([('I','A','1'),('J','B','1')]),'TEST')
        self.assertIsNone(p.compare_profiles(m,m)['spearman'])
    def test_mismatched_gene_symbols_excluded(self):
        a=p.parse_gct(gct([('I','A','1'),('J','B','2')]),'TEST')
        b=p.parse_gct(gct([('I','WRONG','3'),('J','B','2')]),'TEST')
        r=p.compare_profiles(a,b)
        self.assertEqual(r['symbol_disagreements'],1);self.assertEqual(r['matched_gene_ids'],1)
    def test_zeros_excluded_from_union_positive_rank(self):
        a=p.parse_gct(gct([('I','A','0'),('J','B','2'),('K','C','1')]),'TEST')
        b=p.parse_gct(gct([('I','A','0'),('J','B','4'),('K','C','2')]),'TEST')
        r=p.compare_profiles(a,b)
        self.assertEqual(r['ranked_gene_count'],2);self.assertAlmostEqual(r['spearman'],1)
    def test_missing_gene_counts_not_imputed(self):
        a=p.parse_gct(gct([('I','A','1'),('J','B','2')]),'TEST')
        b=p.parse_gct(gct([('I','A','1'),('K','C','3')]),'TEST')
        r=p.compare_profiles(a,b)
        self.assertEqual(r['left_only'],1);self.assertEqual(r['right_only'],1)
    def test_key_is_fixed_sample_and_suffix(self):
        with patch.object(p,'SAMPLES',('SYN-RNA-A',)):
            self.assertEqual(p.validate_key('SYN-RNA-A','.gene_tpm.gct.gz'),'rna-seq/reprocessed/SYN-RNA-A/SYN-RNA-A.gene_tpm.gct.gz')
            for s,suffix in [('../secret','.gene_tpm.gct.gz'),('SYN-RNA-OTHER','.gene_tpm.gct.gz'),('SYN-RNA-A','.bam')]:
                with self.subTest(s=s,suffix=suffix), self.assertRaises(ValueError):p.validate_key(s,suffix)
    def test_header_shape_must_match(self):
        for raw in [b'#1.3\n1\t1\nName\tDescription\tTEST\nI\tA\t1\n', b'#1.2\n1\t2\nName\tDescription\tTEST\nI\tA\t1\n', b'#1.2\n1\t1\nwrong\tDescription\tTEST\nI\tA\t1\n']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):p.parse_gct(raw,'TEST')
    def test_empty_identifier_rejected(self):
        with self.assertRaises(ValueError):p.parse_gct(gct([('','A','1')]),'TEST')
    def test_empty_matrix_rejected(self):
        with self.assertRaises(ValueError):p.parse_gct(gct([]),'TEST')
    def test_input_not_mutated(self):
        m=p.parse_gct(gct([('I','A','1'),('J','B','2')]),'TEST')
        import copy
        original=copy.deepcopy(m);p.gene_summary(m,'A');p.compare_profiles(m,m)
        self.assertEqual(original,m)

if __name__=='__main__': unittest.main()
