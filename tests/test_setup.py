import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

s=importlib.util.spec_from_file_location('setup',Path(__file__).parents[1]/'scripts/setup.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name).resolve();self.source=Path(__file__).parents[1]
    def test_preserve_original_and_idempotent(self):
        old='My rules without newline'
        text=m.managed(old,'new')
        self.assertTrue(text.startswith(old))
        self.assertEqual(m.managed(text,'new'),text)
    def test_bad_markers_refused(self):
        with self.assertRaises(ValueError):m.managed(m.START,'new')
    def test_apply_and_backup(self):
        p=self.home/'.claude/CLAUDE.md';p.parent.mkdir();p.write_text('My instructions')
        changes=m.plan(self.home,self.source);backup=m.apply(changes,self.home)
        self.assertEqual((backup/'.claude/CLAUDE.md').read_text(),'My instructions')
        self.assertIn('My instructions',p.read_text())
        self.assertEqual(m.plan(self.home,self.source),[])
    def test_unmanaged_profile_refused(self):
        p=self.home/'.codex/owen-development.config.toml';p.parent.mkdir();p.write_text('mine')
        with self.assertRaises(ValueError):m.plan(self.home,self.source)
        self.assertEqual(p.read_text(),'mine')
    def test_concurrent_change_refused(self):
        changes=m.plan(self.home,self.source)
        p=changes[0][0];p.parent.mkdir();p.write_text('concurrent')
        with self.assertRaises(ValueError):m.apply(changes,self.home)
        self.assertEqual(p.read_text(),'concurrent')
    def test_symlink_refused(self):
        p=self.home/'.codex';p.symlink_to(self.home/'elsewhere')
        with self.assertRaises(ValueError):m.plan(self.home,self.source)
    def test_failure_restores_written_files(self):
        p=self.home/'.codex/AGENTS.md';p.parent.mkdir();p.write_text('original')
        changes=m.plan(self.home,self.source)
        replace=m.os.replace;count=0
        def fail_second(a,b):
            nonlocal count
            count+=1
            if count==2:raise OSError('simulated failure')
            return replace(a,b)
        with patch.object(m.os,'replace',side_effect=fail_second):
            with self.assertRaises(OSError):m.apply(changes,self.home)
        self.assertEqual(p.read_text(),'original')
        self.assertFalse((self.home/'.claude/CLAUDE.md').exists())

    def test_failed_cli_install_preserves_concurrent_edits_during_recovery(self):
        for existed in (False, True):
            for replacement in ('text', 'symlink', 'absent', 'mode'):
                with self.subTest(existed=existed, replacement=replacement):
                    home = self.home / f'{existed}-{replacement}'
                    home.mkdir()
                    first = home / '.codex/AGENTS.md'
                    first.parent.mkdir()
                    if existed:
                        first.write_text('original personal instructions')
                    external = home / 'user-file'
                    external.write_text('concurrent edit')
                    real_write = m.write_atomic
                    calls = 0
                    installed_first = None
                    def fail_third(target, data, mode):
                        nonlocal calls, installed_first
                        calls += 1
                        if calls == 3:
                            installed_first = first.read_bytes()
                            if replacement == 'text':
                                first.write_text('concurrent edit')
                            elif replacement == 'mode':
                                first.chmod(0o400)
                            else:
                                first.unlink()
                                if replacement == 'symlink':
                                    first.symlink_to(external)
                            raise OSError('simulated third-file failure')
                        return real_write(target, data, mode)
                    errors = io.StringIO()
                    with patch.object(sys, 'argv', ['setup.py', '--home', str(home), '--apply']), \
                         patch.object(m, 'write_atomic', side_effect=fail_third), \
                         contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                        with self.assertRaisesRegex(OSError, 'third-file failure'):
                            m.main()
                    if replacement == 'absent':
                        self.assertFalse(first.exists())
                    elif replacement == 'mode':
                        self.assertTrue(first.exists())
                        self.assertEqual(first.read_bytes(), installed_first)
                        self.assertEqual(m.stat.S_IMODE(first.stat().st_mode), 0o400)
                    else:
                        self.assertEqual(first.read_text(), 'concurrent edit')
                        self.assertEqual(first.is_symlink(), replacement == 'symlink')
                    self.assertEqual(external.read_text(), 'concurrent edit')
                    self.assertFalse((home / '.claude/CLAUDE.md').exists(), 'untouched writes must still recover')
                    backups = list((home / '.local/state/owens-agent-system/backups').iterdir())
                    self.assertEqual(len(backups), 1)
                    if existed:
                        self.assertEqual((backups[0] / '.codex/AGENTS.md').read_text(), 'original personal instructions')
                    self.assertIn(str(backups[0]), errors.getvalue())
                    self.assertIn(str(first), errors.getvalue())

    def test_merge_keeps_other_settings(self):
        self.assertEqual(m.merged({'permissions':{'allow':['Read']},'model':'mine'},{'permissions':{'disableBypassPermissionsMode':'disable'}}),{'permissions':{'allow':['Read'],'disableBypassPermissionsMode':'disable'},'model':'mine'})

    def test_opencode_setup_enables_auto_compaction_and_preserves_siblings(self):
        p = self.home / '.config/opencode/opencode.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'compaction': {'auto': False, 'reserved': 12000}, 'model': 'mine'}))
        changes = m.plan(self.home, self.source)
        after = next(after for target, _, after, _ in changes if target == p)
        data = json.loads(after)
        self.assertTrue(data['compaction']['auto'])
        self.assertEqual(data['compaction']['reserved'], 12000)
        self.assertEqual(data['model'], 'mine')

    def test_markers_and_paths_come_from_oas(self):
        self.assertEqual((m.START,m.END),(m.oas.MANAGED_START,m.oas.MANAGED_END))
        targets={str(t.relative_to(self.home)) for t,_,_,_ in m.plan(self.home,self.source)}
        self.assertTrue(set(m.oas.GLOBAL_INSTRUCTIONS.values())<=targets)

    def install(self):
        p=self.home/'.claude/CLAUDE.md';p.parent.mkdir();p.write_text('My instructions',encoding='utf-8');p.chmod(0o640)
        return p,m.apply(m.plan(self.home,self.source),self.home)
    def snapshot(self):
        return {f:f.read_bytes() for f in self.home.rglob('*') if f.is_file()}

    def test_rollback_restores_and_removes(self):
        p,backup=self.install()
        actions=m.rollback_plan(self.home,backup)
        self.assertEqual({a for a,_,_ in actions},{'restore','remove'})
        counts=m.rollback_apply(actions)
        self.assertEqual((counts['restore'],counts['keep'],counts['absent']),(1,0,0))
        self.assertEqual(p.read_text(encoding='utf-8'),'My instructions')
        self.assertEqual(m.stat.S_IMODE(p.stat().st_mode),0o640)
        for _,t,_ in actions:
            if t!=p:self.assertFalse(t.exists(),t)
        self.assertTrue((backup/'manifest.json').is_file())
        self.assertEqual((backup/'.claude/CLAUDE.md').read_text(encoding='utf-8'),'My instructions')
    def test_rollback_keeps_created_file_modified_after_install(self):
        _,backup=self.install()
        edited=self.home/'.codex/AGENTS.md';edited.write_text('edited later',encoding='utf-8')
        actions=m.rollback_plan(self.home,backup)
        self.assertEqual([a for a,t,_ in actions if t==edited],['keep'])
        counts=m.rollback_apply(actions)
        self.assertEqual(counts['keep'],1)
        self.assertEqual(edited.read_text(encoding='utf-8'),'edited later')
        self.assertFalse((self.home/'.copilot/copilot-instructions.md').exists())
    def test_rollback_reports_absent_created_file(self):
        _,backup=self.install()
        gone=self.home/'.local/bin/oas';gone.unlink()
        actions=m.rollback_plan(self.home,backup)
        self.assertEqual([a for a,t,_ in actions if t==gone],['absent'])
        self.assertEqual(m.rollback_apply(actions)['absent'],1)
        self.assertFalse(gone.exists())
    def test_rollback_without_manifest_raises(self):
        empty=self.home/'nobackup';empty.mkdir()
        with self.assertRaises(ValueError):m.rollback_plan(self.home,empty)
        with self.assertRaises(ValueError):m.rollback_plan(self.home,self.home/'missing')
    def test_rollback_preview_changes_nothing(self):
        _,backup=self.install()
        before=self.snapshot()
        actions=m.rollback_plan(self.home,backup)
        self.assertEqual(len(actions),14)
        self.assertEqual(self.snapshot(),before)
        out=subprocess.run([sys.executable,str(self.source/'scripts/setup.py'),'--home',str(self.home),'--rollback',str(backup)],capture_output=True,text=True,check=True).stdout
        self.assertIn('restore: .claude/CLAUDE.md',out);self.assertIn('remove: .codex/AGENTS.md',out);self.assertIn('preview only',out)
        self.assertEqual(self.snapshot(),before)
    def test_rollback_symlink_refused(self):
        _,backup=self.install()
        p=self.home/'.copilot/copilot-instructions.md';p.unlink();p.symlink_to(self.home/'elsewhere')
        with self.assertRaises(ValueError):m.rollback_plan(self.home,backup)
        self.assertTrue(p.is_symlink())
    def test_rollback_refuses_paths_outside_home(self):
        outside=self.home.parent/'oas-outside-victim.txt';outside.write_text('victim',encoding='utf-8');self.addCleanup(lambda:outside.unlink(missing_ok=True))
        import hashlib,json
        backup=self.home/'bad-backup';backup.mkdir()
        for rel in ('../oas-outside-victim.txt',str(outside),'.claude/../../oas-outside-victim.txt'):
            (backup/'manifest.json').write_text(json.dumps([dict(path=rel,existed=False,mode=0o600,installed_sha256=hashlib.sha256(b'victim').hexdigest())]),encoding='utf-8')
            with self.assertRaises(ValueError,msg=rel):m.rollback_plan(self.home,backup)
        self.assertEqual(outside.read_text(encoding='utf-8'),'victim')
    def test_rollback_apply_refuses_file_changed_after_planning(self):
        _,backup=self.install()
        actions=m.rollback_plan(self.home,backup)
        p=self.home/'.codex/AGENTS.md';p.write_text('changed after planning',encoding='utf-8')
        with self.assertRaises(ValueError):m.rollback_apply(actions)
        self.assertEqual(p.read_text(encoding='utf-8'),'changed after planning')

    def test_rollback_preserves_modified_preexisting_file(self):
        p, backup = self.install()
        p.write_text('new personal rules', encoding='utf-8')
        actions = m.rollback_plan(self.home, backup)
        self.assertEqual([a for a, t, _ in actions if t == p], ['keep'])
        m.rollback_apply(actions)
        self.assertEqual(p.read_text(encoding='utf-8'), 'new personal rules')

    def test_restore_checks_all_files_before_mutating(self):
        p, backup = self.install()
        actions = m.rollback_plan(self.home, backup)
        p.write_text('concurrent rules', encoding='utf-8')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            m.rollback_apply(actions)
        self.assertEqual(self.snapshot(), before)

    def test_rollback_keeps_permission_edits_to_original_and_created_files(self):
        original, backup = self.install()
        created = self.home / '.codex/AGENTS.md'
        for target in (original, created):
            target.chmod(0o400)
        before = {target: target.read_bytes() for target in (original, created)}
        actions = m.rollback_plan(self.home, backup)
        self.assertEqual([a for a, t, _ in actions if t in before], ['keep', 'keep'])
        m.rollback_apply(actions)
        for target, data in before.items():
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual(m.stat.S_IMODE(target.stat().st_mode), 0o400)

    def test_rollback_refuses_permission_edit_after_planning(self):
        original, backup = self.install()
        actions = m.rollback_plan(self.home, backup)
        original.chmod(0o400)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'changed since planning'):
            m.rollback_apply(actions)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(m.stat.S_IMODE(original.stat().st_mode), 0o400)

    def test_legacy_rollback_manifest_without_installed_mode(self):
        original, backup = self.install()
        manifest = backup / 'manifest.json'
        records = json.loads(manifest.read_text())
        for record in records:
            record.pop('installed_mode', None)
        manifest.write_text(json.dumps(records))
        m.rollback_apply(m.rollback_plan(self.home, backup))
        self.assertEqual(original.read_text(), 'My instructions')
        self.assertEqual(m.stat.S_IMODE(original.stat().st_mode), 0o640)

    def test_installer_keeps_explicit_runtime_selection(self):
        binary = self.home / 'Codex with spaces'
        binary.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8'); binary.chmod(0o700)
        changes = m.plan(self.home, self.source, {'codex': str(binary)})
        m.apply(changes, self.home)
        wrapper = self.home / '.local/bin/oas'
        text = wrapper.read_text(encoding='utf-8')
        self.assertIn('OAS_CODEX_BIN', text)
        self.assertEqual(subprocess.run(['sh', '-n', str(wrapper)], capture_output=True).returncode, 0)
        self.assertEqual(m.plan(self.home, self.source), [])

if __name__=='__main__':unittest.main()
