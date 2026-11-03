"""Actual existing PG image custody with an optional remote original replica.

No second image/source store or real data. The archive is a controlled test
double; this suite does not establish live PACS or network-isolation behavior.
"""
import unittest
from unittest.mock import Mock, patch

from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B
from test_image_custody import ImageCustodyHTTPTests, image_bytes, image_request, AMENDED


class PrivateImageReads(ImageCustodyHTTPTests):
    def test_current_original_uses_canonical_mapping_and_receipt(self):
        archive = Mock()
        raw = image_bytes()
        archive.read.return_value = raw
        with running_server(create_app(self.settings, image_archive=archive)) as base:
            patient, source, path = self.prepare(base)
            image = image_request(base, path, raw=raw)[1]['image_id']
            archive.read.assert_not_called()
            self.assertEqual(image_request(base, path+'/'+image, token=TOKEN_B)[0], 404)
            archive.read.assert_not_called()
            code, data, headers = image_request(base, path+'/'+image)
            self.assertEqual((code,data),(200,raw))
            self.assertTrue(headers['X-OI-Access-Receipt'])
            archive.read.assert_called_once_with('2.25.101','2.25.102','2.25.103')
        self.assertEqual(len(self.events("AND event_type='image.original_read_authorized'")),1)

    def test_remote_error_changed_or_nonbytes_result_never_falls_back_to_pg(self):
        archive=Mock();raw=image_bytes()
        with running_server(create_app(self.settings,image_archive=archive)) as base:
            patient,source,path=self.prepare(base)
            image=image_request(base,path,raw=raw)[1]['image_id']
            for bad in (raw+b'changed',bytearray(raw),None):
                archive.read.return_value=bad
                self.assertEqual(image_request(base,path+'/'+image)[:2],
                                 (503,{'detail':'Patient registry unavailable'}))
            archive.read.side_effect=RuntimeError('PRIVATE_UPSTREAM_DETAIL')
            self.assertEqual(image_request(base,path+'/'+image)[:2],
                             (503,{'detail':'Patient registry unavailable'}))
        self.assertEqual(self.events("AND event_type='image.original_read_authorized'"),[])

    def test_source_correction_during_fetch_is_denied_without_locking_out_writer(self):
        archive=Mock();raw=image_bytes()
        with running_server(create_app(self.settings,image_archive=archive)) as base:
            patient,source,path=self.prepare(base)
            image=image_request(base,path,raw=raw)[1]['image_id']
            def fetch(*ids):
                # Separate HTTP transaction must succeed while archive read is
                # in flight; the read must then detect the source amendment.
                self.assertEqual(self.ingest(base,patient,AMENDED)[0],201)
                return raw
            archive.read.side_effect=fetch
            self.assertEqual(image_request(base,path+'/'+image)[0],404)
            archive.read.reset_mock()
            self.assertEqual(image_request(base,path+'/'+image)[0],404)
            archive.read.assert_not_called()
        self.assertEqual(self.events("AND event_type='image.original_read_authorized'"),[])

    def test_late_grant_or_actor_change_withholds_remote_bytes(self):
        archive=Mock();raw=image_bytes()
        with running_server(create_app(self.settings,image_archive=archive)) as base:
            patient,source,path=self.prepare(base)
            image=image_request(base,path,raw=raw)[1]['image_id']
            original_actor=self.creds[0]['actor']
            def revoke(*ids):
                self.creds[0]['actions'].remove('image_original_read');self.write()
                return raw
            archive.read.side_effect=revoke
            self.assertEqual(image_request(base,path+'/'+image)[0],404)
            self.creds[0]['actions'].append('image_original_read');self.write()
            def change_actor(*ids):
                self.creds[0]['actor']='ACTOR-CHANGED';self.write();return raw
            archive.read.side_effect=change_actor
            self.assertEqual(image_request(base,path+'/'+image)[0],404)
            self.creds[0]['actor']=original_actor;self.write()
        self.assertEqual(self.events("AND event_type='image.original_read_authorized'"),[])

    def test_receipt_commit_failure_withholds_successful_remote_original(self):
        archive=Mock();raw=image_bytes();archive.read.return_value=raw
        with running_server(create_app(self.settings,image_archive=archive)) as base:
            patient,source,path=self.prepare(base)
            image=image_request(base,path,raw=raw)[1]['image_id']
            with patch.object(PostgresPatientRegistry,'append_event',side_effect=RuntimeError('no journal')):
                self.assertEqual(image_request(base,path+'/'+image)[0],503)
            archive.read.assert_called_once()
        self.assertEqual(self.events("AND event_type='image.original_read_authorized'"),[])


def load_tests(loader, tests, pattern):
    # Only the five new cases; the inherited owner suite runs in its own module.
    return unittest.TestSuite(PrivateImageReads(name) for name in PrivateImageReads.__dict__
                              if name.startswith('test_'))
