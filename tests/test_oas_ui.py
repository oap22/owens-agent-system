"""Tests for the interactive launcher: scripts/oas_ui.py and scripts/oas_screen.py.

Written against .oas/20260907T011054Z-d526ab96/interface.md and spec.md before those
modules exist or while they are being written concurrently. Every test builds its own
tempfile home with an explicit scan_root and cwd, and a fake `which`; nothing here
touches the real home directory, the real PATH, or a real terminal (no curses.wrapper,
no initscr).
"""
import curses
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_HERE = Path(__file__).parents[1] / 'scripts'
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import oas
import oas_ui
import oas_screen

NATIVE_AGENTS = [a for a in oas.AGENTS if a != 'generic']


def always_which(prefix='/usr/bin/'):
    return lambda name: prefix + name


class OASUITestBase(unittest.TestCase):
    """Builds a fresh tempfile home, scan_root, and cwd for every test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.scan_root = self.home / 'Developer' / 'active'
        self.scan_root.mkdir(parents=True)
        self.cwd = self.scan_root / 'here'
        self.cwd.mkdir()

    def make(self, which=None, **kwargs):
        kwargs.setdefault('home', self.home)
        kwargs.setdefault('scan_root', self.scan_root)
        kwargs.setdefault('cwd', self.cwd)
        kwargs.setdefault('which', which or always_which())
        kwargs.setdefault('list_models', lambda agent: ['m-one', 'm-two'])
        return oas_ui.Launcher(**kwargs)

    def repo(self, name, root=None):
        """A directory with a .git marker directly under scan_root (or root)."""
        d = (root or self.scan_root) / name
        d.mkdir()
        (d / '.git').mkdir()
        return d


# ---------------------------------------------------------------------------
# oas.py additions
# ---------------------------------------------------------------------------

class InteractiveDefaultTest(unittest.TestCase):
    def test_empty_argv_both_tty_returns_ui(self):
        stdin = type('S', (), {'isatty': lambda self: True})()
        stdout = type('S', (), {'isatty': lambda self: True})()
        self.assertEqual(oas.interactive_default([], stdin=stdin, stdout=stdout), ['ui'])

    def test_empty_argv_one_tty_unchanged(self):
        tty = type('S', (), {'isatty': lambda self: True})()
        notty = type('S', (), {'isatty': lambda self: False})()
        self.assertEqual(oas.interactive_default([], stdin=tty, stdout=notty), [])
        self.assertEqual(oas.interactive_default([], stdin=notty, stdout=tty), [])
        self.assertEqual(oas.interactive_default([], stdin=notty, stdout=notty), [])

    def test_nonempty_argv_unchanged_even_when_tty(self):
        tty = type('S', (), {'isatty': lambda self: True})()
        self.assertEqual(oas.interactive_default(['check'], stdin=tty, stdout=tty), ['check'])


class MainNoTTYTest(unittest.TestCase):
    def test_main_empty_argv_non_tty_exits_2(self):
        # main([]) must run interactive_default with the real streams of this process.
        # Under the test harness these are never an interactive TTY (Bash tool pipes),
        # so this exercises the real non-TTY path with no patching required. Guard with
        # a skip in case a test runner ever attaches a real terminal.
        if sys.stdin.isatty() and sys.stdout.isatty():
            self.skipTest('test process stdin/stdout are a real TTY')
        with self.assertRaises(SystemExit) as cm:
            oas.main([])
        self.assertEqual(cm.exception.code, 2)

    def test_main_empty_argv_forced_nontty_exits_2(self):
        # Belt-and-suspenders: force interactive_default itself to report non-TTY
        # behavior (argv unchanged) regardless of how main() wires the streams through,
        # and confirm the resulting bare argparse call still exits 2.
        with patch.object(oas, 'interactive_default', return_value=[]):
            with self.assertRaises(SystemExit) as cm:
                oas.main([])
            self.assertEqual(cm.exception.code, 2)


# ---------------------------------------------------------------------------
# Mode screen
# ---------------------------------------------------------------------------

class ModeScreenTest(OASUITestBase):
    def test_rows_and_descriptions(self):
        launcher = self.make()
        self.assertEqual(launcher.screen, 'mode')
        rows = launcher.rows()
        self.assertEqual([r.value for r in rows], list(oas.MODES))
        for row, mode in zip(rows, oas.MODES):
            self.assertEqual(row.text, mode)
            self.assertEqual(row.detail, oas_ui.MODE_DESCRIPTIONS[mode])
            self.assertIsNone(row.disabled)

    def test_enter_goes_to_agent_backspace_noop(self):
        launcher = self.make()
        launcher.key('backspace')
        self.assertEqual(launcher.screen, 'mode')
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'agent')
        self.assertEqual(launcher.mode, oas.MODES[0])

    def test_q_quits(self):
        launcher = self.make()
        launcher.key('q')
        self.assertTrue(launcher.quit)


# ---------------------------------------------------------------------------
# Agent screen
# ---------------------------------------------------------------------------

def expected_label(agent, mode):
    if agent == 'codex':
        return oas.config(mode)['sandbox_mode']
    if agent == 'claude':
        return 'plan' if mode == 'tutor' else ('manual' if mode == 'ops' else 'acceptEdits')
    if agent == 'gemini':
        return 'plan' if mode == 'tutor' else 'default'
    if agent == 'copilot':
        return 'plan' if mode == 'tutor' else 'interactive'
    if agent == 'opencode':
        return 'plan' if mode == 'tutor' else 'build'
    if agent == 'cursor':
        return 'ask' if mode == 'tutor' else ('sandbox' if mode == 'ops' else 'auto-review')
    raise AssertionError(agent)


class AgentScreenTest(OASUITestBase):
    def enter_agent_screen(self, mode, which=None):
        launcher = self.make(which=which)
        launcher.mode = mode
        launcher.screen = 'agent'
        return launcher

    def test_permission_labels_all_agents_all_modes(self):
        for mode in oas.MODES:
            if mode == 'unattended':
                continue
            launcher = self.enter_agent_screen(mode)
            rows = {r.value: r for r in launcher.rows()}
            self.assertEqual(set(rows), set(NATIVE_AGENTS))
            for agent in NATIVE_AGENTS:
                row = rows[agent]
                self.assertIsNone(row.disabled, f'{agent}/{mode} unexpectedly disabled')
                self.assertEqual(row.detail, expected_label(agent, mode), f'{agent}/{mode}')

    def test_unattended_only_codex_enabled(self):
        launcher = self.enter_agent_screen('unattended')
        rows = {r.value: r for r in launcher.rows()}
        self.assertIsNone(rows['codex'].disabled)
        self.assertEqual(rows['codex'].detail, oas.config('unattended')['sandbox_mode'])
        for agent in NATIVE_AGENTS:
            if agent == 'codex':
                continue
            self.assertEqual(rows[agent].disabled, 'codex only')
            self.assertEqual(rows[agent].detail, '')

    def test_not_installed_disabled(self):
        which = lambda name: None if name == 'gemini' else '/usr/bin/' + name
        launcher = self.enter_agent_screen('development', which=which)
        rows = {r.value: r for r in launcher.rows()}
        self.assertEqual(rows['gemini'].disabled, 'not installed')
        self.assertEqual(rows['gemini'].detail, '')
        self.assertIsNone(rows['codex'].disabled)

    def test_permission_label_pure_function_cursor_variants(self):
        base = ['cursor-agent', '--workspace', '/x', '--sandbox', 'enabled']
        self.assertEqual(oas_ui.permission_label(base + ['--mode', 'ask', 'msg'], 'cursor', 'tutor'), 'ask')
        self.assertEqual(oas_ui.permission_label(base + ['--auto-review', 'msg'], 'cursor', 'development'), 'auto-review')
        self.assertEqual(oas_ui.permission_label(base + ['msg'], 'cursor', 'ops'), 'sandbox')


# ---------------------------------------------------------------------------
# Cursor skipping
# ---------------------------------------------------------------------------

class CursorSkippingTest(OASUITestBase):
    def test_skips_disabled_rows_both_directions(self):
        which = lambda name: None if name in ('claude', 'gemini') else '/usr/bin/' + name
        # NATIVE_AGENTS order: codex, claude, cursor, gemini, copilot, opencode
        launcher = self.make(which=which)
        launcher.mode = 'development'
        launcher.screen = 'agent'
        launcher.cursor['agent'] = 0  # codex, enabled
        launcher.key('down')  # should skip disabled claude, land on cursor
        rows = launcher.rows()
        self.assertEqual(rows[launcher.cursor['agent']].value, 'cursor')
        launcher.key('down')  # skip disabled gemini, land on copilot
        self.assertEqual(rows[launcher.cursor['agent']].value, 'copilot')
        launcher.key('up')  # skip disabled gemini back to cursor
        self.assertEqual(rows[launcher.cursor['agent']].value, 'cursor')
        launcher.key('up')  # skip disabled claude, land back on codex
        self.assertEqual(rows[launcher.cursor['agent']].value, 'codex')
        launcher.key('up')  # nothing above; stays
        self.assertEqual(rows[launcher.cursor['agent']].value, 'codex')

    def test_all_disabled_shows_empty_message_and_only_backspace_works(self):
        which = lambda name: None
        launcher = self.make(which=which)
        launcher.mode = 'unattended'
        # unattended disables everything except codex; also disable codex via which=None
        launcher.screen = 'agent'
        self.assertEqual(launcher.empty_message(), 'no agent available for this mode')
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'agent')
        launcher.key('backspace')
        self.assertEqual(launcher.screen, 'mode')


# ---------------------------------------------------------------------------
# Workspace screen
# ---------------------------------------------------------------------------

class WorkspaceScreenTest(OASUITestBase):
    def enter_workspace_screen(self, which=None):
        # Navigate via key() rather than poking screen='workspace' directly, so the
        # implementation's own entry hook (which caches the workspace scan) actually runs.
        launcher = self.make(which=which)
        launcher.mode = 'development'
        launcher.screen = 'agent'
        launcher.cursor['agent'] = 0
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'model')
        launcher.key('enter')  # inherit the agent's default model
        self.assertEqual(launcher.screen, 'workspace')
        return launcher

    def test_order_cwd_first_scanned_alpha_excludes_cwd_pick_last(self):
        # cwd is under scan_root and has a .git marker; it must still be excluded from
        # the scanned list because it is already shown as the '.' row.
        (self.cwd / '.git').mkdir()
        self.repo('beta')
        self.repo('zeta')
        (self.scan_root / 'not-a-repo').mkdir()  # no .git, excluded
        (self.scan_root / 'afile').write_text('x', encoding='utf-8')  # not a dir, excluded

        launcher = self.enter_workspace_screen()
        rows = launcher.rows()
        self.assertEqual(rows[0].value, self.cwd)
        self.assertEqual(rows[0].text, '.')
        self.assertIsNone(rows[0].disabled)
        scanned = rows[1:-1]
        self.assertEqual([r.value.name for r in scanned], ['beta', 'zeta'])
        self.assertEqual(rows[-1].value, oas_ui.PICK)
        self.assertEqual(rows[-1].text, oas_ui.PICK)

    def test_missing_marks_scanned_dir_and_cwd(self):
        beta = self.repo('beta')
        launcher = self.enter_workspace_screen()
        launcher.rows()  # cache the scan
        import shutil as _sh
        _sh.rmtree(beta)
        rows = launcher.rows()
        missing = [r for r in rows if r.value == beta]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].disabled, 'missing')
        # cwd itself missing
        _sh.rmtree(self.cwd)
        rows = launcher.rows()
        self.assertEqual(rows[0].disabled, 'missing')

    def test_absent_scan_root_yields_dot_and_pick_only(self):
        import shutil as _sh
        # cwd must survive the scan_root's removal, so use one outside it.
        cwd = self.home / 'elsewhere'
        cwd.mkdir()
        _sh.rmtree(self.scan_root)
        launcher = self.make(cwd=cwd)
        launcher.mode = 'development'
        launcher.screen = 'agent'
        launcher.cursor['agent'] = 0
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'model')
        launcher.key('enter')  # inherit
        self.assertEqual(launcher.screen, 'workspace')
        rows = launcher.rows()
        self.assertEqual([r.value for r in rows], [cwd, oas_ui.PICK])

    def test_scan_workspaces_pure_function(self):
        beta = self.repo('beta')
        zeta = self.repo('zeta')
        self.assertEqual(oas_ui.scan_workspaces(self.scan_root, self.cwd), [beta, zeta])
        missing_root = self.home / 'nope'
        self.assertEqual(oas_ui.scan_workspaces(missing_root, self.cwd), [])

    def test_enter_on_directory_sets_workspace_and_launches(self):
        launcher = self.enter_workspace_screen()
        launcher.cursor['workspace'] = 0
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/x'):
            launcher.key('enter')
        self.assertEqual(launcher.workspace, self.cwd)
        self.assertIsNotNone(launcher.launch_request)

    def test_enter_on_pick_opens_browser_at_home(self):
        launcher = self.enter_workspace_screen()
        rows = launcher.rows()
        launcher.cursor['workspace'] = len(rows) - 1
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'browser')
        self.assertEqual(launcher.browser_dir, self.home)
        self.assertEqual(launcher.cursor['browser'], 0)


# ---------------------------------------------------------------------------
# Directory browser
# ---------------------------------------------------------------------------

class BrowserTest(OASUITestBase):
    def enter_browser(self):
        launcher = self.make()
        launcher.mode = 'development'
        launcher.agent = 'codex'
        launcher.workspace = self.cwd
        launcher.screen = 'browser'
        launcher.browser_dir = self.home
        launcher.cursor['browser'] = 0
        return launcher

    def test_starts_at_home(self):
        launcher = self.make()
        self.assertEqual(launcher.browser_dir, self.home)

    def test_hidden_dirs_omitted_and_alphabetical(self):
        (self.home / '.hidden').mkdir()
        (self.home / 'zzz').mkdir()
        (self.home / 'aaa').mkdir()
        launcher = self.enter_browser()
        rows = launcher.rows()
        self.assertEqual([r.text for r in rows], ['Developer', 'aaa', 'zzz'])

    def test_enter_descends_backspace_up_esc_to_workspace(self):
        child = self.home / 'child'
        child.mkdir()
        launcher = self.enter_browser()
        rows = launcher.rows()
        idx = [r.text for r in rows].index('child')
        launcher.cursor['browser'] = idx
        launcher.key('enter')
        self.assertEqual(launcher.browser_dir, child)
        self.assertEqual(launcher.cursor['browser'], 0)
        launcher.key('backspace')
        self.assertEqual(launcher.browser_dir, self.home)
        launcher.key('esc')
        self.assertEqual(launcher.screen, 'workspace')

    def test_backspace_at_filesystem_root_noop(self):
        launcher = self.enter_browser()
        root = Path(launcher.browser_dir.anchor)
        launcher.browser_dir = root
        launcher.key('backspace')
        self.assertEqual(launcher.browser_dir, root)

    def test_space_chooses_current_folder_and_launches(self):
        launcher = self.enter_browser()
        target = launcher.browser_dir
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/x'):
            launcher.key('space')
        self.assertEqual(launcher.workspace, target)
        self.assertIsNotNone(launcher.launch_request)

    def test_no_access_disabled(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('running as root; permission bits are not enforced')
        locked = self.home / 'locked'
        locked.mkdir()
        old_mode = locked.stat().st_mode
        os.chmod(locked, 0)
        self.addCleanup(lambda: os.chmod(locked, old_mode))
        launcher = self.enter_browser()
        rows = {r.text: r for r in launcher.rows()}
        self.assertEqual(rows['locked'].disabled, 'no access')


# ---------------------------------------------------------------------------
# Launch from the workspace choice
# ---------------------------------------------------------------------------

class LaunchTest(OASUITestBase):
    def ready(self, agent='codex', mode='development'):
        launcher = self.make()
        launcher.mode = mode
        launcher.agent = agent
        launcher._enter_workspace_screen()
        launcher.cursor['workspace'] = 0
        return launcher

    def test_enter_on_workspace_launches_open_session(self):
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/codex'):
            launcher = self.ready()
            launcher.key('enter')
        self.assertIsNotNone(launcher.launch_request)
        cmd, workspace_path = launcher.launch_request
        # home must be the Launcher's own home so shared-guidance detection never reads the real one.
        self.assertEqual(cmd, oas.command('codex', 'development', self.cwd, '', 'auto', self.home))
        self.assertTrue(cmd[-1].endswith(oas.DEFAULT_TASK))
        self.assertEqual(workspace_path, oas.workspace_path(self.cwd))
        self.assertEqual(launcher.workspace, self.cwd)

    def test_claude_open_session_has_no_prompt_argument(self):
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/claude'):
            launcher = self.ready(agent='claude')
            launcher.key('enter')
        cmd, _ = launcher.launch_request
        self.assertEqual(cmd[-2], '--append-system-prompt')
        self.assertNotIn(oas.DEFAULT_TASK, cmd[-1])

    def test_browser_space_launches_in_current_folder(self):
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/codex'):
            launcher = self.ready()
            launcher.cursor['workspace'] = len(launcher.rows()) - 1
            launcher.key('enter')
            self.assertEqual(launcher.screen, 'browser')
            launcher.key('space')
        self.assertIsNotNone(launcher.launch_request)
        self.assertEqual(launcher.workspace, self.home)

    def test_refusal_stays_on_screen_until_next_key(self):
        with patch.object(oas.shutil, 'which', return_value=None):
            launcher = self.ready()
            launcher.key('enter')
        self.assertIsNone(launcher.launch_request)
        self.assertEqual(launcher.screen, 'workspace')
        self.assertIn('not installed', launcher.error)
        launcher.key('down')
        self.assertIsNone(launcher.error)


# ---------------------------------------------------------------------------
# Return-to-home preselection, last_exit, q on task screen
# ---------------------------------------------------------------------------

class ReturnedTest(OASUITestBase):
    def test_returned_preselects_and_clears_task(self):
        launcher = self.make()
        launcher.mode = 'research'
        launcher.agent = 'gemini'
        launcher.workspace = self.cwd
        launcher.screen = 'workspace'
        launcher.error = 'boom'
        launcher.launch_request = (['x'], self.cwd)

        launcher.returned(0)

        self.assertEqual(launcher.last_exit, 0)
        self.assertEqual(launcher.screen, 'mode')
        self.assertIsNone(launcher.error)
        self.assertIsNone(launcher.launch_request)
        self.assertEqual(launcher.mode, 'research')
        self.assertEqual(launcher.agent, 'gemini')
        self.assertEqual(launcher.workspace, self.cwd)
        self.assertEqual(launcher.cursor['mode'], oas.MODES.index('research'))

    def test_preselection_carries_into_agent_and_workspace_screens(self):
        launcher = self.make()
        launcher.mode = 'ops'
        launcher.agent = 'opencode'
        launcher.model = 'm-two'
        launcher.workspace = self.cwd
        launcher.screen = 'workspace'
        launcher.returned(0)

        # cursor already parked on 'ops' row; select it
        self.assertEqual(launcher.rows()[launcher.cursor['mode']].value, 'ops')
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'agent')
        self.assertEqual(launcher.rows()[launcher.cursor['agent']].value, 'opencode')
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'model')
        self.assertEqual(launcher.rows()[launcher.cursor['model']].value, 'm-two')
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'workspace')
        self.assertEqual(launcher.rows()[launcher.cursor['workspace']].value, self.cwd)

    def test_last_exit_only_on_mode_screen_and_cleared_after_leaving(self):
        launcher = self.make()
        launcher.mode = 'development'
        launcher.agent = 'codex'
        launcher.workspace = self.cwd
        launcher.screen = 'workspace'
        launcher.returned(3)
        self.assertIn('last session exited 3', launcher.footer())
        launcher.key('enter')  # leaves mode screen
        self.assertEqual(launcher.screen, 'agent')
        self.assertIsNone(launcher.last_exit)
        self.assertNotIn('last session exited', launcher.footer())

    def test_q_quits_on_every_screen(self):
        for screen in oas_ui.SCREENS:
            launcher = self.make()
            launcher.mode = 'development'
            launcher.agent = 'codex'
            launcher.screen = screen
            launcher.key('q')
            self.assertTrue(launcher.quit, screen)


# ---------------------------------------------------------------------------
# oas_screen.Rain
# ---------------------------------------------------------------------------

class RainTest(unittest.TestCase):
    def test_cells_within_bounds_and_level_range(self):
        rain = oas_screen.Rain(20, 10, rng=random.Random(1))
        for cell in rain.cells():
            y, x, glyph, level = cell
            self.assertTrue(0 <= y < 10)
            self.assertTrue(0 <= x < 20)
            self.assertIsInstance(glyph, str)
            self.assertEqual(len(glyph), 1)
            self.assertTrue(0.0 < level <= 1.0)

    def test_faint_only_even_columns_and_half_level(self):
        rain = oas_screen.Rain(20, 10, rng=random.Random(1))
        faint_cells = rain.cells(faint=True)
        for y, x, glyph, level in faint_cells:
            self.assertEqual(x % 2, 0)
            self.assertLessEqual(level, 0.5 + 1e-9)

    def test_step_changes_state(self):
        rain = oas_screen.Rain(20, 10, rng=random.Random(2))
        before = rain.cells()
        changed = False
        for _ in range(20):
            rain.step()
            if rain.cells() != before:
                changed = True
                break
        self.assertTrue(changed, 'rain state never changed across 20 steps')

    def test_resize_keeps_bounds(self):
        rain = oas_screen.Rain(20, 10, rng=random.Random(3))
        rain.resize(8, 5)
        for y, x, glyph, level in rain.cells():
            self.assertTrue(0 <= y < 5)
            self.assertTrue(0 <= x < 8)


# ---------------------------------------------------------------------------
# oas_screen.logo_lines
# ---------------------------------------------------------------------------

class LogoLinesTest(unittest.TestCase):
    def test_five_equal_width_rows(self):
        lines = oas_screen.logo_lines("OWEN'S")
        self.assertEqual(len(lines), 5)
        widths = {len(line) for line in lines}
        self.assertEqual(len(widths), 1)
        for line in lines:
            self.assertTrue(set(line) <= {'█', ' '})

    def test_second_word(self):
        lines = oas_screen.logo_lines('AGENTS')
        self.assertEqual(len(lines), 5)
        widths = {len(line) for line in lines}
        self.assertEqual(len(widths), 1)


# ---------------------------------------------------------------------------
# oas_screen.keyname
# ---------------------------------------------------------------------------

class KeynameTest(unittest.TestCase):
    def test_curses_special_keys(self):
        self.assertEqual(oas_screen.keyname(curses.KEY_UP), 'up')
        self.assertEqual(oas_screen.keyname(curses.KEY_DOWN), 'down')
        self.assertEqual(oas_screen.keyname(curses.KEY_LEFT), 'left')
        self.assertEqual(oas_screen.keyname(curses.KEY_RIGHT), 'right')
        self.assertEqual(oas_screen.keyname(curses.KEY_HOME), 'home')
        self.assertEqual(oas_screen.keyname(curses.KEY_END), 'end')
        self.assertEqual(oas_screen.keyname(curses.KEY_BACKSPACE), 'backspace')

    def test_string_keys(self):
        self.assertEqual(oas_screen.keyname('\n'), 'enter')
        self.assertEqual(oas_screen.keyname(27), 'esc')
        # get_wch() returns control characters as one-character strings on real terminals.
        self.assertEqual(oas_screen.keyname('\x1b'), 'esc')
        self.assertEqual(oas_screen.keyname('\x7f'), 'backspace')
        self.assertEqual(oas_screen.keyname('\x08'), 'backspace')
        self.assertEqual(oas_screen.keyname(' '), 'space')
        self.assertEqual(oas_screen.keyname('q'), 'q')
        self.assertEqual(oas_screen.keyname('a'), 'a')


# ---------------------------------------------------------------------------
# oas_screen.run_ui
# ---------------------------------------------------------------------------

class FakeStream:
    def __init__(self, tty):
        self._tty = tty

    def isatty(self):
        return self._tty


class RunUITest(unittest.TestCase):
    def test_raises_without_tty(self):
        with patch.object(sys, 'stdin', FakeStream(False)), patch.object(sys, 'stdout', FakeStream(False)):
            with self.assertRaises(ValueError) as cm:
                oas_screen.run_ui()
            self.assertIn('terminal', str(cm.exception))

    def test_raises_when_only_stdout_is_tty(self):
        with patch.object(sys, 'stdin', FakeStream(False)), patch.object(sys, 'stdout', FakeStream(True)):
            with self.assertRaises(ValueError):
                oas_screen.run_ui()

    def test_raises_when_only_stdin_is_tty(self):
        with patch.object(sys, 'stdin', FakeStream(True)), patch.object(sys, 'stdout', FakeStream(False)):
            with self.assertRaises(ValueError):
                oas_screen.run_ui()

    # Deviation (see final report): the spec's NO_COLOR/--plain "no rain" behavior lives
    # past this TTY guard, inside the curses.wrapper session loop. The contract does not
    # expose rain-enablement as a standalone function, and driving run_ui past the guard
    # would require either a real terminal (forbidden) or guessing at an unspecified
    # curses.wrapper call signature and risking an infinite loop against a mocked
    # wrapper whose return value never satisfies launcher.quit/launch_request. So only
    # the documented pre-wrapper TTY guard is verified here; the rain-disable branch
    # itself is left for manual/installed-runtime verification per AGENTS.md.


if __name__ == '__main__':
    unittest.main()


class ReviewFixesTest(unittest.TestCase):
    """Regressions for defects found in the lead's review of the first build."""

    def test_visible_window_keeps_cursor_inside(self):
        self.assertEqual(oas_screen.visible_window(3, 1, 10), (0, 3))
        for cursor in range(40):
            start, end = oas_screen.visible_window(40, cursor, 10)
            self.assertEqual(end - start, 10)
            self.assertTrue(start <= cursor < end, cursor)
        self.assertEqual(oas_screen.visible_window(40, 39, 10), (30, 40))
        self.assertEqual(oas_screen.visible_window(0, 0, 10), (0, 0))

    def test_rain_trail_varies_glyphs_within_a_column(self):
        rain = oas_screen.Rain(4, 30, random.Random(3))
        for _ in range(40):
            rain.step()
        by_column = {}
        for y, x, glyph, level in rain.cells():
            by_column.setdefault(x, set()).add(glyph)
        self.assertTrue(any(len(g) > 1 for g in by_column.values()), by_column)
        rain.resize(4, 12)
        for y, x, glyph, level in rain.cells():
            self.assertTrue(0 <= y < 12 and 0 <= x < 4)

    def test_plain_colors_touch_no_curses_pairs(self):
        colors = oas_screen._init_colors(True)
        self.assertEqual(set(colors.values()), {0})

    def test_agent_rows_computed_once_per_screen_entry(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        home = Path(tmp.name); cwd = home / 'w'; cwd.mkdir()
        calls = []
        launcher = oas_ui.Launcher(home=home, scan_root=home / 'none', cwd=cwd, which=lambda n: calls.append(n) or '/bin/x')
        launcher.key('enter')
        before = len(calls)
        for _ in range(20):
            launcher.rows(); launcher.empty_message()
        self.assertEqual(len(calls), before)
        launcher.key('backspace'); launcher.key('down'); launcher.key('enter')
        self.assertGreater(len(calls), before)

    def test_interactive_default_reads_streams_at_call_time(self):
        notty = type('S', (), {'isatty': lambda self: False})()
        with patch.object(oas.sys, 'stdin', notty), patch.object(oas.sys, 'stdout', notty):
            self.assertEqual(oas.interactive_default([]), [])


class OpaqueForegroundTest(unittest.TestCase):
    """Panels and the logo band must fully cover the rain behind them."""

    class FakeWindow:
        def __init__(self, rows, cols):
            self.rows, self.cols = rows, cols
            self.grid = [[' '] * cols for _ in range(rows)]
        def getmaxyx(self):
            return self.rows, self.cols
        def addstr(self, y, x, text, attr=0):
            for i, ch in enumerate(text):
                if 0 <= x + i < self.cols:
                    self.grid[y][x + i] = ch

    def render(self, *keys):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        home = Path(tmp.name); cwd = home / 'proj'; cwd.mkdir()
        launcher = oas_ui.Launcher(home=home, scan_root=home / 'none', cwd=cwd, which=lambda n: '/bin/x')
        for k in keys:
            launcher.key(k)
        win = self.FakeWindow(30, 90)
        rain = oas_screen.Rain(90, 30, random.Random(1))
        for _ in range(25):
            rain.step()
        with patch.object(oas_screen.curses, 'color_pair', lambda n: 0):
            oas_screen._draw_screen(win, launcher, rain, {}, 30, 90)
        return [''.join(r) for r in win.grid]

    @staticmethod
    def has_rain(text):
        return any('ｱ' <= ch <= 'ﾝ' for ch in text)

    def test_panel_interior_and_logo_band_hide_rain(self):
        for keys in ((), ('enter',), ('enter', 'enter')):
            lines = self.render(*keys)
            tops = [i for i, l in enumerate(lines) if '┌' in l]
            self.assertEqual(len(tops), 1, keys)
            top = tops[0]; bottom = next(i for i, l in enumerate(lines) if '└' in l)
            left = lines[top].index('┌'); right = lines[top].index('┐')
            for y in range(top, bottom + 1):
                self.assertFalse(self.has_rain(lines[y][left:right + 1]), (keys, y, lines[y]))
            if not keys:
                logo_rows = [l for l in lines if '█' in l]
                self.assertEqual(len(logo_rows), 5)
                block = oas_screen.logo_lines("OWEN'S AGENTS")
                self.assertEqual(len(block[0]), 70)
                self.assertIn(block[0].strip(), logo_rows[0])
                for l in logo_rows:
                    a = l.index('█'); b = l.rindex('█')
                    self.assertFalse(self.has_rain(l[a - 3:b + 4]), l)

    def test_home_block_and_panels_are_centered(self):
        lines = self.render()
        logo_top = next(i for i, l in enumerate(lines) if '█' in l)
        box_top = next(i for i, l in enumerate(lines) if '┌' in l)
        box_bottom = next(i for i, l in enumerate(lines) if '└' in l)
        block_height = box_bottom - logo_top + 1
        self.assertLessEqual(abs(logo_top - (30 - block_height) // 2), 1)
        left, right = lines[box_top].index('┌'), lines[box_top].index('┐')
        self.assertLessEqual(abs((left + right) // 2 - 45), 1)
        for keys in (('enter',), ('enter', 'enter')):
            lines = self.render(*keys)
            top = next(i for i, l in enumerate(lines) if '┌' in l)
            bottom = next(i for i, l in enumerate(lines) if '└' in l)
            self.assertLessEqual(abs((top + bottom) // 2 - 15), 1, keys)
            left, right = lines[top].index('┌'), lines[top].index('┐')
            self.assertLessEqual(abs((left + right) // 2 - 45), 1, keys)
            self.assertLess(right - left, 80, keys)


class ExitNoticeTest(unittest.TestCase):
    def test_notice_names_agent_and_code_and_waits(self):
        text = oas_screen.exit_notice('codex', 1)
        self.assertIn('codex', text)
        self.assertIn('code 1', text)
        self.assertIn('Press Enter', text)
        calls = []
        oas_screen.wait_for_enter(read=lambda: calls.append(1) or '\n')
        self.assertEqual(calls, [1])
        oas_screen.wait_for_enter(read=lambda: (_ for _ in ()).throw(EOFError()))


class ModelScreenTest(OASUITestBase):
    def at_model(self, agent='codex'):
        launcher = self.make()
        launcher.mode = 'development'
        launcher.screen = 'agent'
        launcher.cursor['agent'] = list(oas.AGENTS).index(agent)
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'model')
        return launcher

    def test_rows_inherit_first_listed_models_then_type_row(self):
        launcher = self.at_model()
        rows = launcher.rows()
        self.assertEqual([r.value for r in rows], [None, 'm-one', 'm-two', oas_ui.TYPE_MODEL])
        self.assertEqual(rows[0].text, oas_ui.INHERIT)
        self.assertNotIn('m-one', launcher.title())

    def test_inherit_keeps_model_none_and_launch_has_no_model_flag(self):
        launcher = self.at_model()
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'workspace')
        self.assertIsNone(launcher.model)
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/codex'):
            launcher.key('enter')
        self.assertNotIn('--model', launcher.launch_request[0])

    def test_listed_model_flows_into_breadcrumb_and_argv(self):
        launcher = self.at_model()
        launcher.key('down'); launcher.key('down'); launcher.key('enter')
        self.assertEqual(launcher.model, 'm-two')
        self.assertIn('m-two', launcher.title())
        with patch.object(oas.shutil, 'which', return_value='/usr/bin/codex'):
            launcher.key('enter')
        cmd = launcher.launch_request[0]
        self.assertEqual(cmd, oas.command('codex', 'development', self.cwd, '', 'auto', self.home, model='m-two'))
        self.assertEqual(cmd[cmd.index('--model') + 1], 'm-two')

    def test_typed_model_validated_and_escapable(self):
        launcher = self.at_model()
        launcher.cursor['model'] = len(launcher.rows()) - 1
        launcher.key('enter')
        self.assertEqual(launcher.model_entry, '')
        self.assertEqual(launcher.footer(), oas_ui.ENTRY_FOOTER)
        for ch in 'bad$id':
            launcher.key(ch)
        launcher.key('space')  # ignored: model ids never contain spaces
        launcher.key('enter')
        self.assertEqual(launcher.screen, 'model')
        self.assertIn('model id', launcher.error)
        launcher.key('esc')
        self.assertIsNone(launcher.model_entry)
        launcher.key('enter')
        for ch in 'q-x':
            launcher.key(ch)
        self.assertFalse(launcher.quit)
        self.assertIn('q-x', launcher.rows()[-1].text)
        launcher.key('enter')
        self.assertEqual(launcher.model, 'q-x')
        self.assertEqual(launcher.screen, 'workspace')

    def test_back_from_workspace_returns_to_model_with_preselection(self):
        launcher = self.at_model()
        launcher.key('down'); launcher.key('enter')
        self.assertEqual(launcher.screen, 'workspace')
        launcher.key('backspace')
        self.assertEqual(launcher.screen, 'model')
        self.assertEqual(launcher.rows()[launcher.cursor['model']].value, 'm-one')
        launcher.key('backspace')
        self.assertEqual(launcher.screen, 'agent')

    def test_model_list_computed_once_per_agent(self):
        calls = []
        launcher = self.make(list_models=lambda agent: calls.append(agent) or ['x'])
        launcher.mode = 'development'; launcher.screen = 'agent'; launcher.cursor['agent'] = 0
        launcher.key('enter')
        for _ in range(10):
            launcher.rows()
        self.assertEqual(calls, ['codex'])


class ModelChoicesTest(unittest.TestCase):
    def test_parse_codex_json_cursor_text_opencode_text(self):
        codex = '{"models": [{"slug": "gpt-a"}, {"slug": "gpt-b", "x": 1}, {"nope": 1}]}'
        self.assertEqual(oas_ui.parse_models('codex', codex), ['gpt-a', 'gpt-b'])
        cursor = 'Available models\n\nauto - Auto (current, default)\ngpt-5 - GPT-5\n'
        self.assertEqual(oas_ui.parse_models('cursor', cursor), ['auto', 'gpt-5'])
        self.assertEqual(oas_ui.parse_models('opencode', 'openai/gpt-5\nollama/qwen3:30b\n'), ['openai/gpt-5', 'ollama/qwen3:30b'])
        self.assertEqual(oas_ui.parse_models('codex', 'not json'), [])

    def test_model_choices_static_and_failure_paths(self):
        self.assertEqual(oas_ui.model_choices('claude'), ['fable', 'opus', 'sonnet', 'haiku'])
        self.assertEqual(oas_ui.model_choices('gemini'), [])
        ran = []
        class R:
            returncode = 0
            stdout = 'a-model - A\n'
        self.assertEqual(oas_ui.model_choices('cursor', run=lambda cmd, **kw: ran.append(cmd) or R()), ['a-model'])
        self.assertEqual(ran, [['cursor-agent', '--list-models']])
        def boom(cmd, **kw):
            raise OSError('missing')
        self.assertEqual(oas_ui.model_choices('codex', run=boom), [])
        class Bad(R):
            returncode = 1
        self.assertEqual(oas_ui.model_choices('opencode', run=lambda cmd, **kw: Bad()), [])
