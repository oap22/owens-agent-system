import importlib.util
from pathlib import Path
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

    def test_merge_keeps_other_settings(self):
        self.assertEqual(m.merged({'permissions':{'allow':['Read']},'model':'mine'},{'permissions':{'disableBypassPermissionsMode':'disable'}}),{'permissions':{'allow':['Read'],'disableBypassPermissionsMode':'disable'},'model':'mine'})

if __name__=='__main__':unittest.main()
