import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('oas', Path(__file__).parents[1] / 'scripts/oas.py')
oas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oas)


class OASTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def task(self):
        return oas.new_task('development', self.root, 'Fix it', ['Regression passes']) / 'task.json'

    def test_merge_preserves_siblings_and_inputs(self):
        base = {'a': {'x': 1, 'y': 2}}
        self.assertEqual(oas.merge(base, {'a': {'x': 3}}), {'a': {'x': 3, 'y': 2}})
        self.assertEqual(base['a']['x'], 1)

    def test_all_modes_sandboxed(self):
        for mode in oas.MODES:
            cfg = oas.config(mode)
            self.assertNotEqual(cfg['sandbox_mode'], 'danger-full-access')
            self.assertFalse(cfg['sandbox_workspace_write']['network_access'])
            self.assertEqual(cfg['sandbox_workspace_write']['writable_roots'], [])

    def test_tutor_readonly(self):
        cfg = oas.config('tutor')
        self.assertEqual(cfg['sandbox_mode'], 'read-only')
        self.assertFalse(cfg['agents']['enabled'])
        self.assertFalse(cfg['apps']['_default']['default_tools_enabled'])

    def test_unattended_no_escalation(self):
        cfg = oas.config('unattended')
        self.assertEqual(cfg['approval_policy'], 'never')
        self.assertEqual(cfg['web_search'], 'disabled')
        self.assertFalse(cfg['apps']['_default']['default_tools_enabled'])

    def test_ops_human_app_writes(self):
        cfg = oas.config('ops')['apps']['_default']
        self.assertEqual(cfg['approvals_reviewer'], 'user')
        self.assertEqual(cfg['default_tools_approval_mode'], 'writes')

    def test_no_model_override(self):
        self.assertNotIn('model', oas.config('development'))

    def test_role_paths_exist(self):
        for role in ('researcher', 'reviewer', 'builder'):
            self.assertTrue(Path(oas.config('research')['agents'][role]['config_file']).is_file())

    def test_shell_metacharacters_are_one_argument(self):
        task = 'Test $(touch /tmp/oas-should-not-exist); `whoami` "quoted"'
        cmd = oas.command('codex', 'development', self.root, task)
        self.assertTrue(cmd[-1].endswith(task))
        self.assertEqual(cmd.count('-C'), 1)
        self.assertEqual(cmd[-2], str(self.root))

    def test_missing_workspace_rejected(self):
        with self.assertRaises(FileNotFoundError):
            oas.command('codex', 'ops', self.root / 'missing', 'task')

    def test_empty_task_rejected(self):
        with self.assertRaises(ValueError):
            oas.prompt('ops', ' ')

    def test_adapters_get_same_core(self):
        for agent in oas.AGENTS[:-1]:
            cmd = oas.command(agent, 'research', self.root, 'Question')
            self.assertIn('Frame → Work → Prove → Hand off', cmd[-1])
            self.assertTrue(cmd[-1].endswith('Question'))
            self.assertNotIn('--yolo', cmd)
            self.assertNotIn('--allow-all', cmd)

    def test_native_tutor_controls(self):
        self.assertIn('plan', oas.command('claude', 'tutor', self.root, 'Teach me'))
        self.assertIn('ask', oas.command('cursor', 'tutor', self.root, 'Teach me'))
        self.assertIn('plan', oas.command('gemini', 'tutor', self.root, 'Teach me'))
        self.assertIn('--deny-tool', oas.command('copilot', 'tutor', self.root, 'Teach me'))

    def test_unattended_unsupported_fails_closed(self):
        for agent in ('claude', 'cursor', 'gemini', 'copilot'):
            with self.assertRaises(ValueError):
                oas.command(agent, 'unattended', self.root, 'job')

    def test_bundle_all_agents(self):
        for agent in oas.AGENTS:
            folder = oas.bundle('research', agent, self.root / agent, 'Question')
            self.assertTrue((folder / 'PERMISSIONS.md').is_file())
            self.assertEqual(len([p for p in folder.rglob('*') if p.is_file()]), 2)

    def test_bundle_refuses_existing_project(self):
        with self.assertRaises(FileExistsError):
            oas.bundle('research', 'generic', self.root, 'Question')

    def test_export_roundtrip(self):
        content = '\n'.join(f'{k} = {oas.toml_value(v)}' for k,v in oas.flatten(oas.config('research')))
        self.assertEqual(tomllib.loads(content), oas.config('research'))

    def test_export_no_overwrite_or_symlink(self):
        p = self.root / 'profile.toml'
        oas.new_file(p, 'original')
        with self.assertRaises(FileExistsError):
            oas.new_file(p, 'changed')
        link = self.root / 'link'
        link.symlink_to(self.root / 'nonexistent')
        with self.assertRaises(FileExistsError):
            oas.new_file(link, 'changed')
        self.assertEqual(p.read_text(), 'original')

    def test_initial_task_valid_not_complete(self):
        p = self.task()
        self.assertEqual(oas.validate_task(p), [])
        self.assertEqual(json.loads(p.read_text())['status'], 'planned')

    def test_complete_requires_all_evidence(self):
        p = self.task()
        data = json.loads(p.read_text()); data['status'] = 'complete'
        p.write_text(json.dumps(data))
        self.assertTrue(oas.validate_task(p))
        data['criteria'][0].update(passed=True, evidence=['test.txt'])
        (p.parent / 'test.txt').write_text('Regression output')
        p.write_text(json.dumps(data))
        self.assertEqual(oas.validate_task(p), [])

    def test_complete_rejects_blockers(self):
        p = self.task(); data = json.loads(p.read_text())
        data['status'] = 'complete'; data['checkpoint']['blockers'] = ['CI failed']
        p.write_text(json.dumps(data))
        self.assertIn('Complete task still has blockers', oas.validate_task(p))

    def test_evidence_cannot_escape_or_be_empty(self):
        p = self.task(); data = json.loads(p.read_text())
        outside = self.root / 'outside.txt'; outside.write_text('data')
        (p.parent / 'link').symlink_to(outside)
        for evidence in ('../outside.txt', str(outside), 'link', 'missing'):
            data['criteria'][0].update(passed=True, evidence=[evidence]); p.write_text(json.dumps(data))
            self.assertTrue(oas.validate_task(p), evidence)

    def test_unattended_contract_needs_scope_and_budget(self):
        p = self.task(); data = json.loads(p.read_text())
        data.update(mode='unattended', status='active')
        p.write_text(json.dumps(data))
        self.assertTrue(oas.validate_task(p))
        data.update(authorized_actions=['Write local report'], writable_scope=['reports/'], budget={'max_minutes':10,'max_iterations':2})
        p.write_text(json.dumps(data))
        self.assertEqual(oas.validate_task(p), [])

    def test_malformed_criterion(self):
        p = self.task(); data = json.loads(p.read_text())
        data['criteria'] = [None]; p.write_text(json.dumps(data))
        self.assertTrue(oas.validate_task(p))

    def test_run_uses_argv_and_cwd(self):
        with patch.object(oas.shutil, 'which', return_value='/bin/codex'), patch.object(oas.subprocess, 'call', return_value=0) as call:
            self.assertEqual(oas.main(['run','development','--workspace',str(self.root),'--task','Task']), 0)
            self.assertIsInstance(call.call_args.args[0], list)
            self.assertEqual(call.call_args.kwargs, {'cwd':self.root})

    def test_copilot_bypass_environment_rejected(self):
        with patch.object(oas.shutil, 'which', return_value='/bin/copilot'), patch.dict(oas.os.environ, {'COPILOT_ALLOW_ALL':'true'}), patch.object(oas.subprocess, 'call') as call:
            self.assertEqual(oas.main(['run','ops','--agent','copilot','--workspace',str(self.root),'--task','Task']), 2)
            call.assert_not_called()

if __name__ == '__main__':
    unittest.main()
