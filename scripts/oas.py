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
SHARED_CHOICES = ('auto', 'always', 'never')
DEFAULT_TASK = "Follow this workflow for the user's next request."
MODEL_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._:/-]*'   # aliases, full ids, provider/model, ollama tags
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
TASK_HEADER = '\n\n# Current user task\n\n'
# Effort levels documented for Claude Code; Codex accepts whatever the selected model advertises.
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
IMPLEMENTOR = 'implementor'
IMPLEMENTOR_TOOLS = ['Read', 'Edit', 'Write', 'Grep', 'Glob', 'Bash']
IMPLEMENTOR_MAX_TURNS = 30


def read(path):
    return Path(path).read_text(encoding='utf-8')


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


def overrides(mode, extra=None):
    """Codex -c arguments for MODE; EXTRA is merged in so every key is emitted exactly once."""
    result = []
    for key, value in flatten(merge(config(mode), extra or {})):
        result.extend(['-c', f'{key}={toml_value(value)}'])
    return result


def shared_installed(agent, home=None):
    """True when the agent's global instruction file carries the managed block with the current shared prompts."""
    if agent not in GLOBAL_INSTRUCTIONS:
        return False
    try:
        text = read((Path.home() if home is None else Path(home)) / GLOBAL_INSTRUCTIONS[agent])
        if text.count(MANAGED_START) != 1 or text.count(MANAGED_END) != 1:
            return False
        block = text[text.index(MANAGED_START):text.index(MANAGED_END)]
        return all(read(ROOT / p).strip() in block for p in SHARED_PROMPTS)
    except (OSError, ValueError):
        return False


def shared_decision(agent, shared='auto', home=None):
    """Resolve a --shared choice to (include_shared_prompts, reason)."""
    if shared not in SHARED_CHOICES:
        raise ValueError(f'--shared must be one of {", ".join(SHARED_CHOICES)}')
    if shared != 'auto':
        return shared == 'always', f'--shared {shared}'
    location = GLOBAL_INSTRUCTIONS.get(agent)
    if location is None:
        return True, f'{agent} has no known global instruction file'
    if shared_installed(agent, home):
        return False, f'managed block with current shared prompts found in ~/{location}'
    return True, f'no managed block with current shared prompts in ~/{location}'


def guidance(mode, shared=True):
    if mode not in MODES:
        raise ValueError('Unknown mode')
    workflow = read(ROOT / f'workflows/{mode}.md')
    if not shared:
        return f'Shared guidance is loaded from your global instructions; this is the {mode} workflow.\n\n' + workflow
    return '\n\n'.join([read(ROOT / p) for p in SHARED_PROMPTS] + [workflow])


def prompt(mode, task, shared=True):
    if mode not in MODES or not task.strip():
        raise ValueError('A valid mode and nonempty task are required')
    return guidance(mode, shared) + TASK_HEADER + task


def workspace_path(value):
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except FileNotFoundError:
        raise ValueError(f'Workspace not found: {value} (if this is ".", your shell\'s current directory may no longer exist; cd to a real directory)') from None
    if not path.is_dir():
        raise ValueError('Workspace must be an existing directory')
    return path


def role(name):
    """Parsed role layer from config/agents/NAME.toml."""
    return tomllib.loads(read(ROOT / f'config/agents/{name}.toml'))


def delegation(mode, lead_effort=None, worker_model=None, worker_effort=None):
    """Validate lead/worker options; return (lead_effort, worker) where worker is a dict or None."""
    for value in (lead_effort, worker_effort):
        if value is not None and value not in EFFORTS:
            raise ValueError(f'Effort must be one of {", ".join(EFFORTS)}')
    if worker_model is not None and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]*', worker_model):
        raise ValueError('Worker model must be a plain alias or model identifier')
    worker = {k: v for k, v in (('model', worker_model), ('effort', worker_effort)) if v is not None}
    if worker and not config(mode).get('agents', {}).get('enabled', False):
        raise ValueError(f'{mode} disables delegation; worker options are not allowed')
    return lead_effort, worker or None


def implementor_agent(worker):
    """Claude Code --agents JSON for the implementor, sharing the Codex role text."""
    layer = role(IMPLEMENTOR)
    spec = dict(description=config('development')['agents'][IMPLEMENTOR]['description'],
                prompt=layer['developer_instructions'].strip(), tools=list(IMPLEMENTOR_TOOLS), maxTurns=IMPLEMENTOR_MAX_TURNS)
    spec.update(worker or {})
    return json.dumps({IMPLEMENTOR: spec}, ensure_ascii=False)


def implementor_overlay(workspace, worker):
    """Write the implementor role layer plus worker overrides under WORKSPACE/.oas/roles and return its path."""
    path = Path(workspace) / '.oas/roles' / f'{IMPLEMENTOR}.toml'
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f'{path} must be a regular file or absent')
    lines = [read(ROOT / f'config/agents/{IMPLEMENTOR}.toml').rstrip(), '# Launch-time worker overrides written by scripts/oas.py; regenerated on every launch.']
    if 'model' in worker:
        lines.append(f'model = {toml_value(worker["model"])}')
    if 'effort' in worker:
        lines.append(f'model_reasoning_effort = {toml_value(worker["effort"])}')
    content = '\n'.join(lines) + '\n'
    tomllib.loads(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def command(agent, mode, workspace, task, shared='auto', home=None, lead_effort=None, worker_model=None, worker_effort=None, model=None):
    workspace = workspace_path(workspace)
    if model is not None and not re.fullmatch(MODEL_PATTERN, model):
        raise ValueError('Model must be a plain alias or model identifier')
    # Every native CLI takes the session model as a flag; None inherits the user's own default.
    model_flag = ['--model', model] if model else []
    include, _ = shared_decision(agent, shared, home)
    # An empty task opens a session that waits for the user: Claude gets no initial
    # prompt, agents that need one get DEFAULT_TASK.
    open_session = not task.strip()
    message = prompt(mode, DEFAULT_TASK if open_session else task, include)
    lead_effort, worker = delegation(mode, lead_effort, worker_model, worker_effort)
    if agent not in AGENTS or agent == 'generic':
        raise ValueError('Generic agents use bundle, not run; select a native adapter')
    if mode == 'unattended' and agent != 'codex':
        raise ValueError('Unattended permission mapping is only implemented for Codex; use bundle to design a native audited job')
    if agent not in ('codex', 'claude') and (lead_effort or worker):
        raise ValueError(f'Lead effort and worker options are implemented for codex and claude only, not {agent}')
    if agent == 'codex':
        extra = {}
        if lead_effort:
            extra['model_reasoning_effort'] = lead_effort
        if worker:
            extra['agents'] = {IMPLEMENTOR: {'config_file': str(implementor_overlay(workspace, worker))}}
        return ['codex', '--strict-config', *overrides(mode, extra), *model_flag, '-C', str(workspace), message]
    if agent == 'claude':
        native_mode = 'plan' if mode == 'tutor' else ('manual' if mode == 'ops' else 'acceptEdits')
        # Guidance is system-level context for Claude Code; the raw task is the user turn.
        if task.lstrip().startswith('-'):
            raise ValueError('Claude receives the task as a positional prompt; it must not start with a dash')
        args = ['claude', '--settings', str(ROOT / 'adapters/claude/settings.json'), '--permission-mode', native_mode, *model_flag]
        if lead_effort:
            args += ['--effort', lead_effort]
        if worker:
            args += ['--agents', implementor_agent(worker)]
        return args + ['--append-system-prompt', guidance(mode, include)] + ([] if open_session else [task])
    if agent == 'cursor':
        args = ['cursor-agent', '--workspace', str(workspace), '--sandbox', 'enabled', *model_flag]
        if mode == 'tutor':
            args += ['--mode', 'ask']
        elif mode != 'ops':
            args += ['--auto-review']
        return args + [message]
    if agent == 'gemini':
        return ['gemini', '--sandbox', '--approval-mode', 'plan' if mode == 'tutor' else 'default', *model_flag, '--prompt-interactive', message]
    if agent == 'opencode':
        return ['opencode', str(workspace), '--agent', 'plan' if mode == 'tutor' else 'build', *model_flag, '--prompt', message]
    args = ['copilot', '--mode', 'plan' if mode == 'tutor' else 'interactive', *model_flag]
    if mode == 'tutor':
        args += ['--deny-tool', 'write', '--deny-tool', 'shell']
    return args + ['--interactive', message]


def launch_command(agent, mode, workspace, task, shared='auto', home=None, **options):
    cmd = command(agent, mode, workspace, task, shared, home, **options)
    if not shutil.which(cmd[0]):
        raise ValueError(f'{cmd[0]} is not installed; use bundle or install its official CLI')
    # Copilot supports permission-bypass environment variables. Fail closed,
    # without silently rewriting the caller's environment.
    if agent == 'copilot' and any(os.environ.get(k, '').lower() in ('1', 'true') for k in ('COPILOT_ALLOW_ALL', 'COPILOT_PLAN_THEN_AUTOPILOT')):
        raise ValueError('Remove Copilot allow-all/autopilot environment overrides before launch')
    return cmd


def launch(agent, mode, workspace, task, shared='auto', **options):
    return subprocess.call(launch_command(agent, mode, workspace, task, shared, **options), cwd=workspace_path(workspace))


def interactive_default(argv, stdin=None, stdout=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    if not argv and stdin.isatty() and stdout.isatty():
        return ['ui']
    return argv


def new_file(path, content):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation rejects existing files and symlinks, including broken ones.
    with path.open('x', encoding='utf-8') as f:
        f.write(content)
    return path


def scenarios():
    return json.loads(read(ROOT / 'evals/scenarios.json'))


def scenario(ident):
    for item in scenarios():
        if item['id'] == ident:
            return item
    raise ValueError(f'Unknown scenario: {ident}')


def new_task(mode, output, title, criteria, scenario_id=None):
    if scenario_id is not None:
        item = scenario(scenario_id)
        if mode not in (None, item['mode']):
            raise ValueError(f'Scenario {scenario_id} uses mode {item["mode"]}, not {mode}')
        mode = item['mode']
        title = title or item['prompt']
        criteria = criteria or list(item['expected']) + list(item['checks'])
    if mode not in MODES or not isinstance(title, str) or not title.strip() or not criteria or any(not isinstance(x, str) or not x.strip() for x in criteria):
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
    if scenario_id is not None:
        record['scenario'] = scenario_id
    new_file(folder / 'task.json', json.dumps(record, indent=2) + '\n')
    new_file(folder / 'handoff.md', '# Handoff\n\nOutcome:\n\nEvidence:\n\nRemaining work:\n\nNext action:\n')
    return folder


def validate_task(path):
    path = Path(path).resolve(strict=True)
    data = json.loads(read(path))
    errors = []
    if not isinstance(data, dict):
        return ['Task must be a JSON object']
    for field in ('id', 'title', 'owner'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f'{field} must be a nonempty string')
    if 'scenario' in data and (not isinstance(data['scenario'], str) or not data['scenario'].strip()):
        errors.append('scenario must be a nonempty string when present')
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


def bundle(mode, agent, output, task, shared=True):
    if agent not in AGENTS:
        raise ValueError('Unknown agent')
    folder = Path(output).expanduser()
    # Require a fresh destination: no existing project files can be replaced.
    folder.mkdir(parents=True, exist_ok=False)
    name = {'codex':'AGENTS.md', 'claude':'CLAUDE.md', 'gemini':'GEMINI.md',
            'copilot':'.github/copilot-instructions.md', 'cursor':'.cursor/rules/owen-agent-system.mdc',
            'opencode':'AGENTS.md', 'generic':'AGENTS.md'}[agent]
    content = prompt(mode, task, shared)
    if agent == 'cursor':
        content = '---\ndescription: Owen working system\nalwaysApply: true\n---\n\n' + content
    new_file(folder / name, content)
    new_file(folder / 'PERMISSIONS.md', f'# Runtime permissions\n\nTarget: {agent}. Mode: {mode}.\n\nThis bundle contains instructions only. It grants no runtime permission. Configure and verify the native agent controls described in the source repository docs/adapters.md. Do not replace existing workspace instructions without reviewing the merge.\n')
    return folder


def routed_skills():
    """Skill names referenced by `Skill routing:` lines in the workflows."""
    names = set()
    for path in sorted((ROOT / 'workflows').glob('*.md')):
        for line in read(path).splitlines():
            if line.startswith('Skill routing:'):
                names.update(re.findall(r'`([^`]+)`', line))
    return names


def check(skills_root=None):
    for mode in MODES:
        cfg = config(mode)
        if cfg['sandbox_mode'] == 'danger-full-access':
            raise ValueError(f'{mode}: sandbox_mode must not be danger-full-access')
        if cfg['sandbox_workspace_write']['network_access'] is not False:
            raise ValueError(f'{mode}: sandbox_workspace_write.network_access must be false')
        if cfg['sandbox_workspace_write']['writable_roots'] != []:
            raise ValueError(f'{mode}: sandbox_workspace_write.writable_roots must be empty')
        prompt(mode, 'validation')
    roles = [tomllib.loads(read(path)) for path in sorted((ROOT / 'config/agents').glob('*.toml'))]
    items = scenarios()
    if len({s['id'] for s in items}) != len(items):
        raise ValueError('Evaluation scenario ids must be unique')
    if not all(s['mode'] in MODES and s['expected'] and s['checks'] for s in items):
        raise ValueError('Every evaluation scenario needs a valid mode, expected list, and checks list')
    json.loads(read(ROOT / 'adapters/claude/settings.json'))
    if IMPLEMENTOR not in config('development')['agents'] or not role(IMPLEMENTOR).get('developer_instructions', '').strip():
        raise ValueError('The implementor role must be registered with nonempty developer_instructions')
    json.loads(implementor_agent({'effort': 'low'}))
    skills_root = Path.home() / 'Developer/active/skills/skills' if skills_root is None else Path(skills_root)
    if skills_root.is_dir():
        for name in sorted(routed_skills()):
            if not (skills_root / name).is_dir():
                print(f'WARNING: routed skill `{name}` has no directory under {skills_root}', file=sys.stderr)
    else:
        print('skills repo not present; routing check skipped', file=sys.stderr)
    print(f'PASS: {len(MODES)} profiles, {len(roles)} roles, {len(items)} evaluation scenarios')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('check')
    p.add_argument('--skills-root', help='Skills directory for routing drift check (default: ~/Developer/active/skills/skills)')
    for name in ('preview', 'run'):
        p = sub.add_parser(name)
        p.add_argument('mode', choices=MODES)
        p.add_argument('--agent', choices=AGENTS, default='codex')
        p.add_argument('--workspace', required=True)
        p.add_argument('--task', required=True)
        p.add_argument('--shared', choices=SHARED_CHOICES, default='auto', help='Include shared prompts; auto omits them when the agent\'s global instructions carry them')
        p.add_argument('--model', help='Session model alias or id for the agent; omit to inherit your current default')
        p.add_argument('--lead-effort', choices=EFFORTS, help='Reasoning effort for the lead session (codex and claude only)')
        p.add_argument('--worker-model', help='Model alias or identifier for the implementor role (codex and claude only)')
        p.add_argument('--worker-effort', choices=EFFORTS, help='Reasoning effort for the implementor role (codex and claude only)')
    p = sub.add_parser('doctor')
    p.add_argument('mode', choices=MODES)
    p = sub.add_parser('export', help='Export Codex settings without overwriting')
    p.add_argument('mode', choices=MODES)
    p.add_argument('--output', required=True)
    p = sub.add_parser('bundle', help='Generate standalone native instruction files')
    p.add_argument('mode', choices=MODES)
    p.add_argument('--agent', choices=AGENTS, default='generic')
    p.add_argument('--output', required=True)
    p.add_argument('--task', default=DEFAULT_TASK)
    p.add_argument('--shared', choices=SHARED_CHOICES, default='always')
    p = sub.add_parser('task')
    p.add_argument('mode', nargs='?', choices=MODES)
    p.add_argument('--output', required=True)
    p.add_argument('--title')
    p.add_argument('--criterion', action='append')
    p.add_argument('--scenario', help='Take mode, title, and criteria from this evals/scenarios.json id')
    p = sub.add_parser('verify-task')
    p.add_argument('path')
    p = sub.add_parser('ui')
    p.add_argument('--plain', action='store_true', help='Disable rain and color; monochrome panels')
    argv = interactive_default(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)
    try:
        if args.action == 'check':
            check(args.skills_root)
        elif args.action == 'task':
            if args.scenario is None and (args.mode is None or args.title is None or not args.criterion):
                raise ValueError('mode, --title, and --criterion are required unless --scenario is given')
            print(new_task(args.mode, args.output, args.title, args.criterion, args.scenario))
        elif args.action == 'verify-task':
            errors = validate_task(args.path)
            if errors:
                print('\n'.join(errors), file=sys.stderr)
                return 1
            print('PASS: record structure and evidence files; semantic correctness not assessed')
        elif args.action == 'bundle':
            include, _ = shared_decision(args.agent, args.shared)
            print(bundle(args.mode, args.agent, args.output, args.task, include))
        elif args.action == 'export':
            content = '# Generated Codex profile; role paths depend on this clone location.\n'
            content += '\n'.join(f'{k} = {toml_value(v)}' for k,v in flatten(config(args.mode))) + '\n'
            tomllib.loads(content)
            print(new_file(args.output, content))
        elif args.action == 'doctor':
            return subprocess.call(['codex', '--strict-config', *overrides(args.mode), 'doctor', '--summary'], cwd=ROOT)
        elif args.action == 'ui':
            _here = Path(__file__).resolve().parent
            if str(_here) not in sys.path:
                sys.path.insert(0, str(_here))
            import oas_screen
            return oas_screen.run_ui(plain=args.plain)
        elif args.action == 'preview':
            workspace = workspace_path(args.workspace)
            cmd = command(args.agent, args.mode, workspace, args.task, args.shared,
                          lead_effort=args.lead_effort, worker_model=args.worker_model, worker_effort=args.worker_effort, model=args.model)
            include, reason = shared_decision(args.agent, args.shared)
            print(f'shared guidance {"included" if include else "omitted"}: {reason}', file=sys.stderr)
            print(shlex.join(cmd))
        else:
            return launch(args.agent, args.mode, args.workspace, args.task, args.shared,
                          lead_effort=args.lead_effort, worker_model=args.worker_model, worker_effort=args.worker_effort, model=args.model)
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
