#!/usr/bin/env python3
"""Install global guidance and native defaults with backups. Preview by default."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load_oas(source):
    spec = importlib.util.spec_from_file_location('oas_setup_source', Path(source) / 'scripts/oas.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


oas = load_oas(ROOT)
START, END = oas.MANAGED_START, oas.MANAGED_END
GLOBAL_INSTRUCTIONS = oas.GLOBAL_INSTRUCTIONS
# Rollback actions and the line printed for each.
LABELS = {'restore': 'restore', 'remove': 'remove', 'keep': 'kept (modified since install)', 'absent': 'already absent'}


def managed(original, content):
    block = START + '\n' + content + '\n' + END
    if START in original or END in original:
        if original.count(START) != 1 or original.count(END) != 1 or original.index(START) > original.index(END):
            raise ValueError('Malformed or duplicate managed markers')
        a = original.index(START); b = original.index(END) + len(END)
        return original[:a] + block + original[b:]
    return original + ('\n\n' if original else '') + block + '\n'


def merged(base, overlay):
    out = dict(base)
    for k, v in overlay.items():
        out[k] = merged(out.get(k, {}), v) if isinstance(v, dict) else v
    return out


def refuse_symlink(home, target, relative):
    if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != home and p.is_relative_to(home)):
        raise ValueError(f'Refusing symlink target: {relative}')


def plan(home, source):
    home, source = Path(home).resolve(), Path(source).resolve()
    src = oas if source == ROOT else load_oas(source)
    guidance = '\n\n'.join((source / f).read_text(encoding='utf-8') for f in src.SHARED_PROMPTS)
    guidance += '\n\n# Workflow selection\n\n'
    guidance += f'The system source is `{source}`. Read only the relevant workflow from its `workflows/` directory: development, research, ops, tutor, or unattended. For mixed requests, use the matching sections. Existing explicit personal instructions outside this managed block and applicable project instructions take precedence over these defaults, especially worktree choices and plan-before-code preferences. Do not auto-run an unattended job.\n'
    changes = []
    def add(relative, content, executable=False):
        target = home / relative
        refuse_symlink(home, target, relative)
        before = target.read_bytes() if target.exists() else None
        after = content(before.decode('utf-8') if before is not None else '').encode('utf-8')
        if before != after:
            changes.append((target, before, after, executable))
    # OpenCode falls back to Claude's global instructions; preserve that personal
    # preamble when adding its own global file for the first time. Cursor needs
    # rule frontmatter when its file is new.
    old_claude = home / src.GLOBAL_INSTRUCTIONS['claude']
    fallbacks = {
        'opencode': old_claude.read_text(encoding='utf-8').split(START)[0] if old_claude.exists() else '',
        'cursor': '---\ndescription: Owen research, development, operations and learning defaults\nalwaysApply: true\n---\n',
    }
    for agent, relative in src.GLOBAL_INSTRUCTIONS.items():
        add(relative, lambda old, agent=agent: managed(old or fallbacks.get(agent, ''), guidance))
    for mode in src.MODES:
        body = '# Owen agent system profile\n' + '\n'.join(f'{k} = {src.toml_value(v)}' for k,v in src.flatten(src.config(mode))) + '\n'
        def profile(old, body=body):
            if old and not old.startswith('# Owen agent system profile\n'):
                raise ValueError('Refusing to replace an unmanaged Codex profile')
            return body
        add(f'.codex/owen-{mode}.config.toml', profile)
    patches = {
        '.claude/settings.json': {'permissions': {'disableBypassPermissionsMode':'disable'}},
        '.cursor/cli-config.json': {'sandbox': {'mode':'enabled'},'approvalMode':'allowlist'},
        '.config/opencode/opencode.json': {
            'permission':{'*':'ask','read':'allow','glob':'allow','grep':'allow','list':'allow','edit':'allow','external_directory':'ask','doom_loop':'ask'},
            'compaction':{'auto':True},
        },
    }
    for relative, patch in patches.items():
        def update(old, patch=patch):
            base = json.loads(old) if old.strip() else {}
            return json.dumps(merged(base, patch), indent=2) + '\n'
        add(relative, update)
    wrapper = '#!/bin/sh\n# Owen agent system launcher\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(source / 'scripts/oas.py')) + ' "$@"\n'
    def launcher(old):
        if old and '# Owen agent system launcher\n' not in old:
            raise ValueError('Refusing to replace an unmanaged oas executable')
        return wrapper
    add('.local/bin/oas', launcher, True)
    return changes


def write_atomic(target, data, mode):
    temp = target.with_name(target.name + '.oas-' + uuid.uuid4().hex)
    try:
        with temp.open('xb') as f:
            os.chmod(temp, mode); f.write(data)
        os.replace(temp, target)
    finally:
        if temp.exists(): temp.unlink()


def apply(changes, home):
    home = Path(home).resolve()
    for target, before, _, _ in changes:
        if (target.read_bytes() if target.exists() else None) != before:
            raise ValueError(f'File changed since planning: {target.name}')
    if not changes:
        return None
    backup = home / '.local/state/owens-agent-system/backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    records = []
    for target, before, after, executable in changes:
        rel = target.relative_to(home)
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else (0o755 if executable else 0o600)
        if before is not None:
            dest = backup / rel; dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(before); os.chmod(dest, 0o600)
        records.append(dict(path=str(rel), existed=before is not None, mode=mode, installed_sha256=hashlib.sha256(after).hexdigest()))
    (backup / 'manifest.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
    done = []
    try:
        for (target,before,after,executable), record in zip(changes,records):
            if (target.read_bytes() if target.exists() else None) != before:
                raise ValueError(f'Concurrent change: {target.name}')
            target.parent.mkdir(parents=True,exist_ok=True)
            write_atomic(target, after, 0o755 if executable else record['mode'])
            done.append((target,before,record['mode']))
    except Exception:
        for target,before,mode in reversed(done):
            if before is None: target.unlink()
            else: target.write_bytes(before); os.chmod(target,mode)
        raise
    return backup


def rollback_plan(home, backup):
    """Return (action, target, payload) per manifest record; payload is (bytes, mode) for 'restore'."""
    home, backup = Path(home).resolve(), Path(backup).resolve()
    manifest = backup / 'manifest.json'
    if not manifest.is_file():
        raise ValueError(f'No manifest.json in backup directory: {backup}')
    actions = []
    for record in json.loads(manifest.read_text(encoding='utf-8')):
        rel = record['path']
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError(f'Manifest path must be relative and inside home: {rel!r}')
        target = home / rel
        refuse_symlink(home, target, rel)
        if not target.exists():
            actions.append(('absent', target, None))
        elif record['existed']:
            saved = backup / rel
            if not saved.is_file():
                raise ValueError(f'Backup copy missing: {rel}')
            actions.append(('restore', target, (saved.read_bytes(), record['mode'])))
        elif hashlib.sha256(target.read_bytes()).hexdigest() == record['installed_sha256']:
            actions.append(('remove', target, record['installed_sha256']))
        else:
            actions.append(('keep', target, None))
    return actions


def rollback_apply(actions):
    """Execute a rollback plan. The backup directory is left in place. Returns counts per action."""
    counts = {action: 0 for action in LABELS}
    for action, target, payload in actions:
        if action == 'restore':
            data, mode = payload
            target.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(target, data, mode)
        elif action == 'remove':
            if hashlib.sha256(target.read_bytes()).hexdigest() != payload:
                raise ValueError(f'File changed since planning: {target.name}')
            target.unlink()
        counts[action] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home',type=Path,default=Path.home())
    parser.add_argument('--source',type=Path,default=ROOT)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--rollback',type=Path,metavar='BACKUP_DIR',help='preview (or with --apply, perform) a rollback from this backup directory instead of installing')
    args=parser.parse_args()
    home=args.home.resolve()
    if args.rollback:
        actions=rollback_plan(home,args.rollback)
        for action,target,_ in actions: print(f'{LABELS[action]}: {target.relative_to(home)}')
        if args.apply:
            counts=rollback_apply(actions)
            print('Rolled back: ' + ', '.join(f'{n} {LABELS[a]}' for a,n in counts.items()) + '. Backup kept.')
        else:
            print(f'{len(actions)} records; preview only, re-run with --apply to roll back')
        return
    if args.apply and home == Path.home().resolve() and (args.source / '.git').is_file():
        parser.error('Install from the permanent checkout, not a linked worktree; use --source to select it')
    changes=plan(home,args.source)
    for path,_,_,_ in changes: print(path.relative_to(home))
    print(f'{len(changes)} files to update')
    if args.apply:
        backup=apply(changes,home)
        print(f'Applied. Backup: {backup}' if backup else 'Already current.')

if __name__=='__main__': main()
