"""Real composition advertises the bounded asynchronous execution controls."""
import unittest
from oi_api.app import create_app


class ComposerRunRouteTests(unittest.TestCase):
    def test_existing_brief_and_all_execution_controls_have_response_contracts(self):
        schema = create_app().openapi()
        base = '/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}'
        for suffix, method, expected in (
                ('/brief', 'post', 'SourceQuestionBrief'),
                ('/runs', 'post', 'ComposerRunReceipt'),
                ('/runs/{run_id}', 'get', 'ComposerRunStatus'),
                ('/runs/{run_id}/cancel', 'post', 'ComposerRunStatus'),
                ('/runs/{run_id}/result', 'get', 'ComposerRunResult')):
            with self.subTest(suffix=suffix):
                self.assertTrue(base + suffix in schema['paths'], 'Missing execution path: ' + base + suffix)
                responses = schema['paths'][base + suffix][method]['responses']
                successful = [body for status, body in responses.items() if status.startswith('2')]
                self.assertTrue(any(body.get('content', {}).get('application/json', {}).get('schema', {}).get('$ref')
                                    == '#/components/schemas/' + expected for body in successful))
