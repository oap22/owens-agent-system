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
            self.assertIn('automatic context compaction as lossy working-memory compression', ' '.join(cmd))
            self.assertTrue(cmd[-1].endswith('Question'))
            self.assertNotIn('--yolo', cmd)
            self.assertNotIn('--allow-all', cmd)

    def test_claude_native_autocompact_is_explicit(self):
        for mode in ('development', 'research', 'ops', 'tutor'):
            cmd = oas.command('claude', mode, self.root, 'Task')
            self.assertEqual(cmd.count('--autocompact'), 1, mode)
            self.assertEqual(cmd[cmd.index('--autocompact') + 1], 'auto', mode)

    def test_every_workflow_defines_compaction_continuity(self):
        for mode in oas.MODES:
            workflow = (oas.ROOT / f'workflows/{mode}.md').read_text(encoding='utf-8').lower()
            self.assertIn('compact', workflow, mode)
            self.assertTrue('checkpoint' in workflow or 'retrieval' in workflow, mode)

    def test_compaction_scenarios_cover_every_mode(self):
        covered = {item['mode'] for item in oas.scenarios() if item['id'].startswith('compact-')}
        self.assertEqual(covered, set(oas.MODES))

    def test_native_tutor_controls(self):
        self.assertIn('plan', oas.command('claude', 'tutor', self.root, 'Teach me'))
        self.assertIn('ask', oas.command('cursor', 'tutor', self.root, 'Teach me'))
        self.assertIn('--deny-tool', oas.command('copilot', 'tutor', self.root, 'Teach me'))

    def test_claude_native_permission_modes(self):
        expected = {
            'development': 'auto',
            'research': 'auto',
            'ops': 'default',
            'tutor': 'plan',
        }
        for mode, permission_mode in expected.items():
            cmd = oas.command('claude', mode, self.root, 'Task')
            index = cmd.index('--permission-mode')
            self.assertEqual(cmd[index + 1], permission_mode, mode)
            self.assertNotIn('acceptEdits', cmd)
            self.assertNotIn('bypassPermissions', cmd)
        settings = json.loads((Path(__file__).parents[1] / 'adapters/claude/settings.json').read_text())
        self.assertEqual(settings['permissions']['defaultMode'], 'auto')
        self.assertEqual(settings['permissions']['disableBypassPermissionsMode'], 'disable')

    def test_claude_auto_rejects_known_ineligible_models(self):
        for mode in ('development', 'research'):
            for model in ('haiku', 'claude-haiku-4-5', 'claude-3-opus', 'claude-sonnet-4-5', 'claude-opus-4.5'):
                with self.assertRaisesRegex(ValueError, 'auto mode', msg=f'{mode}/{model}'):
                    oas.command('claude', mode, self.root, 'Task', model=model)
        for mode in ('ops', 'tutor'):
            self.assertIn('haiku', oas.command('claude', mode, self.root, 'Task', model='haiku'))
        for model in (None, 'fable', 'sonnet', 'opus', 'claude-sonnet-5', 'claude-opus-4-7'):
            oas.command('claude', 'development', self.root, 'Task', model=model)

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
        data = json.loads(p.read_text())
        self.assertEqual((data['schema_version'], data['status']), (2, 'planned'))
        self.assertEqual(data['checkpoint'], {
            'phase': 'frame', 'completed': [], 'blockers': [], 'next_action': 'Confirm scope and begin',
            'commit': None, 'worktree': None, 'owned_files': [], 'changed_files': [], 'evidence_paths': [],
            'reverify': [], 'cursor': None, 'iteration': 0, 'retries_used': 0,
        })

    def test_version_two_checkpoint_fields_are_required_and_version_one_stays_readable(self):
        p = self.task()
        original = json.loads(p.read_text())
        for field in ('phase', 'next_action', 'completed', 'owned_files', 'changed_files', 'evidence_paths',
                      'reverify', 'commit', 'worktree', 'cursor', 'iteration', 'retries_used'):
            data = json.loads(json.dumps(original))
            del data['checkpoint'][field]
            p.write_text(json.dumps(data))
            self.assertTrue(oas.validate_task(p), field)
        legacy = json.loads(json.dumps(original))
        legacy['schema_version'] = 1
        legacy['checkpoint'] = {k: legacy['checkpoint'][k] for k in ('completed', 'blockers', 'next_action', 'commit')}
        p.write_text(json.dumps(legacy))
        self.assertEqual(oas.validate_task(p), [])

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

    def test_unattended_continuity_cannot_exceed_contract(self):
        p = self.task(); data = json.loads(p.read_text())
        data.update(mode='unattended', status='active', authorized_actions=['Write local report'],
                    writable_scope=['reports/'], budget={'max_minutes': 10, 'max_iterations': 2}, retry_limit=1)
        data['checkpoint'].update(iteration=3, retries_used=2)
        p.write_text(json.dumps(data))
        errors = oas.validate_task(p)
        self.assertIn('Checkpoint retries exceed retry limit', errors)
        self.assertIn('Checkpoint iteration exceeds task budget', errors)
        data['schema_version'] = 1
        data['checkpoint'] = {k: data['checkpoint'][k] for k in ('completed', 'blockers', 'next_action', 'commit')}
        p.write_text(json.dumps(data))
        self.assertIn('Active unattended task requires schema version 2 continuity state', oas.validate_task(p))

    def test_checkpoint_evidence_must_be_local_and_present(self):
        p = self.task(); data = json.loads(p.read_text())
        for evidence in ('../outside.txt', '/absolute.txt', 'missing.txt'):
            data['checkpoint']['evidence_paths'] = [evidence]
            p.write_text(json.dumps(data))
            self.assertTrue(oas.validate_task(p), evidence)
        (p.parent / 'result.txt').write_text('current evidence')
        data['checkpoint']['evidence_paths'] = ['result.txt']
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
        self.assertEqual(path.parent, self.root / '.oas/roles')
        original = path.read_bytes()
        layer = tomllib.loads(path.read_text(encoding='utf-8'))
        self.assertEqual((layer['model'], layer['model_reasoning_effort'], layer['sandbox_mode']), ('gpt-mini', 'low', 'workspace-write'))
        self.assertEqual(layer['developer_instructions'], oas.role('implementor')['developer_instructions'])
        oas.command('codex', 'development', self.root, 'Task', worker_effort='medium')
        other = oas.implementor_overlay(self.root, {'effort': 'medium'})
        self.assertNotEqual(path, other)
        self.assertEqual(path.read_bytes(), original)
        layer = tomllib.loads(other.read_text(encoding='utf-8'))
        self.assertNotIn('model', layer); self.assertEqual(layer['model_reasoning_effort'], 'medium')
        plain = [a for a in oas.command('codex', 'development', self.root, 'Task') if a.startswith('agents.implementor.config_file=')]
        self.assertEqual(plain, [f'agents.implementor.config_file={oas.toml_value(str(oas.ROOT / "config/agents/implementor.toml"))}'])
        path.unlink(); path.symlink_to(self.root / 'elsewhere')
        with self.assertRaises(ValueError):
            oas.command('codex', 'development', self.root, 'Task', worker_model='gpt-mini', worker_effort='low')

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


class TokenEconomyTest(unittest.TestCase):
    def test_preview_does_not_write_and_doctor_uses_launch_options(self):
        args = ['development', '--workspace', str(self.root), '--model', 'gpt-6-astra',
                '--lead-effort', 'high', '--worker-model', 'gpt-5.6-luna',
                '--worker-effort', 'low', '--worker-retry-effort', 'medium']
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['preview', *args, '--task', 'Fix it']), 0)
        self.assertFalse((self.root / '.oas').exists())
        with patch.object(oas.shutil, 'which', return_value='/bin/codex'), patch.object(oas.subprocess, 'call', return_value=0) as call:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(oas.main(['doctor', *args]), 0)
        cmd = call.call_args.args[0]
        self.assertEqual(cmd[-2:], ['doctor', '--summary'])
        self.assertEqual(cmd[cmd.index('--model') + 1], 'gpt-6-astra')
        self.assertIn('model_reasoning_effort="high"', cmd)
        self.assertEqual(call.call_args.kwargs['cwd'], self.root)
        self.assertEqual(len(list((self.root / '.oas/roles').glob('*.toml'))), 2)

    def test_role_snapshots_parallel_and_parent_symlinks(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda effort: oas.implementor_overlay(self.root, {'effort': effort}),
                                  ['low', 'medium', 'low', 'high']))
        self.assertEqual(paths[0], paths[2])
        self.assertEqual(len(set(paths)), 3)
        for path, effort in zip(paths, ['low', 'medium', 'low', 'high']):
            self.assertEqual(tomllib.loads(path.read_text(encoding='utf-8'))['model_reasoning_effort'], effort)
        workspace = self.root / 'other'; workspace.mkdir()
        (workspace / '.oas').symlink_to(self.root / '.oas')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            oas.implementor_overlay(workspace, {'effort': 'low'})

    def test_runtime_selection_is_explicit_and_invalid_choice_fails(self):
        binary = self.root / 'custom codex'
        binary.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8'); binary.chmod(0o700)
        with patch.dict(oas.os.environ, {'OAS_CODEX_BIN': str(binary)}):
            self.assertEqual(oas.launch_command('codex', 'development', self.root, 'Task')[0], str(binary))
        with patch.dict(oas.os.environ, {'OAS_CODEX_BIN': '/missing/oas-codex'}):
            with self.assertRaisesRegex(ValueError, 'OAS_CODEX_BIN'):
                oas.launch_command('codex', 'development', self.root, 'Task')

    def test_cost_groups_modes_cohorts_and_unique_completed_tasks(self):
        base = dict(task='same', harness='claude', mode='development', result='pass', cost_usd=2)
        for _ in range(2):
            oas.log_run(self.root, **base)
        oas.log_run(self.root, **dict(base, mode='research'))
        oas.log_run(self.root, **dict(base, cohort='new-suite', runtime_version='2.1.266'))
        report = oas.report_runs(self.root)
        self.assertIn('development / unspecified / claude lead inherit@default alone | 2 | 1 | 4.00', report)
        self.assertIn('research / unspecified / claude', report)
        self.assertIn('development / new-suite / claude [runtime 2.1.266]', report)
        for value in (float('nan'), float('inf'), -float('inf')):
            for key in ('cost_usd', 'minutes'):
                with self.assertRaises(ValueError):
                    oas.log_run(self.root, **dict(base, **{key: value}))

    def test_cli_cost_report_keeps_distinct_configuration_fields_separate(self):
        common = [sys.executable, str(SOURCE), 'log-run', '--output', str(self.root), '--task', 'same',
                  '--mode', 'development', '--result', 'pass', '--cohort', 'coding-v1', '--cost-usd', '2']
        subprocess.run([*common, '--harness', 'codex 0.154'], check=True, capture_output=True)
        subprocess.run([*common, '--harness', 'codex', '--runtime-version', '0.154'], check=True, capture_output=True)
        report = subprocess.run([sys.executable, str(SOURCE), 'report-runs', '--output', str(self.root)],
                                check=True, capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(len(report), 3, report)
        self.assertNotEqual(report[1].split(' | ')[0], report[2].split(' | ')[0])
        for row in report[1:]:
            self.assertIn(' | 1 | 1 | 2.00 | 0 | ', row)

    def test_malformed_checkpoint_returns_errors_instead_of_crashing(self):
        path = oas.new_task('development', self.root, 'Fix it', ['Regression passes']) / 'task.json'
        record = json.loads(path.read_text(encoding='utf-8'))
        for value in (None, 5, False, 'evidence.txt'):
            record['checkpoint']['evidence_paths'] = value
            path.write_text(json.dumps(record), encoding='utf-8')
            self.assertIn('Checkpoint evidence_paths must be a string list', oas.validate_task(path))
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home'; self.home.mkdir()
        self.enterContext(patch.object(oas.Path, 'home', return_value=self.home))

    def test_retry_rung_defines_second_claude_agent_same_model_higher_effort(self):
        cmd = oas.command('claude', 'development', self.root, 'Task', shared='never', worker_model='sonnet', worker_effort='low', retry_effort='medium')
        spec = json.loads(cmd[cmd.index('--agents') + 1])
        self.assertEqual(list(spec), ['implementor', 'implementor-retry'])
        first, retry = spec['implementor'], spec['implementor-retry']
        self.assertEqual((first['model'], first['effort']), ('sonnet', 'low'))
        self.assertEqual((retry['model'], retry['effort']), ('sonnet', 'medium'))
        self.assertEqual(retry['prompt'], first['prompt'])
        self.assertEqual((retry['tools'], retry['maxTurns']), (first['tools'], first['maxTurns']))
        self.assertNotEqual(retry['description'], first['description'])
        # Without a retry effort only the first rung exists.
        cmd = oas.command('claude', 'development', self.root, 'Task', shared='never', worker_effort='low')
        self.assertEqual(list(json.loads(cmd[cmd.index('--agents') + 1])), ['implementor'])

    def test_retry_rung_writes_second_codex_layer_and_registers_it(self):
        cmd = oas.command('codex', 'development', self.root, 'Task', worker_model='gpt-mini', worker_effort='low', retry_effort='high')
        keys = {a.split('=', 1)[0]: json.loads(a.split('=', 1)[1]) for a in cmd if a.startswith('agents.implementor')}
        self.assertEqual(Path(keys['agents.implementor-retry.config_file']).parent, self.root / '.oas/roles')
        self.assertTrue(keys['agents.implementor-retry.description'])
        self.assertEqual(keys['agents.implementor.description'], oas.config('development')['agents']['implementor']['description'])
        first = tomllib.loads(Path(keys['agents.implementor.config_file']).read_text(encoding='utf-8'))
        retry = tomllib.loads(Path(keys['agents.implementor-retry.config_file']).read_text(encoding='utf-8'))
        self.assertEqual((first['model'], first['model_reasoning_effort']), ('gpt-mini', 'low'))
        self.assertEqual((retry['model'], retry['model_reasoning_effort']), ('gpt-mini', 'high'))
        self.assertEqual(retry['developer_instructions'], first['developer_instructions'])
        plain = oas.command('codex', 'development', self.root, 'Task', worker_effort='low')
        self.assertFalse(any(a.startswith('agents.implementor-retry') for a in plain))

    def test_retry_rung_validation(self):
        with self.assertRaises(ValueError):
            oas.command('claude', 'development', self.root, 'Task', shared='never', retry_effort='medium')
        for worker, retry in (('medium', 'medium'), ('high', 'low')):
            with self.assertRaises(ValueError, msg=(worker, retry)):
                oas.command('claude', 'development', self.root, 'Task', shared='never', worker_effort=worker, retry_effort=retry)
        with self.assertRaises(ValueError):
            oas.command('codex', 'tutor', self.root, 'Task', worker_effort='low', retry_effort='high')
        with self.assertRaises(ValueError):
            oas.command('cursor', 'development', self.root, 'Task', worker_effort='low', retry_effort='high')
        self.assertFalse((self.root / '.oas').exists())

    def test_cli_retry_flag_reaches_preview_and_run(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['preview', 'development', '--agent', 'claude', '--workspace', str(self.root), '--task', 'x', '--shared', 'never',
                                       '--worker-model', 'sonnet', '--worker-effort', 'low', '--worker-retry-effort', 'medium']), 0)
        self.assertIn('implementor-retry', out.getvalue())
        with patch.object(oas.shutil, 'which', return_value='/bin/claude'), patch.object(oas.subprocess, 'call', return_value=0) as call:
            self.assertEqual(oas.main(['run', 'development', '--agent', 'claude', '--workspace', str(self.root), '--task', 'T', '--shared', 'never',
                                       '--worker-effort', 'low', '--worker-retry-effort', 'high']), 0)
            self.assertIn('implementor-retry', call.call_args.args[0][call.call_args.args[0].index('--agents') + 1])

    def test_prompt_sizes_and_budget_report(self):
        full = oas.prompt_sizes('development', 'Fix the parser', True)
        lean = oas.prompt_sizes('development', 'Fix the parser', False)
        self.assertGreater(full['guidance'], lean['guidance'])
        self.assertEqual(full['task'], oas.estimate_tokens('Fix the parser'))
        self.assertEqual(oas.estimate_tokens('abcde'), 2)
        # The estimator must stay within a tenth of what the real tokenizer charged for this
        # kit's own prose (evals/token-calibration.json); re-measure before changing the constant.
        calibration = json.loads(oas.read(oas.ROOT / oas.TOKEN_CALIBRATION))
        prose = [s for s in calibration['samples'] if s['kind'] == 'prose']
        self.assertGreaterEqual(len(prose), 5)
        for sample in prose:
            estimate = oas.estimate_tokens('x' * sample['chars'])
            self.assertLess(abs(estimate - sample['measured_tokens']) / sample['measured_tokens'], 0.10, sample['name'])
        sizes, over = oas.guidance_report()
        self.assertEqual(set(sizes), set(oas.MODES))
        self.assertEqual(over, [], 'shared guidance grew past the per-launch budget; trim it or raise the budget deliberately')
        self.assertEqual(oas.guidance_report(budget=1)[1], list(oas.MODES))
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(oas.main(['preview', 'development', '--agent', 'claude', '--workspace', str(self.root), '--task', 'x', '--shared', 'never']), 0)
        self.assertIn('estimated tokens sent: guidance', err.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['check', '--skills-root', str(self.root / 'absent')]), 0)
        self.assertIn('largest guidance about', out.getvalue())

    def test_log_run_and_report_cost_per_completed_task(self):
        oas.log_run(self.root, task='t1', harness='claude', mode='development', result='pass', lead_effort='high', cost_usd=2)
        oas.log_run(self.root, task='t2', harness='claude', mode='development', result='fail', lead_effort='high', cost_usd=1)
        oas.log_run(self.root, task='t1', harness='claude', mode='development', result='pass', lead_effort='xhigh',
                    worker_model='sonnet', worker_effort='low', retry_effort='medium', packets=3, escalated=1, cost_usd=1.5, corrections=1)
        oas.log_run(self.root, task='t3', harness='codex', mode='development', result='partial')
        lines = (self.root / 'evals/runs.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 4)
        record = json.loads(lines[3])
        self.assertIsNone(record['cost_usd'], 'unknown cost is null, never zero')
        self.assertEqual(record['schema_version'], 1)
        report = oas.report_runs(self.root)
        self.assertIn('claude lead inherit@high alone | 2 | 1 | 3.00 | 0 | 0/0 | 0', report)
        self.assertIn('claude lead inherit@xhigh worker sonnet@low->medium | 1 | 1 | 1.50 | 0 | 1/3 | 1', report)
        self.assertIn('codex lead inherit@default alone | 1 | 0 | unknown | 1 | 0/0 | 0', report)

    def test_log_run_rejects_bad_records(self):
        good = dict(task='t', harness='claude', mode='development', result='pass')
        for bad in (dict(good, result='done'), dict(good, mode='nope'), dict(good, task=' '), dict(good, packets=-1),
                    dict(good, packets=1, escalated=2), dict(good, cost_usd=-1), dict(good, cost_usd=True), dict(good, lead_effort='ultra')):
            with self.assertRaises(ValueError, msg=bad):
                oas.log_run(self.root, **bad)
        self.assertFalse((self.root / 'evals').exists())
        with self.assertRaises(OSError):
            oas.report_runs(self.root)

    def test_cli_log_and_report(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['log-run', '--output', str(self.root), '--task', 'csv', '--harness', 'codex', '--mode', 'development',
                                       '--result', 'pass', '--worker-effort', 'low', '--packets', '2', '--cost-usd', '0.8']), 0)
            self.assertEqual(oas.main(['log-run', '--output', str(self.root), '--task', 'csv', '--harness', 'codex', '--mode', 'development',
                                       '--result', 'pass', '--packets', '1', '--escalated', '2']), 2)
            self.assertEqual(oas.main(['report-runs', '--output', str(self.root)]), 0)
        self.assertIn('"cost_usd": 0.8', out.getvalue())
        self.assertIn('codex lead inherit@default worker inherit@low | 1 | 1 | 0.80', out.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(oas.main(['report-runs', '--output', str(self.root / 'nowhere')]), 2)


class RetrospectiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def scaffold(self, **options):
        return oas.new_retro(self.root, 'Fix the CSV import', 'development', 'claude', **options)

    def filled(self, summary='Add a CSV fixture to the development scenario bank', **header):
        facts = dict(task='csv-1', model='claude-fable-5-1@high', workspace='/work/project', outcome='partial', corrections=2, cost_usd=1.25, minutes=40)
        facts.update(header)
        path = self.scaffold(**facts)
        text = path.read_text(encoding='utf-8')
        body = text[text.index('## What went well'):]
        report = text[:text.index('## What went well')] + '\n'.join([
            '## What went well', '', '- The worktree was inspected first; `workflows/development.md` step 1 produced it.', '',
            '## What went wrong', '', '- The import test was rerun three times | Expected: one run after the fix | Evidence: `.oas/csv-1/check.log` | Cost: 12 minutes', '',
            '## Root causes', '', '- Repeated reruns <- policy guidance: step 5 does not say what "unresolved concern" means.', '',
            '## Proposed change', '', f'Summary: {summary}', '',
            'Why: The rerun loop above would have stopped at the first passing run with a fixture to compare against.', '',
            'Files to change:', '- `evals/scenarios.json`: add a scenario for the CSV import', '- `workflows/development.md`: define the stop rule in step 5', '',
            'Implementation steps:', '1. Add the scenario with a check that names the fixture file.', '2. Edit step 5 to stop after one passing run of the required checks.', '',
            'Acceptance criteria:', '- `check` reports one more scenario', '- The workflow names the stop rule in one sentence', '',
            'Validation:', '```sh', 'python3 scripts/oas.py check', 'python3 -m unittest discover -s tests -v', '```', '',
            'Out of scope:', '- Changing the research workflow', ''])
        del body
        path.write_text(report, encoding='utf-8')
        return path

    def test_scaffold_fills_known_facts_and_verification_demands_the_rest(self):
        path = self.scaffold(model='inherit', outcome='pass', corrections=0)
        self.assertEqual(path.parent.parent, self.root / oas.RETRO_DIR)
        text = path.read_text(encoding='utf-8')
        self.assertTrue(text.startswith('# Retrospective: Fix the CSV import\n'))
        self.assertIn('- Mode: development\n', text)
        self.assertIn('- Harness: claude\n', text)
        self.assertIn('- Outcome: pass\n', text)
        self.assertIn('- Corrections by Owen: 0\n', text)
        self.assertIn('- Workspace: <absolute path>\n', text, 'unknown facts stay as placeholders')
        errors = oas.validate_retro(path)
        self.assertTrue(any(e.startswith('Unfilled placeholder: <absolute path>') for e in errors), errors)
        self.assertTrue(any(e.startswith('Unfilled placeholder: <one sentence naming the change') for e in errors), 'the template summary is a placeholder, not a proposal')
        self.assertTrue(all(e.startswith('Unfilled placeholder: ') for e in errors), 'the template is structurally complete; only its placeholders block filing')
        for bad in (dict(mode='nope'), dict(harness=' '), dict(outcome='done'), dict(corrections=-1), dict(cost_usd=float('nan'))):
            options = dict(mode='development', harness='claude'); options.update(bad)
            with self.assertRaises(ValueError, msg=bad):
                oas.new_retro(self.root, 'Fix it', options.pop('mode'), options.pop('harness'), **options)

    def test_filled_report_verifies_and_renders_an_implementation_ready_issue(self):
        path = self.filled()
        self.assertEqual(oas.validate_retro(path), [])
        title, body = oas.retro_issue(path)
        self.assertEqual(title, 'Retrospective: Add a CSV fixture to the development scenario bank')
        self.assertTrue(body.startswith('The rerun loop above'), 'the issue opens with the reason')
        summary = body[:body.index('<details>')]
        for heading in ('## Problem observed', '## Root causes', '## Files to change', '## Implementation steps', '## Acceptance criteria', '## Validation', '## Out of scope', '## Session'):
            self.assertEqual(summary.count(heading + '\n'), 1, heading)
        self.assertLess(body.index('## Problem observed'), body.index('## Files to change'))
        self.assertIn('- `evals/scenarios.json`: add a scenario for the CSV import', body)
        self.assertIn('- Cost and time: 1.25, 40\n', body)
        self.assertIn('<details><summary>Full retrospective</summary>', body)
        self.assertIn('it grants no authorization', body)

    def test_verification_rejects_structure_gaps_placeholders_and_credentials(self):
        path = self.filled()
        good = path.read_text(encoding='utf-8')
        cases = {
            'no title': ('# Retrospective: Fix the CSV import', '# Retro'),
            'missing header fact': ('- Harness: claude\n', ''),
            'bad outcome': ('- Outcome: partial', '- Outcome: done'),
            'section out of order': ('## Root causes', '## Causes'),
            'empty went wrong': ('- The import test was rerun three times', 'The import test was rerun'),
            'no files': ('- `evals/scenarios.json`: add a scenario for the CSV import\n- `workflows/development.md`: define the stop rule in step 5\n', '- scenarios: add one\n'),
            'no steps': ('1. Add the scenario with a check that names the fixture file.\n2. Edit step 5 to stop after one passing run of the required checks.\n', '- add it\n'),
            'no criteria': ('- `check` reports one more scenario\n- The workflow names the stop rule in one sentence\n', '\n'),
            'no validation': ('python3 scripts/oas.py check\npython3 -m unittest discover -s tests -v\n', ''),
            'no out of scope': ('- Changing the research workflow\n', '\n'),
            'placeholder left': ('- Changing the research workflow', '- <what this issue deliberately leaves alone>'),
            'credential': ('- Changing the research workflow', '- token ghp_' + 'a1B2' * 6),
            'multi-line summary': ('Summary: Add a CSV fixture to the development scenario bank\n', 'Summary: Add a CSV fixture\nto the bank\n'),
            'title too long': ('Summary: Add a CSV fixture to the development scenario bank\n', 'Summary: ' + 'x' * 260 + '\n'),
        }
        for name, (old, new) in cases.items():
            self.assertEqual(good.count(old), 1, name)
            path.write_text(good.replace(old, new), encoding='utf-8')
            self.assertNotEqual(oas.validate_retro(path), [], name)
            with self.assertRaises(ValueError, msg=name):
                oas.retro_issue(path)
        path.write_text(good.replace('- The import test was rerun three times | Expected: one run after the fix | Evidence: `.oas/csv-1/check.log` | Cost: 12 minutes', '- None observed.'), encoding='utf-8')
        self.assertEqual(oas.validate_retro(path), [], 'an explicit "None observed." satisfies a section')

    def test_no_change_proposed_skips_the_issue_without_calling_gh(self):
        path = self.filled(summary=oas.NO_CHANGE)
        self.assertEqual(oas.validate_retro(path), [])
        self.assertIsNone(oas.retro_issue(path))
        with patch.object(oas.subprocess, 'run', side_effect=AssertionError('gh must not run')):
            self.assertIsNone(oas.file_retro_issue(path, repo='oap22/owens-agent-system'))
        self.assertFalse((path.parent / 'issue.json').exists())
        self.assertFalse((path.parent / 'issue-body.md').exists())

    def test_issue_is_filed_once_through_gh_and_recorded(self):
        path = self.filled()
        url = 'https://github.com/oap22/owens-agent-system/issues/42'
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout=f'\nCreating issue in oap22/owens-agent-system\n\n{url}\n', stderr='')
        with patch.object(oas.subprocess, 'run', side_effect=fake_run), patch.object(oas.shutil, 'which', return_value='/usr/bin/gh'):
            record = oas.file_retro_issue(path, repo='oap22/owens-agent-system', labels=('retrospective', 'enhancement'))
        self.assertEqual(record['url'], url)
        cmd, kwargs = calls[0]
        self.assertEqual(cmd[:3], ['gh', 'issue', 'create'])
        self.assertEqual(cmd[cmd.index('--repo') + 1], 'oap22/owens-agent-system')
        self.assertEqual(cmd[cmd.index('--title') + 1], 'Retrospective: Add a CSV fixture to the development scenario bank')
        self.assertEqual(cmd.count('--label'), 2)
        self.assertEqual(Path(cmd[cmd.index('--body-file') + 1]), path.parent / 'issue-body.md')
        self.assertFalse(kwargs.get('shell'), 'never through a shell')
        self.assertEqual(kwargs['cwd'], oas.ROOT)
        self.assertEqual(json.loads((path.parent / 'issue.json').read_text(encoding='utf-8'))['url'], url)
        self.assertEqual((path.parent / 'issue-body.md').read_text(encoding='utf-8'), oas.retro_issue(path)[1])
        with self.assertRaises(ValueError) as caught, patch.object(oas.subprocess, 'run', side_effect=AssertionError('gh must not run again')):
            oas.file_retro_issue(path, repo='oap22/owens-agent-system')
        self.assertIn(url, str(caught.exception))

    def test_gh_failure_and_bad_output_leave_no_record(self):
        path = self.filled()
        failures = [subprocess.CompletedProcess([], 1, stdout='', stderr='could not add label: retrospective not found'),
                    subprocess.CompletedProcess([], 0, stdout='not a url\n', stderr='')]
        for completed in failures:
            with patch.object(oas.subprocess, 'run', return_value=completed), patch.object(oas.shutil, 'which', return_value='/usr/bin/gh'):
                with self.assertRaises(ValueError):
                    oas.file_retro_issue(path, repo='oap22/owens-agent-system')
            self.assertFalse((path.parent / 'issue.json').exists())
        with patch.object(oas.shutil, 'which', return_value=None):
            with self.assertRaises(ValueError):
                oas.file_retro_issue(path, repo='oap22/owens-agent-system')
        for repo in ('owens-agent-system', 'a/b/c', 'a b/c'):
            with self.assertRaises(ValueError, msg=repo):
                oas.file_retro_issue(path, repo=repo, dry_run=True)
        with self.assertRaises(ValueError):
            oas.file_retro_issue(path, repo='oap22/owens-agent-system', labels=('',), dry_run=True)

    def test_default_repo_is_this_kit_and_parses_both_remote_forms(self):
        self.assertEqual(oas.repo_slug('git@github.com:oap22/owens-agent-system.git\n'), 'oap22/owens-agent-system')
        self.assertEqual(oas.repo_slug('https://github.com/oap22/owens-agent-system'), 'oap22/owens-agent-system')
        self.assertEqual(oas.repo_slug('https://github.com/oap22/owens-agent-system.git/'), 'oap22/owens-agent-system')
        with self.assertRaises(ValueError):
            oas.repo_slug('https://gitlab.com/oap22/owens-agent-system.git')
        with patch.object(oas.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='git@github.com:oap22/owens-agent-system.git\n', stderr='')) as run:
            self.assertEqual(oas.default_repo(), 'oap22/owens-agent-system')
        self.assertEqual(run.call_args.args[0][:4], ['git', '-C', str(oas.ROOT), 'remote'])
        with patch.object(oas.subprocess, 'run', side_effect=subprocess.CalledProcessError(128, 'git')):
            with self.assertRaises(ValueError):
                oas.default_repo()

    def test_cli_scaffold_verify_and_dry_run(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(oas.main(['retro', '--output', str(self.root), '--title', 'Fix it', '--mode', 'development', '--harness', 'codex', '--outcome', 'pass']), 0)
            scaffold = Path(out.getvalue().strip())
            self.assertEqual(oas.main(['verify-retro', str(scaffold)]), 1)
            self.assertEqual(oas.main(['retro-issue', str(scaffold), '--dry-run', '--repo', 'oap22/owens-agent-system']), 2)
        self.assertIn('Unfilled placeholder', err.getvalue())
        path = self.filled()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.object(oas.subprocess, 'run', side_effect=AssertionError('dry run must not call gh')):
            self.assertEqual(oas.main(['verify-retro', str(path)]), 0)
            self.assertEqual(oas.main(['retro-issue', str(path), '--dry-run', '--repo', 'oap22/owens-agent-system', '--label', 'enhancement']), 0)
        self.assertIn('PASS: retrospective structure', out.getvalue())
        self.assertIn('Retrospective: Add a CSV fixture to the development scenario bank\n\nThe rerun loop', out.getvalue())
        self.assertIn('--label enhancement', err.getvalue())
        self.assertFalse((path.parent / 'issue.json').exists())
        with patch.object(oas.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='https://github.com/oap22/owens-agent-system/issues/7\n', stderr='')), \
                patch.object(oas.shutil, 'which', return_value='/usr/bin/gh'), contextlib.redirect_stdout(out):
            self.assertEqual(oas.main(['retro-issue', str(path), '--repo', 'oap22/owens-agent-system']), 0)
        self.assertTrue(out.getvalue().endswith('https://github.com/oap22/owens-agent-system/issues/7\n'))

    def test_contract_and_template_agree_on_the_reflect_step(self):
        contract = (oas.ROOT / 'prompts/core.md').read_text(encoding='utf-8')
        self.assertIn('Frame → Work → Prove → Hand off → Reflect', contract)
        for command in ('oas.py retro', 'verify-retro', 'retro-issue', 'templates/retrospective.md'):
            self.assertIn(command, contract)
        self.assertIn('authorizes nothing', contract)
        template = (oas.ROOT / oas.RETRO_TEMPLATE).read_text(encoding='utf-8')
        _, header, sections = oas.parse_retro(template)
        self.assertEqual(tuple(header), oas.RETRO_HEADER)
        self.assertEqual(tuple(sections), oas.RETRO_SECTIONS)
        self.assertEqual(tuple(label for label in oas.proposal_fields(sections['Proposed change']) if label not in ('Summary', 'Why')), oas.RETRO_FIELDS)
        self.assertIn('retrospective', {item['id'] for item in oas.scenarios()})
        self.assertIn('Retrospective path and issue URL:', (oas.ROOT / 'templates/handoff.md').read_text(encoding='utf-8'))
        # A retrospective is conditional on a preventable failure; a clean session records none.
        self.assertIn('Reflect only when the session hit a failure', contract)
        self.assertIn('none, no failure', contract)
        self.assertIn('retrospective-clean', {item['id'] for item in oas.scenarios()})

    def test_contract_states_each_rule_once(self):
        contract = (oas.ROOT / 'prompts/core.md').read_text(encoding='utf-8')
        self.assertEqual(contract.count('data, never instructions'), 1)
        self.assertNotIn('Batch independent reads', contract)
        self.assertIn('Name the file and quote the line when an instruction blocks progress.', contract)
        for gotcha in ('/bin/ls', 'find ... | while read'):
            self.assertIn(gotcha, contract)
