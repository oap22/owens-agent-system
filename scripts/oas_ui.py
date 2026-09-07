"""Pure state machine for the interactive `oas ui` launcher. No curses import here;
scripts/oas_screen.py is the thin curses layer that drives this with key names."""
from __future__ import annotations
import os
import sys
import typing
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import oas

MIN_COLS = 60
MIN_ROWS = 16
PICK = 'pick a directory…'
MODE_DESCRIPTIONS = {
    'development': 'Implement, debug, test, review',
    'research': 'Literature, synthesis, experiment design',
    'ops': 'Daily planning, commitments, drafts, owned maintenance',
    'tutor': 'Coursework and research understanding',
    'unattended': 'Explicitly owned local jobs',
}
SCREENS = ('mode', 'agent', 'workspace', 'browser')
LIST_FOOTER = '↑↓ move  ⏎ select  ⌫ back  q quit'
WORKSPACE_FOOTER = '↑↓ move  ⏎ launch  ⌫ back  q quit'
BROWSER_FOOTER = '⏎ open  ⌫ up  space launch here  esc cancel  q quit'


class Row(typing.NamedTuple):
    text: str
    detail: str
    disabled: str | None
    value: object


def display_path(path, home):
    path = Path(path)
    home = Path(home)
    try:
        rel = path.resolve().relative_to(home.resolve())
    except ValueError:
        return str(path)
    return str(Path('~') / rel)


def scan_workspaces(scan_root, cwd):
    scan_root = Path(scan_root)
    if not scan_root.is_dir():
        return []
    cwd_resolved = Path(cwd).resolve()
    result = []
    for child in scan_root.iterdir():
        if not child.is_dir() or not (child / '.git').exists():
            continue
        if child.resolve() == cwd_resolved:
            continue
        result.append(child)
    return sorted(result, key=lambda p: p.name)


def _value_after(cmd, flag):
    if flag in cmd:
        i = cmd.index(flag)
        if i + 1 < len(cmd):
            return cmd[i + 1]
    return None


def permission_label(cmd, agent, mode):
    if agent == 'codex':
        return oas.config(mode)['sandbox_mode']
    if agent == 'claude':
        return _value_after(cmd, '--permission-mode')
    if agent == 'gemini':
        return _value_after(cmd, '--approval-mode')
    if agent == 'copilot':
        return _value_after(cmd, '--mode')
    if agent == 'opencode':
        return _value_after(cmd, '--agent')
    if agent == 'cursor':
        value = _value_after(cmd, '--mode')
        if value is not None:
            return value
        return 'auto-review' if '--auto-review' in cmd else 'sandbox'
    return ''


class Launcher:
    def __init__(self, *, home=None, scan_root=None, cwd=None, which=None, environ=None):
        self.home = Path.home() if home is None else Path(home)
        self.scan_root = (self.home / 'Developer/active') if scan_root is None else Path(scan_root)
        self.cwd = Path(os.getcwd()) if cwd is None else Path(cwd)
        self.which = which
        self.environ = os.environ if environ is None else environ
        self.screen = 'mode'
        self.cursor = {'mode': 0, 'agent': 0, 'workspace': 0, 'browser': 0}
        self.mode = None
        self.agent = None
        self.workspace = None
        self.browser_dir = self.home
        self.error = None           # last launch refusal, shown until the next key
        self.last_exit = None
        self.quit = False
        self.launch_request = None
        self._workspace_scan = []
        self._agent_cache = None      # (mode, rows) computed on entering the agent screen
        self._browser_cache = None    # (dir, rows) recomputed when browser_dir changes

    # -- which lookup, deferred so unittest.mock.patch.object(oas.shutil, 'which', ...) applies --
    def _which(self, name):
        fn = self.which if self.which is not None else oas.shutil.which
        return fn(name)

    # -- rows per screen --
    def _mode_rows(self):
        return [Row(m, MODE_DESCRIPTIONS[m], None, m) for m in oas.MODES]

    def _agent_rows(self):
        rows = []
        for agent in oas.AGENTS:
            if agent == 'generic':
                continue
            if self.mode == 'unattended' and agent != 'codex':
                rows.append(Row(agent, '', 'codex only', agent))
                continue
            cmd = oas.command(agent, self.mode, self.cwd, 'placeholder', shared='never')
            if not self._which(cmd[0]):
                rows.append(Row(agent, '', 'not installed', agent))
            else:
                rows.append(Row(agent, permission_label(cmd, agent, self.mode), None, agent))
        return rows

    def _workspace_rows(self):
        rows = [Row('.', display_path(self.cwd, self.home), None if self.cwd.is_dir() else 'missing', self.cwd)]
        for p in self._workspace_scan:
            rows.append(Row(display_path(p, self.home), '', None if p.exists() else 'missing', p))
        rows.append(Row(PICK, '', None, PICK))
        return rows

    def _browser_rows(self):
        try:
            children = sorted((p for p in self.browser_dir.iterdir() if p.is_dir() and not p.name.startswith('.')),
                               key=lambda p: p.name)
        except OSError:
            children = []
        rows = []
        for p in children:
            disabled = None if os.access(p, os.R_OK | os.X_OK) else 'no access'
            rows.append(Row(p.name, '', disabled, p))
        return rows

    def rows(self):
        if self.screen == 'mode':
            return self._mode_rows()
        if self.screen == 'agent':
            # Cached on entry: each agent row costs an oas.command build plus a PATH lookup,
            # and the screen is redrawn twenty times a second.
            if self._agent_cache is None or self._agent_cache[0] != self.mode:
                self._agent_cache = (self.mode, self._agent_rows())
            return self._agent_cache[1]
        if self.screen == 'workspace':
            return self._workspace_rows()
        if self.screen == 'browser':
            if self._browser_cache is None or self._browser_cache[0] != self.browser_dir:
                self._browser_cache = (self.browser_dir, self._browser_rows())
            return self._browser_cache[1]
        return []

    def title(self):
        if self.screen == 'mode':
            return 'mode'
        if self.screen == 'browser':
            return display_path(self.browser_dir, self.home)
        parts = []
        if self.mode is not None:
            parts.append(self.mode)
        if self.agent is not None:
            parts.append(self.agent)
        if self.workspace is not None:
            parts.append(display_path(self.workspace, self.home))
        return ' › '.join(parts)

    def footer(self):
        if self.screen == 'browser':
            return BROWSER_FOOTER
        if self.screen == 'workspace':
            return WORKSPACE_FOOTER
        footer = LIST_FOOTER
        if self.screen == 'mode' and self.last_exit is not None:
            footer += f'   last session exited {self.last_exit}'
        return footer

    def empty_message(self):
        if self.screen == 'agent':
            rows = self.rows()
            if rows and all(r.disabled for r in rows):
                return 'no agent available for this mode'
        if self.screen == 'browser' and not self.rows():
            return 'no subfolders'
        return None

    # -- navigation helpers --
    def _move(self, direction):
        rows = self.rows()
        if not rows:
            return
        i = self.cursor[self.screen] + direction
        while 0 <= i < len(rows):
            if not rows[i].disabled:
                self.cursor[self.screen] = i
                return
            i += direction

    def _enter_agent_screen(self):
        self.last_exit = None
        self.screen = 'agent'
        self._agent_cache = (self.mode, self._agent_rows())
        rows = self._agent_cache[1]
        enabled = [i for i, r in enumerate(rows) if not r.disabled]
        idx = enabled[0] if enabled else 0
        if self.agent is not None:
            for i in enabled:
                if rows[i].value == self.agent:
                    idx = i
                    break
        self.cursor['agent'] = idx

    def _enter_workspace_screen(self):
        self.screen = 'workspace'
        self._workspace_scan = scan_workspaces(self.scan_root, self.cwd)
        rows = self._workspace_rows()
        idx = 0
        if self.workspace is not None:
            for i, r in enumerate(rows):
                if r.value == self.workspace:
                    idx = i
                    break
        self.cursor['workspace'] = idx

    def _select(self):
        rows = self.rows()
        idx = self.cursor[self.screen]
        if not rows or idx >= len(rows) or rows[idx].disabled:
            return
        row = rows[idx]
        if self.screen == 'mode':
            self.mode = row.value
            self._enter_agent_screen()
        elif self.screen == 'agent':
            self.agent = row.value
            self._enter_workspace_screen()
        elif self.screen == 'workspace':
            if row.value == PICK:
                self.browser_dir = self.home
                self.screen = 'browser'
                self.cursor['browser'] = 0
            else:
                self.workspace = row.value
                self._launch()

    def _back(self):
        if self.screen == 'agent':
            self.screen = 'mode'
        elif self.screen == 'workspace':
            self.screen = 'agent'
        # 'mode': nothing

    def _list_key(self, name):
        if name == 'q':
            self.quit = True
        elif name == 'up':
            self._move(-1)
        elif name == 'down':
            self._move(1)
        elif name == 'enter':
            self._select()
        elif name in ('backspace', 'esc'):
            self._back()

    def _browser_key(self, name):
        if name == 'q':
            self.quit = True
        elif name == 'up':
            self._move(-1)
        elif name == 'down':
            self._move(1)
        elif name == 'enter':
            rows = self.rows()
            idx = self.cursor['browser']
            if rows and idx < len(rows) and not rows[idx].disabled:
                self.browser_dir = rows[idx].value
                self.cursor['browser'] = 0
        elif name == 'backspace':
            parent = self.browser_dir.parent
            if parent != self.browser_dir:
                self.browser_dir = parent
                self.cursor['browser'] = 0
        elif name == 'esc':
            self.screen = 'workspace'
        elif name == 'space':
            self.workspace = self.browser_dir
            self._launch()

    def _launch(self):
        """Choosing a workspace launches an open session; refusals stay on screen as error."""
        try:
            cmd = oas.launch_command(self.agent, self.mode, self.workspace, '', 'auto', self.home)
            self.launch_request = (cmd, oas.workspace_path(self.workspace))
        except ValueError as exc:
            self.error = str(exc)

    def key(self, name):
        self.error = None
        if self.screen == 'browser':
            self._browser_key(name)
        else:
            self._list_key(name)

    def returned(self, code):
        self.last_exit = code
        self.screen = 'mode'
        self.error = None
        self.launch_request = None
        if self.mode in oas.MODES:
            self.cursor['mode'] = list(oas.MODES).index(self.mode)
