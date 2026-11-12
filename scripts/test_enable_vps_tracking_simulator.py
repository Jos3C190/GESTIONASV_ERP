import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('enable_simulator', ROOT / 'scripts/enable-vps-tracking-simulator.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class SimulatorActivationTests(unittest.TestCase):
    def test_existing_image_patch_is_idempotent_and_rejects_unknown_code(self):
        old = 'class Settings:\n' + helper.OLD_FIELD + '\n    @property\n    def simulator_enabled(self):\n' + helper.OLD_RULE + '\n'
        patched = helper.patch_settings(old)
        self.assertIn(helper.NEW_FIELD, patched)
        self.assertIn(helper.NEW_RULE, patched)
        self.assertEqual(helper.patch_settings(patched), patched)
        with self.assertRaises(ValueError):
            helper.patch_settings('class Settings: pass')

    def test_actual_settings_properties_for_every_flag_combination(self):
        # Execute the real property methods without importing unavailable DB/runtime dependencies.
        tree = ast.parse((ROOT / 'backend/app/core/config.py').read_text(encoding='utf-8'))
        settings = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Settings')
        methods = [n for n in settings.body if isinstance(n, ast.FunctionDef) and n.name in {'simulator_enabled', 'is_production'}]
        for method in methods:
            method.decorator_list = [ast.Name(id='property', ctx=ast.Load())]
        container = ast.ClassDef(name='Guard', bases=[], keywords=[], body=methods, decorator_list=[])
        module = ast.fix_missing_locations(ast.Module(body=[container], type_ignores=[]))
        namespace = {}
        exec(compile(module, '<actual-settings-properties>', 'exec'), namespace)
        for environment in ['development', 'test', 'staging', 'production']:
            for enabled in [False, True]:
                for allow in [False, True]:
                    with self.subTest(environment=environment, enabled=enabled, allow=allow):
                        s = namespace['Guard']()
                        s.ENVIRONMENT = environment
                        s.TRACKING_SIMULATOR_ENABLED = enabled
                        s.TRACKING_SIMULATOR_ALLOW_PRODUCTION = allow
                        self.assertEqual(s.simulator_enabled, enabled and (environment != 'production' or allow))
                        self.assertEqual(s.is_production, environment == 'production')
        defaults = {n.target.id: ast.literal_eval(n.value) for n in settings.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id.startswith('TRACKING_SIMULATOR_')}
        self.assertIs(defaults['TRACKING_SIMULATOR_ENABLED'], False)
        self.assertIs(defaults['TRACKING_SIMULATOR_ALLOW_PRODUCTION'], False)

    def test_remote_script_compiles(self):
        compile(helper.REMOTE, '<remote-activation>', 'exec')


if __name__ == '__main__':
    unittest.main()
