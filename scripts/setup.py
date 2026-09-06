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

START = '<!-- owens-agent-system:start -->'
END = '<!-- owens-agent-system:end -->'


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


def plan(home, source):
    home, source = Path(home).resolve(), Path(source).resolve()
    spec = importlib.util.spec_from_file_location('oas_setup_source', source / 'scripts/oas.py')
    oas = importlib.util.module_from_spec(spec); spec.loader.exec_module(oas)
    guidance = '\n\n'.join((source / 'prompts' / f).read_text() for f in ('core.md','owen.md'))
    guidance += '\n\n# Workflow selection\n\n'
    guidance += f'The system source is `{source}`. Read only the relevant workflow from its `workflows/` directory: development, research, ops, tutor, or unattended. For mixed requests, use the matching sections. Existing explicit personal instructions outside this managed block and applicable project instructions take precedence over these defaults, especially worktree choices and plan-before-code preferences. Do not auto-run an unattended job.\n'
    changes = []
    def add(relative, content, executable=False):
        target = home / relative
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != home and p.is_relative_to(home)):
            raise ValueError(f'Refusing symlink target: {relative}')
        before = target.read_bytes() if target.exists() else None
        after = content(before.decode() if before is not None else '').encode()
        if before != after:
            changes.append((target, before, after, executable))
    for relative in ('.codex/AGENTS.md','.claude/CLAUDE.md','.gemini/GEMINI.md','.copilot/copilot-instructions.md'):
        add(relative, lambda old: managed(old, guidance))
    # OpenCode falls back to Claude's global instructions; preserve that personal
    # preamble when adding its own global file for the first time.
    old_claude = home / '.claude/CLAUDE.md'
    fallback = old_claude.read_text().split(START)[0] if old_claude.exists() else ''
    add('.config/opencode/AGENTS.md', lambda old: managed(old or fallback, guidance))
    add('.cursor/rules/owens-agent-system.mdc', lambda old: managed(old or '---\ndescription: Owen research, development, operations and learning defaults\nalwaysApply: true\n---\n', guidance))
    for mode in oas.MODES:
        body = '# Owen agent system profile\n' + '\n'.join(f'{k} = {oas.toml_value(v)}' for k,v in oas.flatten(oas.config(mode))) + '\n'
        def profile(old, body=body):
            if old and not old.startswith('# Owen agent system profile\n'):
                raise ValueError('Refusing to replace an unmanaged Codex profile')
            return body
        add(f'.codex/owen-{mode}.config.toml', profile)
    patches = {
        '.claude/settings.json': {'permissions': {'disableBypassPermissionsMode':'disable'}},
        '.cursor/cli-config.json': {'sandbox': {'mode':'enabled'},'approvalMode':'allowlist'},
        '.gemini/settings.json': {'general':{'defaultApprovalMode':'default'},'tools':{'sandbox':True}},
        '.config/opencode/opencode.json': {'permission':{'*':'ask','read':'allow','glob':'allow','grep':'allow','list':'allow','edit':'allow','external_directory':'ask','doom_loop':'ask'}},
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
    (backup / 'manifest.json').write_text(json.dumps(records, indent=2)+'\n')
    done = []
    try:
        for (target,before,after,executable), record in zip(changes,records):
            if (target.read_bytes() if target.exists() else None) != before:
                raise ValueError(f'Concurrent change: {target.name}')
            target.parent.mkdir(parents=True,exist_ok=True)
            temp = target.with_name(target.name + '.oas-' + uuid.uuid4().hex)
            try:
                with temp.open('xb') as f:
                    os.chmod(temp, 0o755 if executable else record['mode']); f.write(after)
                os.replace(temp,target)
                done.append((target,before,record['mode']))
            finally:
                if temp.exists(): temp.unlink()
    except Exception:
        for target,before,mode in reversed(done):
            if before is None: target.unlink()
            else: target.write_bytes(before); os.chmod(target,mode)
        raise
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home',type=Path,default=Path.home())
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.apply and args.home.resolve() == Path.home().resolve() and (args.source / '.git').is_file():
        parser.error('Install from the permanent checkout, not a linked worktree; use --source to select it')
    changes=plan(args.home,args.source)
    for path,_,_,_ in changes: print(path.relative_to(args.home.resolve()))
    print(f'{len(changes)} files to update')
    if args.apply:
        backup=apply(changes,args.home)
        print(f'Applied. Backup: {backup}' if backup else 'Already current.')

if __name__=='__main__': main()
