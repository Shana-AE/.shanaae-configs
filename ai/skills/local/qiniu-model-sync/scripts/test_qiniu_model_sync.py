"""Offline regression checks for model retention and safe config updates."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parent / 'qiniu_model_sync.py'
spec = importlib.util.spec_from_file_location('qiniu_sync', SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.policy = sync.load_policy()

    def test_retired_deepseek_never_returns(self):
        ids = {'deepseek-v3', 'deepseek/deepseek-v3.2-exp-thinking', 'deepseek-r1-0528', 'deepseek/deepseek-v4-pro'}
        self.assertEqual(sync.retained_models(ids, self.policy), {'deepseek/deepseek-v4-pro'})

    def test_window_separates_tiers_and_ignores_dates(self):
        ids = {'deepseek/deepseek-v4-pro-202606', 'deepseek/deepseek-v4.1-flash', 'deepseek/deepseek-v4.2-flash', 'deepseek/deepseek-v4.3-flash', 'unknown-special', 'gpt-oss-120b'}
        kept = sync.retained_models(ids, self.policy)
        self.assertNotIn('deepseek/deepseek-v4.1-flash', kept)
        self.assertEqual(kept, ids - {'deepseek/deepseek-v4.1-flash'})
        self.assertEqual(sync.model_series('claude-4.8-opus')[0], sync.model_series('anthropic/claude-opus-5.5')[0])

    def test_minimum_versions_remove_old_specialized_variants(self):
        old = {'openai/gpt-5.2-codex', 'openai/gpt-5.3-codex', 'openai/gpt-5.4-mini',
               'gemini-3.1-flash-image-preview', 'google/gemini-3-pro-image',
               'x-ai/grok-4.1-fast', 'x-ai/grok-4.2-fast-reasoning',
               'z-ai/glm-5.2', 'moonshotai/kimi-k2.6', 'claude-4.5-haiku'}
        current = {'openai/gpt-5.5', 'google/gemini-3.8-flash', 'x-ai/grok-4.7',
                   'z-ai/glm-5.3', 'moonshotai/kimi-k2.7-code', 'gpt-oss-120b'}
        self.assertEqual(sync.retained_models(old | current, self.policy), current)

    def test_pin_overrides_retirement(self):
        mid = 'deepseek-v3'
        self.assertEqual(sync.retained_models({mid}, {**self.policy, 'pin': [mid]}), {mid})

    def test_jsonc_preserves_string_contents(self):
        self.assertEqual(sync.parse_jsonc('{"url":"https://x/a,}", // comment\n"x":[1,],}'), {'url': 'https://x/a,}', 'x': [1]})

    def test_update_preserves_settings_and_is_idempotent(self):
        for key in ('provider', 'providers'):
            with self.subTest(schema=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.jsonc'
                path.write_text('{// retained comment\n"'+key+'":{"qiniu":{"models":{"deepseek-v3":{},"deepseek/deepseek-v4-pro":{"custom":42}}}},"outside":true}')
                catalog = {'deepseek/deepseek-v4-pro': {'id':'deepseek/deepseek-v4-pro'}, 'openai/gpt-6-sol': {'id':'openai/gpt-6-sol', 'reasoning': True, 'modalities': {'input':['text','image'], 'output':['text']}}}
                result, added, removed = sync.update_config(path, 'opencode', catalog, self.policy)
                data = sync.parse_jsonc(result)
                self.assertTrue(data['outside'])
                self.assertIn('// retained comment', result)
                self.assertEqual(data[key]['qiniu']['models']['deepseek/deepseek-v4-pro'], {'custom':42})
                self.assertEqual(removed, ['deepseek-v3'])
                self.assertEqual(added, ['openai/gpt-6-sol'])
                if key == 'providers':
                    self.assertEqual(data[key]['qiniu']['models']['openai/gpt-6-sol']['capabilities']['input'], ['text', 'image'])
                path.write_text(result)
                self.assertEqual(sync.update_config(path, 'opencode', catalog, self.policy), (result, [], []))

    def test_unresolved_route_aborts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'router.json'
            text = '{"Providers":[{"name":"qiniu","models":["deepseek-v3"]}],"Router":{"think":"qiniu,deepseek-v3"}}'
            path.write_text(text)
            with self.assertRaises(ValueError):
                sync.update_config(path, 'router', {}, self.policy)
            self.assertEqual(path.read_text(), text)

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "Hermes tests require PyYAML")
    def test_hermes_preserves_other_settings_and_updates_selection(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            text = '# keep this comment\nmodel:\n  provider: openai-codex\n  default: gpt-5.6-terra\ncustom_providers:\n  - name: qiniu\n    api_key: example-placeholder\n    models:\n      - deepseek-v3\n      - deepseek/deepseek-v4-pro\n  - name: other\n    model: keep-other\nauxiliary:\n  task:\n    provider: qiniu\n    model: deepseek-v3\n'
            path.write_text(text)
            catalog = {'deepseek/deepseek-v4-pro': {'id': 'deepseek/deepseek-v4-pro'}}
            policy = {**self.policy, 'route_replacements': {'deepseek-v3': 'deepseek/deepseek-v4-pro'}}
            result, added, removed = sync.update_config(path, 'hermes', catalog, policy)
            data = yaml.safe_load(result)
            self.assertIn('# keep this comment', result)
            self.assertIn('api_key: example-placeholder', result)
            self.assertEqual(data['model'], yaml.safe_load(text)['model'])
            self.assertEqual(data['custom_providers'][1], {'name': 'other', 'model': 'keep-other'})
            self.assertEqual(data['auxiliary']['task']['model'], 'deepseek/deepseek-v4-pro')
            self.assertEqual(removed, ['deepseek-v3'])
            self.assertEqual(added, [])
            path.write_text(result)
            self.assertEqual(sync.update_config(path, 'hermes', catalog, policy), (result, [], []))

    def test_empty_catalog_aborts_before_writing(self):
        with patch.object(sync, 'fetch_sufy', return_value=[]), patch.object(sync, 'update_config') as update:
            with self.assertRaises(ValueError):
                sync.cmd_update(SimpleNamespace(target='all', config=None, apply=True))
            update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
