import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('repair', Path(__file__).with_name('repair-vps-maps.py'))
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class RepairTests(unittest.TestCase):
    def test_patch_is_valid_and_idempotent(self):
        source = 'def build():\n  ' + repair.BUILD_BEFORE + '\n'
        result = repair.patch_builder(source)
        self.assertIn(repair.BUILD_AFTER, result)
        self.assertEqual(repair.patch_builder(result), result)

    def test_unexpected_or_ambiguous_builder_is_rejected(self):
        for source in ['pass', repair.BUILD_BEFORE + '\n' + repair.BUILD_BEFORE]:
            with self.assertRaises(ValueError):
                repair.patch_builder(source)

    def test_key_parsing_and_missing_key(self):
        path = Mock()
        for value in ['example-key', '"example-key"', "'example-key'"]:
            path.read_text.return_value = 'PUBLIC_CARTO_BASEMAP_API_KEY=' + value
            self.assertEqual(repair.read_carto_key(path), 'example-key')
        path.read_text.return_value = 'PUBLIC_CARTO_BASEMAP_API_KEY=  '
        with self.assertRaises(ValueError):
            repair.read_carto_key(path)

    def test_remote_script_compiles(self):
        compile(repair.REMOTE, '<remote>', 'exec')


if __name__ == '__main__':
    unittest.main()
