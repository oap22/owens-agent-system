import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parents[1] / 'scripts/oas.py'

spec = importlib.util.spec_from_file_location('oas', SOURCE)
oas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oas)


class OASTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        # Never read the real home directory: shared-guidance detection defaults to Path.home().
        self.home = self.root / 'home'
        self.home.mkdir()
        self.enterContext(patch.object(oas.Path, 'home', return_value=self.home))

    def task(self):
        return oas.new_task('development', self.root, 'Fix it', ['Regression passes']) / 'task.json'

    def install_block(self, agent, body=None):
        body = '\n\n'.join((oas.ROOT / p).read_text(encoding='utf-8') for p in oas.SHARED_PROMPTS) if body is None else body
        path = self.home / oas.GLOBAL_INSTRUCTIONS[agent]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'# Local notes\n\n{oas.MANAGED_START}\n{body}\n{oas.MANAGED_END}\n', encoding='utf-8')
        return path

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
        self.assertFalse(cfg['apps']['_default']['enabled'])

    def test_unattended_no_escalation(self):
        cfg = oas.config('unattended')
        self.assertEqual(cfg['approval_policy'], 'never')
        self.assertEqual(cfg['web_search'], 'disabled')
        self.assertFalse(cfg['apps']['_default']['enabled'])

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

    def test_claude_task_cannot_look_like_an_option(self):
        for task in ('-p', '--dangerously-skip-permissions', '  --settings x'):
            with self.assertRaises(ValueError, msg=task):
                oas.command('claude', 'development', self.root, task, shared='never')
        cmd = oas.command('codex', 'development', self.root, '-p', shared='never')
        self.assertTrue(cmd[-1].startswith('Shared guidance'))

    def test_missing_workspace_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            oas.command('codex', 'ops', self.root / 'missing', 'task')
        self.assertIn('missing', str(ctx.exception))

    def test_deleted_cwd_names_the_problem(self):
        gone = self.root / 'gone'; gone.mkdir()
        self.addCleanup(oas.os.chdir, oas.os.getcwd())
        oas.os.chdir(gone); gone.rmdir()
        with self.assertRaises(ValueError) as ctx:
            oas.workspace_path('.')
        self.assertIn('current directory', str(ctx.exception))

    def test_empty_task_rejected(self):
        with self.assertRaises(ValueError):
            oas.prompt('ops', ' ')

    def test_adapters_get_same_core(self):
        for agent in oas.AGENTS[:-1]:
            cmd = oas.command(agent, 'research', self.root, 'Question')
            self.assertIn('Frame → Work → Prove → Hand off', ' '.join(cmd))
            self.assertTrue(cmd[-1].endswith('Question'))
            self.assertNotIn('--yolo', cmd)
            self.assertNotIn('--allow-all', cmd)

    def test_native_tutor_controls(self):
        self.assertIn('plan', oas.command('claude', 'tutor', self.root, 'Teach me'))
        self.assertIn('ask', oas.command('cursor', 'tutor', self.root, 'Teach me'))
        self.assertIn('--deny-tool', oas.command('copilot', 'tutor', self.root, 'Teach me'))

    def test_unattended_unsupported_fails_closed(self):
        for agent in ('claude', 'cursor', 'copilot', 'opencode'):
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

    def test_check_rejects_full_access_without_assert(self):
        cfg = oas.config('development'); cfg['sandbox_mode'] = 'danger-full-access'
        with patch.object(oas, 'config', return_value=cfg):
            with self.assertRaises(ValueError):
                oas.check(skills_root=self.root / 'no-skills')
        cfg = oas.config('development'); cfg['sandbox_workspace_write']['network_access'] = True
        with patch.object(oas, 'config', return_value=cfg):
            with self.assertRaises(ValueError):
                oas.check(skills_root=self.root / 'no-skills')

    def test_check_enforced_under_optimize_flag(self):
        code = ('import importlib.util, sys; from unittest.mock import patch\n'
                f'spec = importlib.util.spec_from_file_location("oas", {str(SOURCE)!r})\n'
                'oas = importlib.util.module_from_spec(spec); spec.loader.exec_module(oas)\n'
                'cfg = oas.config("development"); cfg["sandbox_mode"] = "danger-full-access"\n'
                'with patch.object(oas, "config", return_value=cfg):\n'
                f'    sys.exit(oas.main(["check", "--skills-root", {str(self.root / "no-skills")!r}]))\n')
        result = subprocess.run([sys.executable, '-O', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('danger-full-access', result.stderr)

    def test_check_counts_roles_and_reports_pass(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            oas.check(skills_root=self.root / 'no-skills')
        roles = len(list((oas.ROOT / 'config/agents').glob('*.toml')))
        self.assertIn(f'{roles} roles', out.getvalue())

    def test_shared_detection_requires_current_block(self):
        self.assertFalse(oas.shared_installed('claude', self.home))
        path = self.install_block('claude')
        self.assertTrue(oas.shared_installed('claude', self.home))
        self.assertFalse(oas.shared_installed('codex', self.home))
        self.install_block('claude', 'core text changed')
        self.assertFalse(oas.shared_installed('claude', self.home))
        self.install_block('claude')
        path.write_text(path.read_text(encoding='utf-8') + oas.MANAGED_START, encoding='utf-8')
        self.assertFalse(oas.shared_installed('claude', self.home))
        path.write_bytes(b'\xff\xfe' + oas.MANAGED_START.encode())
        self.assertFalse(oas.shared_installed('claude', self.home))

    def test_generic_and_unknown_agents_never_detected(self):
        for agent in ('generic', 'nonexistent'):
            self.assertFalse(oas.shared_installed(agent, self.home))
            self.assertEqual(oas.shared_decision(agent, 'auto', self.home)[0], True)

    def test_shared_auto_omits_only_when_installed(self):
        core = 'Frame → Work → Prove → Hand off'
        for agent in ('codex', 'claude'):
            self.assertIn(core, ' '.join(oas.command(agent, 'development', self.root, 'Task', home=self.home)))
            self.install_block(agent)
            cmd = oas.command(agent, 'development', self.root, 'Task', home=self.home)
            self.assertNotIn(core, ' '.join(cmd))
            self.assertIn('Shared guidance is loaded from your global instructions; this is the development workflow.', ' '.join(cmd))
            self.assertTrue(cmd[-1].endswith('Task'))
            self.assertIn(core, ' '.join(oas.command(agent, 'development', self.root, 'Task', shared='always', home=self.home)))
        self.assertNotIn(core, ' '.join(oas.command('copilot', 'development', self.root, 'Task', shared='never', home=self.home)))
        with self.assertRaises(ValueError):
            oas.command('codex', 'development', self.root, 'Task', shared='sometimes', home=self.home)

    def test_shared_auto_uses_patched_home_by_default(self):
        self.install_block('codex')
        self.assertFalse(oas.shared_decision('codex')[0])
        self.assertTrue(oas.shared_decision('claude')[0])

    def test_prompt_is_guidance_plus_task(self):
        for shared in (True, False):
            self.assertEqual(oas.prompt('ops', 'Do it', shared), oas.guidance('ops', shared) + '\n\n# Current user task\n\nDo it')
        self.assertTrue(oas.guidance('ops', False).startswith('Shared guidance is loaded from your global instructions; this is the ops workflow.'))
        self.assertNotIn('Shared guidance is loaded', oas.guidance('ops', True))

    def test_claude_guidance_in_system_prompt(self):
        cmd = oas.command('claude', 'research', self.root, 'Question', shared='always', home=self.home)
        self.assertEqual(cmd[-1], 'Question')
        self.assertEqual(cmd[-3], '--append-system-prompt')
        self.assertEqual(cmd[-2], oas.guidance('research', True))
        self.assertNotIn('# Current user task', cmd[-2])
        self.assertEqual(cmd[:2], ['claude', '--settings'])

    def test_preview_reports_shared_decision(self):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            self.assertEqual(oas.main(['preview', 'development', '--agent', 'claude', '--workspace', str(self.root), '--task', 'x']), 0)
        self.assertIn('shared guidance included: no managed block', err.getvalue())
        self.assertIn('--append-system-prompt', out.getvalue())
        self.install_block('claude')
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(oas.main(['preview', 'development', '--agent', 'claude', '--workspace', str(self.root), '--task', 'x']), 0)
        self.assertIn('shared guidance omitted: managed block', err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(oas.main(['preview', 'development', '--workspace', str(self.root), '--task', 'x', '--shared', 'never']), 0)
        self.assertIn('omitted: --shared never', err.getvalue())

    def test_run_passes_shared_flag_and_resolves_workspace_once(self):
        self.install_block('codex')
        with patch.object(oas.shutil, 'which', return_value='/bin/codex'), patch.object(oas.subprocess, 'call', return_value=0) as call:
            self.assertEqual(oas.main(['run', 'development', '--workspace', str(self.root), '--task', 'Task']), 0)
            self.assertNotIn('Frame → Work → Prove → Hand off', call.call_args.args[0][-1])
            self.assertEqual(call.call_args.kwargs, {'cwd': self.root})
            self.assertEqual(oas.main(['run', 'development', '--workspace', str(self.root), '--task', 'Task', '--shared', 'always']), 0)
            self.assertIn('Frame → Work → Prove → Hand off', call.call_args.args[0][-1])

    def test_bundle_shared_flag(self):
        core = 'Frame → Work → Prove → Hand off'
        self.assertIn(core, (oas.bundle('research', 'generic', self.root / 'a', 'Q') / 'AGENTS.md').read_text(encoding='utf-8'))
        self.assertNotIn(core, (oas.bundle('research', 'generic', self.root / 'b', 'Q', shared=False) / 'AGENTS.md').read_text(encoding='utf-8'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(oas.main(['bundle', 'research', '--output', str(self.root / 'c'), '--shared', 'never']), 0)
            self.assertEqual(oas.main(['bundle', 'research', '--output', str(self.root / 'd')]), 0)
        self.assertNotIn(core, (self.root / 'c/AGENTS.md').read_text(encoding='utf-8'))
        self.assertIn(core, (self.root / 'd/AGENTS.md').read_text(encoding='utf-8'))

    def test_task_from_scenario(self):
        item = oas.scenario('coursework')
        p = oas.new_task(None, self.root, None, None, scenario_id='coursework') / 'task.json'
        self.assertEqual(oas.validate_task(p), [])
        data = json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(data['scenario'], 'coursework')
        self.assertEqual(data['mode'], item['mode'])
        self.assertEqual(data['title'], item['prompt'])
        self.assertEqual([c['description'] for c in data['criteria']], item['expected'] + item['checks'])
        p = oas.new_task(item['mode'], self.root, 'Custom', ['Own criterion'], scenario_id='coursework') / 'task.json'
        data = json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual((data['title'], [c['description'] for c in data['criteria']]), ('Custom', ['Own criterion']))
        with self.assertRaises(ValueError):
            oas.new_task('development', self.root, None, None, scenario_id='coursework')
        with self.assertRaises(ValueError):
            oas.new_task(None, self.root, None, None, scenario_id='nonexistent')
        self.assertNotIn('scenario', json.loads(self.task().read_text(encoding='utf-8')))

    def test_task_cli_scenario_and_required_fields(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['task', '--scenario', 'regression', '--output', str(self.root / 'a')]), 0)
            self.assertEqual(oas.main(['task', 'development', '--output', str(self.root / 'b'), '--title', 'T', '--criterion', 'C']), 0)
            self.assertEqual(oas.main(['task', '--output', str(self.root / 'c'), '--title', 'T', '--criterion', 'C']), 2)
            self.assertEqual(oas.main(['task', 'development', '--output', str(self.root / 'd'), '--title', 'T']), 2)
            self.assertEqual(oas.main(['task', 'tutor', '--scenario', 'regression', '--output', str(self.root / 'e')]), 2)
        self.assertEqual(json.loads((Path(out.getvalue().splitlines()[0]) / 'task.json').read_text(encoding='utf-8'))['scenario'], 'regression')
        self.assertFalse((self.root / 'c').exists()); self.assertFalse((self.root / 'd').exists()); self.assertFalse((self.root / 'e').exists())

    def test_validate_task_scenario_field(self):
        p = self.task(); data = json.loads(p.read_text())
        data['scenario'] = 'coursework'; p.write_text(json.dumps(data))
        self.assertEqual(oas.validate_task(p), [])
        for bad in ('', 7, None):
            data['scenario'] = bad; p.write_text(json.dumps(data))
            self.assertIn('scenario must be a nonempty string when present', oas.validate_task(p))

    def test_routed_skills_parsed(self):
        names = oas.routed_skills()
        self.assertIn('plan-then-ship', names)
        self.assertIn('research-loop', names)
        self.assertTrue(all(name == name.strip() and ' ' not in name for name in names))

    def test_skill_routing_drift(self):
        skills = self.root / 'skills'
        for name in oas.routed_skills():
            (skills / name).mkdir(parents=True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            oas.check(skills_root=skills)
        self.assertEqual(err.getvalue(), '')
        (skills / 'plan-then-ship').rmdir()
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            self.assertEqual(oas.main(['check', '--skills-root', str(skills)]), 0)
        self.assertIn('WARNING: routed skill `plan-then-ship`', err.getvalue())
        self.assertNotIn('research-loop', err.getvalue())
        self.assertIn('PASS:', out.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(oas.main(['check', '--skills-root', str(self.root / 'absent')]), 0)
        self.assertIn('skills repo not present; routing check skipped', err.getvalue())

    def test_lead_effort_maps_per_harness(self):
        cmd = oas.command('codex', 'development', self.root, 'Task', lead_effort='xhigh')
        self.assertIn('model_reasoning_effort="xhigh"', cmd)
        self.assertEqual(cmd[cmd.index('model_reasoning_effort="xhigh"') - 1], '-c')
        cmd = oas.command('claude', 'development', self.root, 'Task', shared='never', lead_effort='high')
        self.assertEqual(cmd[cmd.index('--effort') + 1], 'high')
        self.assertEqual(cmd[-1], 'Task')
        for cmd in (oas.command('codex', 'development', self.root, 'Task'), oas.command('claude', 'development', self.root, 'Task')):
            self.assertNotIn('--effort', cmd)
            self.assertFalse(any('model_reasoning_effort' in a for a in cmd))
        with self.assertRaises(ValueError):
            oas.command('codex', 'development', self.root, 'Task', lead_effort='ultra')

    def test_worker_options_define_implementor_for_claude(self):
        cmd = oas.command('claude', 'development', self.root, 'Task', shared='never', worker_model='sonnet', worker_effort='low')
        spec = json.loads(cmd[cmd.index('--agents') + 1])
        self.assertEqual(list(spec), ['implementor'])
        agent = spec['implementor']
        self.assertEqual((agent['model'], agent['effort'], agent['maxTurns']), ('sonnet', 'low', oas.IMPLEMENTOR_MAX_TURNS))
        self.assertEqual(agent['tools'], oas.IMPLEMENTOR_TOOLS)
        self.assertEqual(agent['prompt'], oas.role('implementor')['developer_instructions'].strip())
        self.assertTrue(agent['description'])
        self.assertEqual(cmd[-3], '--append-system-prompt')
        self.assertNotIn('model', json.loads(oas.implementor_agent({'effort': 'medium'}))['implementor'])
        self.assertNotIn('--agents', oas.command('claude', 'development', self.root, 'Task', shared='never'))

    def test_worker_options_write_codex_overlay(self):
        cmd = oas.command('codex', 'development', self.root, 'Task', worker_model='gpt-mini', worker_effort='low')
        keys = [a for a in cmd if a.startswith('agents.implementor.config_file=')]
        self.assertEqual(len(keys), 1)
        self.assertEqual(sum(a.startswith('model_reasoning_effort=') for a in oas.command('codex', 'development', self.root, 'T', lead_effort='low')), 1)
        path = Path(json.loads(keys[0].split('=', 1)[1]))
        self.assertEqual(path, self.root / '.oas/roles/implementor.toml')
        layer = tomllib.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((layer['model'], layer['model_reasoning_effort'], layer['sandbox_mode']), ('gpt-mini', 'low', 'workspace-write'))
        self.assertEqual(layer['developer_instructions'], oas.role('implementor')['developer_instructions'])
        oas.command('codex', 'development', self.root, 'Task', worker_effort='medium')
        layer = tomllib.loads(path.read_text(encoding='utf-8'))
        self.assertNotIn('model', layer); self.assertEqual(layer['model_reasoning_effort'], 'medium')
        plain = [a for a in oas.command('codex', 'development', self.root, 'Task') if a.startswith('agents.implementor.config_file=')]
        self.assertEqual(plain, [f'agents.implementor.config_file={oas.toml_value(str(oas.ROOT / "config/agents/implementor.toml"))}'])
        path.unlink(); path.symlink_to(self.root / 'elsewhere')
        with self.assertRaises(ValueError):
            oas.command('codex', 'development', self.root, 'Task', worker_effort='low')

    def test_delegation_refused_where_unsupported(self):
        for agent in ('cursor', 'copilot', 'opencode'):
            with self.assertRaises(ValueError, msg=agent):
                oas.command(agent, 'development', self.root, 'Task', lead_effort='high')
            with self.assertRaises(ValueError, msg=agent):
                oas.command(agent, 'development', self.root, 'Task', worker_effort='low')
        for mode in ('tutor', 'unattended'):
            with self.assertRaises(ValueError, msg=mode):
                oas.command('codex', mode, self.root, 'Task', worker_effort='low')
        self.assertIn('model_reasoning_effort="high"', oas.command('codex', 'unattended', self.root, 'Task', lead_effort='high'))
        for model in ('-p', 'a b', '', 'x;y'):
            with self.assertRaises(ValueError, msg=model):
                oas.command('claude', 'development', self.root, 'Task', worker_model=model)
        self.assertFalse((self.root / '.oas').exists())

    def test_preview_accepts_delegation_flags(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['preview', 'development', '--agent', 'claude', '--workspace', str(self.root), '--task', 'x',
                                       '--lead-effort', 'xhigh', '--worker-model', 'haiku', '--worker-effort', 'low']), 0)
            self.assertEqual(oas.main(['preview', 'development', '--agent', 'cursor', '--workspace', str(self.root), '--task', 'x', '--lead-effort', 'high']), 2)
        self.assertIn('--effort xhigh', out.getvalue())
        self.assertIn('--agents', out.getvalue())

    def test_text_io_declares_utf8(self):
        source = SOURCE.read_text(encoding='utf-8')
        for match in re.finditer(r'\.(read_text|write_text)\(([^)]*)\)', source):
            self.assertIn("encoding='utf-8'", match.group(2), match.group(0))
        self.assertNotIn('assert ', source.split('def check(')[1].split('def main(')[0])

if __name__ == '__main__':
    unittest.main()


class ModelFlagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_every_adapter_passes_model_flag_and_none_inherits(self):
        for agent in oas.AGENTS[:-1]:
            mode = 'development'
            cmd = oas.command(agent, mode, self.root, 'Task', shared='never', model='my-model')
            self.assertEqual(cmd[cmd.index('--model') + 1], 'my-model', agent)
            self.assertTrue(cmd[-1].endswith('Task'), agent)
            self.assertNotIn('--model', oas.command(agent, mode, self.root, 'Task', shared='never'), agent)

    def test_model_ids_validated(self):
        for bad in ('', ' ', 'bad model', '-x', 'a;b', 'm$'):
            with self.assertRaises(ValueError, msg=bad):
                oas.command('codex', 'development', self.root, 'Task', shared='never', model=bad)
        for good in ('opus', 'gpt-5.6-luna', 'openai/gpt-5.4', 'ollama/qwen3-coder:30b', 'claude-fable-5-1'):
            oas.command('codex', 'development', self.root, 'Task', shared='never', model=good)

    def test_cli_model_reaches_run_and_preview(self):
        with patch.object(oas.shutil, 'which', return_value='/bin/codex'), patch.object(oas.subprocess, 'call', return_value=0) as call:
            self.assertEqual(oas.main(['run', 'development', '--workspace', str(self.root), '--task', 'T', '--model', 'gpt-x']), 0)
            argv = call.call_args.args[0]
            self.assertEqual(argv[argv.index('--model') + 1], 'gpt-x')
