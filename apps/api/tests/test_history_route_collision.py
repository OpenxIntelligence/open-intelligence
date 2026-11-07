"""Static API routing contract regression that runs without PostgreSQL or clinical wheels."""
import ast
import unittest
from pathlib import Path

PATIENTS = Path(__file__).resolve().parents[1] / 'src' / 'oi_api' / 'patients.py'


class HistoryRouteCollisionTests(unittest.TestCase):
    def test_history_models_and_routes_have_independent_owners(self):
        tree = ast.parse(PATIENTS.read_text(encoding='utf-8'))
        models = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        self.assertEqual(models.count('SourceHistory'), 1)
        self.assertEqual(models.count('SourceMembershipHistory'), 1)
        routes = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == 'get' and decorator.args):
                    continue
                if not isinstance(decorator.args[0], ast.Constant):
                    continue
                path = decorator.args[0].value
                if not isinstance(path, str) or not (path.endswith('/source-history') or path.endswith('/world-model/history')):
                    continue
                keywords = {kw.arg: kw.value for kw in decorator.keywords}
                operation_id = ast.literal_eval(keywords['operation_id'])
                response_model = keywords['response_model'].id
                routes[path] = (node.name, operation_id, response_model)
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes['/{patient_id}/cases/{case_id}/source-history'],
                         ('source_membership_history', 'read_source_membership_history_v1', 'SourceMembershipHistory'))
        self.assertEqual(routes['/{patient_id}/cases/{case_id}/world-model/history'],
                         ('source_history', 'read_source_history_v1', 'SourceHistory'))
        self.assertEqual(len(set(value[1] for value in routes.values())), 2)


if __name__ == '__main__':
    unittest.main()
