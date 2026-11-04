"""Exact declared text class; invented permission records are not legal grants."""
import unittest
from open_intelligence.rights import RightsError, check_link_content, excerpt_mode, normalize_permissions, permitted


class TextContentRightsTests(unittest.TestCase):
    def grants(self, item, **overrides):
        return normalize_permissions({item:{'store':'allowed','display':'allowed',**overrides}})

    def test_each_declared_class_uses_only_its_own_store_and_display_permissions(self):
        for granted in ('full_text','abstract','api_output'):
            permissions=self.grants(granted)
            for selected in ('full_text','abstract','api_output'):
                with self.subTest(granted=granted,selected=selected):
                    if granted==selected:
                        self.assertEqual(check_link_content(permissions,content_item=selected,
                            citation_title=None,excerpt='Independently fictional text.'),'full')
                    else:
                        with self.assertRaises(RightsError):
                            check_link_content(permissions,content_item=selected,
                                citation_title=None,excerpt='Independently fictional text.')

    def test_legacy_default_is_full_text_and_does_not_borrow_api_or_abstract_rights(self):
        for item in ('api_output','abstract'):
            with self.subTest(item=item),self.assertRaises(RightsError):
                check_link_content(self.grants(item),citation_title=None,excerpt='Fictional text.')
        self.assertEqual(check_link_content(self.grants('full_text'),citation_title=None,
            excerpt='Fictional text.'),'full')

    def test_invalid_class_fails_even_for_metadata_only_or_revoked_requests(self):
        for value in (None,True,1,'','metadata','figures',['api_output'],{'item':'api_output'}):
            for revoked in (False,True):
                with self.subTest(value=value,revoked=revoked),self.assertRaises(RightsError):
                    check_link_content(self.grants('api_output'),content_item=value,
                        citation_title=None,excerpt=None,revoked=revoked)

    def test_title_model_use_and_redistribution_require_separate_permissions(self):
        permissions=self.grants('api_output')
        with self.assertRaises(RightsError):
            check_link_content(permissions,content_item='api_output',citation_title='Fictional title',
                excerpt='Independently fictional text.')
        self.assertFalse(permitted(permissions,'api_output','ml_use'))
        self.assertFalse(permitted(permissions,'api_output','redistribute'))
        self.assertFalse(permitted(permissions,'full_text','store'))
        self.assertEqual(excerpt_mode(permissions,content_item='api_output'),'full')

    def test_unknown_denied_revoked_and_superseded_content_fails_closed(self):
        for item in ('api_output','abstract','full_text'):
            for use in ('store','display'):
                for value in ('unknown','denied'):
                    with self.subTest(item=item,use=use,value=value),self.assertRaises(RightsError):
                        check_link_content(self.grants(item,**{use:value}),content_item=item,
                            citation_title=None,excerpt='Independently fictional text.')
            for state in ('revoked','superseded'):
                with self.subTest(item=item,state=state),self.assertRaises(RightsError):
                    check_link_content(self.grants(item),content_item=item,citation_title=None,
                        excerpt='Independently fictional text.',**{state:True})


if __name__=='__main__': unittest.main()
