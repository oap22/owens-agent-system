#!/usr/bin/env python3
"""Portable agent workflow launcher. Standard library only; never uses a shell."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODES = ('development', 'research', 'ops', 'tutor', 'unattended')
AGENTS = ('codex', 'claude', 'cursor', 'gemini', 'copilot', 'opencode', 'generic')
# Markers and native global instruction paths shared with scripts/setup.py.
MANAGED_START = '<!-- owens-agent-system:start -->'
MANAGED_END = '<!-- owens-agent-system:end -->'
GLOBAL_INSTRUCTIONS = {
    'codex': '.codex/AGENTS.md',
    'claude': '.claude/CLAUDE.md',
    'gemini': '.gemini/GEMINI.md',
    'copilot': '.copilot/copilot-instructions.md',
    'opencode': '.config/opencode/AGENTS.md',
    'cursor': '.cursor/rules/owens-agent-system.mdc',
}
SHARED_PROMPTS = ('prompts/core.md', 'prompts/owen.md')


def merge(base, overlay):
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else copy.deepcopy(value)
    return result


def config(mode):
    if mode not in MODES:
        raise ValueError('Unknown mode')
    with (ROOT / 'config/config.toml').open('rb') as f:
        base = tomllib.load(f)
    with (ROOT / f'config/profiles/{mode}.toml').open('rb') as f:
        result = merge(base, tomllib.load(f))
    for value in result.get('agents', {}).values():
        if isinstance(value, dict) and 'config_file' in value:
            path = (ROOT / 'config' / value['config_file']).resolve()
            if not path.is_relative_to(ROOT / 'config/agents') or not path.is_file():
                raise ValueError('Role config is missing or outside config/agents')
            value['config_file'] = str(path)
    return result


def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(toml_value(v) for v in value) + ']'
    raise ValueError(f'Unsupported TOML value type: {type(value).__name__}')


def flatten(data, prefix=''):
    for key, value in data.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
            raise ValueError('Unsupported configuration key')
        name = prefix + key
        if isinstance(value, dict):
            yield from flatten(value, name + '.')
        else:
            yield name, value


def overrides(mode):
    result = []
    for key, value in flatten(config(mode)):
        result.extend(['-c', f'{key}={toml_value(value)}'])
    return result


def prompt(mode, task):
    if mode not in MODES or not task.strip():
        raise ValueError('A valid mode and nonempty task are required')
    parts = [(ROOT / p).read_text() for p in ('prompts/core.md', 'prompts/owen.md', f'workflows/{mode}.md')]
    return '\n\n'.join(parts) + '\n\n# Current user task\n\n' + task


def workspace_path(value):
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Workspace must be an existing directory')
    return path


def command(agent, mode, workspace, task):
    workspace = workspace_path(workspace)
    message = prompt(mode, task)
    if agent not in AGENTS or agent == 'generic':
        raise ValueError('Generic agents use bundle, not run; select a native adapter')
    if mode == 'unattended' and agent != 'codex':
        raise ValueError('Unattended permission mapping is only implemented for Codex; use bundle to design a native audited job')
    if agent == 'codex':
        return ['codex', '--strict-config', *overrides(mode), '-C', str(workspace), message]
    if agent == 'claude':
        native_mode = 'plan' if mode == 'tutor' else ('manual' if mode == 'ops' else 'acceptEdits')
        return ['claude', '--settings', str(ROOT / 'adapters/claude/settings.json'), '--permission-mode', native_mode, message]
    if agent == 'cursor':
        args = ['cursor-agent', '--workspace', str(workspace), '--sandbox', 'enabled']
        if mode == 'tutor':
            args += ['--mode', 'ask']
        elif mode != 'ops':
            args += ['--auto-review']
        return args + [message]
    if agent == 'gemini':
        return ['gemini', '--sandbox', '--approval-mode', 'plan' if mode == 'tutor' else 'default', '--prompt-interactive', message]
    if agent == 'opencode':
        return ['opencode', str(workspace), '--agent', 'plan' if mode == 'tutor' else 'build', '--prompt', message]
    args = ['copilot', '--mode', 'plan' if mode == 'tutor' else 'interactive']
    if mode == 'tutor':
        args += ['--deny-tool', 'write', '--deny-tool', 'shell']
    return args + ['--interactive', message]


def new_file(path, content):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation rejects existing files and symlinks, including broken ones.
    with path.open('x', encoding='utf-8') as f:
        f.write(content)
    return path


def new_task(mode, output, title, criteria):
    if mode not in MODES or not title.strip() or not criteria or any(not x.strip() for x in criteria):
        raise ValueError('Task requires a valid mode, title, and nonempty acceptance criteria')
    ident = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    folder = Path(output).expanduser().resolve() / ident
    folder.mkdir(parents=True, exist_ok=False)
    record = dict(schema_version=1, id=ident, mode=mode, title=title, status='planned',
                  owner='Owen', authorized_actions=[], writable_scope=[],
                  criteria=[dict(description=c, passed=False, evidence=[]) for c in criteria],
                  checkpoint=dict(completed=[], blockers=[], next_action='Confirm scope and begin', commit=None),
                  budget=dict(max_minutes=None, max_iterations=None),
                  idempotency_key=ident, retry_limit=0)
    new_file(folder / 'task.json', json.dumps(record, indent=2) + '\n')
    new_file(folder / 'handoff.md', '# Handoff\n\nOutcome:\n\nEvidence:\n\nRemaining work:\n\nNext action:\n')
    return folder


def validate_task(path):
    path = Path(path).resolve(strict=True)
    data = json.loads(path.read_text())
    errors = []
    if not isinstance(data, dict):
        return ['Task must be a JSON object']
    for field in ('id', 'title', 'owner'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f'{field} must be a nonempty string')
    if data.get('schema_version') != 1 or data.get('mode') not in MODES:
        errors.append('Unsupported schema or mode')
    if data.get('status') not in ('planned', 'active', 'blocked', 'complete'):
        errors.append('Invalid status')
    criteria = data.get('criteria')
    if not isinstance(criteria, list) or not criteria:
        return errors + ['Nonempty criteria list required']
    complete = data.get('status') == 'complete'
    if data.get('mode') == 'unattended' and data.get('status') != 'planned':
        for field in ('authorized_actions', 'writable_scope'):
            values = data.get(field)
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                errors.append(f'Unattended task requires explicit {field}')
        budget = data.get('budget')
        if not isinstance(budget, dict) or any(type(budget.get(k)) is not int or budget[k] <= 0 for k in ('max_minutes', 'max_iterations')):
            errors.append('Unattended task requires positive time and iteration limits')
        if type(data.get('retry_limit')) is not int or data['retry_limit'] < 0:
            errors.append('Unattended task requires a nonnegative retry limit')
        if not isinstance(data.get('idempotency_key'), str) or not data['idempotency_key'].strip():
            errors.append('Unattended task requires an idempotency key')
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, dict):
            errors.append(f'Criterion {index}: must be an object')
            continue
        if not isinstance(criterion.get('description'), str) or not criterion['description'].strip():
            errors.append(f'Criterion {index}: description required')
        passed = criterion.get('passed')
        evidence = criterion.get('evidence')
        if not isinstance(passed, bool) or not isinstance(evidence, list):
            errors.append(f'Criterion {index}: boolean passed and evidence list required')
            continue
        if (passed or complete) and not evidence:
            errors.append(f'Criterion {index}: evidence required')
        if complete and not passed:
            errors.append(f'Criterion {index}: incomplete')
        for item in evidence:
            if not isinstance(item, str) or not item.strip():
                errors.append(f'Criterion {index}: invalid evidence path')
                continue
            candidate = (path.parent / item).resolve()
            if Path(item).is_absolute() or not candidate.is_relative_to(path.parent):
                errors.append(f'Criterion {index}: evidence must stay inside task directory')
            elif not candidate.is_file() or candidate.stat().st_size == 0:
                errors.append(f'Criterion {index}: missing or empty evidence artifact')
    checkpoint = data.get('checkpoint')
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get('blockers'), list):
        errors.append('Checkpoint with blockers list required')
    elif complete and checkpoint['blockers']:
        errors.append('Complete task still has blockers')
    return errors


def bundle(mode, agent, output, task):
    if agent not in AGENTS:
        raise ValueError('Unknown agent')
    folder = Path(output).expanduser()
    # Require a fresh destination: no existing project files can be replaced.
    folder.mkdir(parents=True, exist_ok=False)
    name = {'codex':'AGENTS.md', 'claude':'CLAUDE.md', 'gemini':'GEMINI.md',
            'copilot':'.github/copilot-instructions.md', 'cursor':'.cursor/rules/owen-agent-system.mdc',
            'opencode':'AGENTS.md', 'generic':'AGENTS.md'}[agent]
    content = prompt(mode, task)
    if agent == 'cursor':
        content = '---\ndescription: Owen working system\nalwaysApply: true\n---\n\n' + content
    new_file(folder / name, content)
    new_file(folder / 'PERMISSIONS.md', f'# Runtime permissions\n\nTarget: {agent}. Mode: {mode}.\n\nThis bundle contains instructions only. It grants no runtime permission. Configure and verify the native agent controls described in the source repository docs/adapters.md. Do not replace existing workspace instructions without reviewing the merge.\n')
    return folder


def check():
    for mode in MODES:
        cfg = config(mode)
        assert cfg['sandbox_mode'] != 'danger-full-access'
        assert cfg['sandbox_workspace_write']['network_access'] is False
        assert cfg['sandbox_workspace_write']['writable_roots'] == []
        prompt(mode, 'validation')
    for path in (ROOT / 'config/agents').glob('*.toml'):
        tomllib.loads(path.read_text())
    scenarios = json.loads((ROOT / 'evals/scenarios.json').read_text())
    assert len({s['id'] for s in scenarios}) == len(scenarios)
    assert all(s['mode'] in MODES and s['expected'] and s['checks'] for s in scenarios)
    json.loads((ROOT / 'adapters/claude/settings.json').read_text())
    print(f'PASS: {len(MODES)} profiles, 3 roles, {len(scenarios)} evaluation scenarios')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('check')
    for name in ('preview', 'run'):
        p = sub.add_parser(name)
        p.add_argument('mode', choices=MODES)
        p.add_argument('--agent', choices=AGENTS, default='codex')
        p.add_argument('--workspace', required=True)
        p.add_argument('--task', required=True)
    p = sub.add_parser('doctor')
    p.add_argument('mode', choices=MODES)
    p = sub.add_parser('export', help='Export Codex settings without overwriting')
    p.add_argument('mode', choices=MODES)
    p.add_argument('--output', required=True)
    p = sub.add_parser('bundle', help='Generate standalone native instruction files')
    p.add_argument('mode', choices=MODES)
    p.add_argument('--agent', choices=AGENTS, default='generic')
    p.add_argument('--output', required=True)
    p.add_argument('--task', default='Follow this workflow for the user\'s next request.')
    p = sub.add_parser('task')
    p.add_argument('mode', choices=MODES)
    p.add_argument('--output', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--criterion', action='append', required=True)
    p = sub.add_parser('verify-task')
    p.add_argument('path')
    args = parser.parse_args(argv)
    try:
        if args.action == 'check':
            check()
        elif args.action == 'task':
            print(new_task(args.mode, args.output, args.title, args.criterion))
        elif args.action == 'verify-task':
            errors = validate_task(args.path)
            if errors:
                print('\n'.join(errors), file=sys.stderr)
                return 1
            print('PASS: record structure and evidence files; semantic correctness not assessed')
        elif args.action == 'bundle':
            print(bundle(args.mode, args.agent, args.output, args.task))
        elif args.action == 'export':
            content = '# Generated Codex profile; role paths depend on this clone location.\n'
            content += '\n'.join(f'{k} = {toml_value(v)}' for k,v in flatten(config(args.mode))) + '\n'
            tomllib.loads(content)
            print(new_file(args.output, content))
        elif args.action == 'doctor':
            return subprocess.call(['codex', '--strict-config', *overrides(args.mode), 'doctor', '--summary'], cwd=ROOT)
        else:
            cmd = command(args.agent, args.mode, args.workspace, args.task)
            if args.action == 'preview':
                print(shlex.join(cmd))
            else:
                if not shutil.which(cmd[0]):
                    raise ValueError(f'{cmd[0]} is not installed; use bundle or install its official CLI')
                # Copilot supports permission-bypass environment variables. Fail closed,
                # without silently rewriting the caller's environment.
                if args.agent == 'copilot' and any(os.environ.get(k, '').lower() in ('1', 'true') for k in ('COPILOT_ALLOW_ALL', 'COPILOT_PLAN_THEN_AUTOPILOT')):
                    raise ValueError('Remove Copilot allow-all/autopilot environment overrides before launch')
                return subprocess.call(cmd, cwd=workspace_path(args.workspace))
    except (ValueError, OSError, AssertionError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
