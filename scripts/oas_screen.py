#!/usr/bin/env python3
"""Curses drawing layer for the interactive oas launcher.

Pure state lives in oas_ui.Launcher; this module only draws it and turns key
presses into the key names oas_ui.Launcher.key() understands. oas_ui is
imported lazily (inside run_ui) so this module stays importable on its own
for testing Rain / logo_lines / keyname even before oas_ui exists or when no
terminal is available.
"""
from __future__ import annotations
import os
# Must be set before curses is imported so Esc is not held for the default
# ~1s escape-sequence timeout.
os.environ.setdefault('ESCDELAY', '25')
import curses
import random
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

FRAME_MS = 50  # 20 fps

GLYPHS = [chr(c) for c in range(0xFF71, 0xFF9E)] + [str(d) for d in range(10)]


class Rain:
    """Deterministic matrix-rain columns. Pure aside from the injected rng."""

    def __init__(self, cols, rows, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.cols = 0
        self.rows = 0
        self._head = []
        self._speed = []
        self._glyph = []      # one glyph per cell so a trail shows varied characters
        self.resize(cols, rows)

    def _new_head(self):
        return self.rng.uniform(-self.rows, 0) if self.rows > 0 else 0.0

    def _column(self):
        return [self.rng.choice(GLYPHS) for _ in range(max(1, self.rows))]

    def resize(self, cols, rows):
        cols = max(0, int(cols))
        rows = max(0, int(rows))
        old_cols, old_rows = self.cols, self.rows
        self.cols = cols
        self.rows = rows
        if rows != old_rows:
            self._glyph = [self._column() for _ in range(min(cols, len(self._glyph)))]
        if cols == old_cols:
            return
        if cols < old_cols:
            self._head = self._head[:cols]
            self._speed = self._speed[:cols]
            self._glyph = self._glyph[:cols]
        else:
            for _ in range(old_cols, cols):
                self._head.append(self._new_head())
                self._speed.append(self.rng.uniform(0.4, 1.4))
                self._glyph.append(self._column())

    def step(self):
        if self.rows <= 0 or self.cols <= 0:
            return
        for i in range(self.cols):
            self._head[i] += self._speed[i]
            if self._head[i] - 12 > self.rows:
                self._head[i] = self._new_head()
                self._speed[i] = self.rng.uniform(0.4, 1.4)
            if self.rng.random() < 0.3:
                self._glyph[i][self.rng.randrange(len(self._glyph[i]))] = self.rng.choice(GLYPHS)

    def cells(self, faint=False):
        trail = 9
        out = []
        columns = range(0, self.cols, 2) if faint else range(self.cols)
        for x in columns:
            head = self._head[x]
            column = self._glyph[x]
            for offset in range(trail + 1):
                y = int(head) - offset
                if 0 <= y < self.rows:
                    glyph = column[y % len(column)]
                    level = 1.0 if offset == 0 else max(0.05, 1.0 - offset / trail)
                    if faint:
                        level *= 0.5
                    out.append((y, x, glyph, level))
        return out


# 5-row block letters, '█' and ' ' only. Only the letters needed to spell
# OWEN'S and AGENTS, plus space, are defined.
LOGO_FONT = {
    'O': [' ███ ', '█   █', '█   █', '█   █', ' ███ '],
    'W': ['█   █', '█   █', '█ █ █', '██ ██', '█   █'],
    'E': ['████', '█   ', '███ ', '█   ', '████'],
    'N': ['█   █', '██  █', '█ █ █', '█  ██', '█   █'],
    "'": ['██', '██', '  ', '  ', '  '],
    'S': [' ████', '█    ', ' ███ ', '    █', '████ '],
    'A': [' ███ ', '█   █', '█████', '█   █', '█   █'],
    'G': [' ████', '█    ', '█  ██', '█   █', ' ████'],
    'T': ['█████', '  █  ', '  █  ', '  █  ', '  █  '],
    ' ': ['   ', '   ', '   ', '   ', '   '],
}


def logo_lines(text):
    """5 equal-width row strings spelling text in LOGO_FONT block letters."""
    letters = [LOGO_FONT[ch] for ch in text]
    if not letters:
        return ['', '', '', '', '']
    return [' '.join(letter[row] for letter in letters) for row in range(5)]


def keyname(ch):
    """Map a curses get_wch() result to the key name oas_ui.Launcher.key() wants.

    Returns None for input that should be ignored (unmapped control codes,
    KEY_RESIZE, multi-char sequences the terminal handed back whole).
    """
    if ch in (curses.KEY_ENTER, '\n', '\r'):
        return 'enter'
    # get_wch() hands back control characters as one-character strings; the
    # integer forms are kept for terminals that report keypad codes.
    if ch in (curses.KEY_BACKSPACE, 127, 8, '\x7f', '\x08'):
        return 'backspace'
    if ch in (27, '\x1b'):
        return 'esc'
    if ch == ' ':
        return 'space'
    if ch == curses.KEY_UP:
        return 'up'
    if ch == curses.KEY_DOWN:
        return 'down'
    if ch == curses.KEY_LEFT:
        return 'left'
    if ch == curses.KEY_RIGHT:
        return 'right'
    if ch == curses.KEY_HOME:
        return 'home'
    if ch == curses.KEY_END:
        return 'end'
    if ch == curses.KEY_RESIZE:
        return None
    if isinstance(ch, str) and len(ch) == 1 and ch.isprintable():
        return ch
    return None


def _safe_addstr(stdscr, y, x, text, attr=0):
    """addstr guarded against off-screen coordinates and the bottom-right cell."""
    if not text:
        return
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or max_x <= 0:
        return
    if x < 0:
        text = text[-x:]
        x = 0
        if not text:
            return
    if x >= max_x:
        return
    avail = max_x - x
    # Writing into the final column of the final line raises in curses.
    if y == max_y - 1:
        avail -= 1
    if avail <= 0:
        return
    text = text[:avail]
    if not text:
        return
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def _init_colors(plain):
    """256-color green ramp via init_pair only; never curses.init_color."""
    names = ('head', 'bright', 'mid', 'dim', 'dark', 'red')
    if plain or not curses.has_colors():
        # Pair 0 is the terminal default; init_pair with -1 would need use_default_colors first.
        return {name: 0 for name in names}
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    if curses.COLORS >= 256:
        values = (15, 46, 40, 34, 22, 196)
    else:
        values = (curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_GREEN,
                   curses.COLOR_GREEN, curses.COLOR_GREEN, curses.COLOR_RED)
    for i, fg in enumerate(values, start=1):
        try:
            curses.init_pair(i, fg, -1)
        except curses.error:
            curses.init_pair(i, curses.COLOR_WHITE, -1)
    return dict(zip(names, range(1, len(names) + 1)))


def _pair(colors, name, fallback='bright'):
    return curses.color_pair(colors.get(name, colors.get(fallback, 1)))


def _draw_rain(stdscr, rain, colors, faint):
    head_attr = _pair(colors, 'head') | curses.A_BOLD
    bright_attr = _pair(colors, 'bright')
    mid_attr = _pair(colors, 'mid')
    dim_attr = _pair(colors, 'dim')
    for y, x, glyph, level in rain.cells(faint=faint):
        if level >= 0.95:
            attr = head_attr
        elif level >= 0.6:
            attr = bright_attr
        elif level >= 0.3:
            attr = mid_attr
        else:
            attr = dim_attr
        _safe_addstr(stdscr, y, x, glyph, attr)


def _draw_box(stdscr, y0, x0, width, height, title, attr):
    if width < 4 or height < 2:
        return
    top = '┌' + '─' * (width - 2) + '┐'
    if title:
        label = f' {title} '
        if len(label) <= width - 4:
            top = top[:2] + label + top[2 + len(label):]
    _safe_addstr(stdscr, y0, x0, top, attr)
    for i in range(1, height - 1):
        _safe_addstr(stdscr, y0 + i, x0, '│', attr)
        _safe_addstr(stdscr, y0 + i, x0 + width - 1, '│', attr)
    bottom = '└' + '─' * (width - 2) + '┘'
    _safe_addstr(stdscr, y0 + height - 1, x0, bottom, attr)


def visible_window(count, cursor, max_visible):
    """Return (start, end) so that at most max_visible rows show and cursor is inside."""
    max_visible = max(1, max_visible)
    if count <= max_visible:
        return 0, count
    start = min(max(0, cursor - max_visible // 2), count - max_visible)
    return start, start + max_visible


def _draw_rows(stdscr, y0, x0, width, rows_data, cursor, colors, start=0):
    inner = width - 4
    for i, row in enumerate(rows_data, start=start):
        y = y0 + 1 + i - start
        marker = '▸ ' if i == cursor else '  '
        if row.disabled:
            text_attr = _pair(colors, 'dark', 'dim')
        elif i == cursor:
            text_attr = _pair(colors, 'head') | curses.A_BOLD
        else:
            text_attr = _pair(colors, 'dim')
        right = row.disabled or row.detail or ''
        right_attr = _pair(colors, 'dark') if row.disabled else _pair(colors, 'dim')
        reserve = len(right) + 1 if right else 0
        left = (marker + row.text)[:max(0, inner - reserve)]
        _safe_addstr(stdscr, y, x0 + 2, left, text_attr)
        if right:
            rx = x0 + width - 2 - len(right)
            _safe_addstr(stdscr, y, rx, right, right_attr)


def _draw_panel(stdscr, y0, x0, width, rows_data, cursor, title, footer, colors, message=None, max_visible=None):
    start, end = visible_window(len(rows_data), cursor, max_visible or max(len(rows_data), 1))
    shown = rows_data[start:end]
    content = max(len(shown), 1)
    height = content + 4
    _draw_box(stdscr, y0, x0, width, height, title, _pair(colors, 'mid'))
    if shown:
        _draw_rows(stdscr, y0, x0, width, shown, cursor, colors, start)
        if start > 0:
            _safe_addstr(stdscr, y0, x0 + width - 4, '▲', _pair(colors, 'dim'))
        if end < len(rows_data):
            _safe_addstr(stdscr, y0 + height - 1, x0 + width - 4, '▼', _pair(colors, 'dim'))
    if message:
        # With rows present the message takes the spare line above the footer.
        my = y0 + 1 + content // 2 if not shown else y0 + height - 3
        mx = x0 + max(0, (width - len(message)) // 2)
        _safe_addstr(stdscr, my, mx, message, _pair(colors, 'red'))
    footer_y = y0 + height - 2
    _safe_addstr(stdscr, footer_y, x0 + 2, footer[:max(0, width - 4)], _pair(colors, 'dim'))
    return height


def _panel_geometry(cols, n_rows):
    width = min(max(50, cols - 10), max(4, cols - 2))
    x = max(0, (cols - width) // 2)
    return width, x


def _draw_home(stdscr, launcher, colors, rows, cols):
    if rows >= 24:
        logo_rows = logo_lines("OWEN'S") + logo_lines('AGENTS')
    else:
        logo_rows = ["O W E N ' S   A G E N T S"]
    n = len(logo_rows)
    ramp = (_pair(colors, 'head') | curses.A_BOLD, _pair(colors, 'bright') | curses.A_BOLD, _pair(colors, 'mid'))
    for i, line in enumerate(logo_rows):
        attr = ramp[min(len(ramp) - 1, i * len(ramp) // max(1, n))]
        x = max(0, (cols - len(line)) // 2)
        _safe_addstr(stdscr, 1 + i, x, line, attr)
    panel_rows = launcher.rows()
    width, x = _panel_geometry(cols, len(panel_rows))
    y = min(1 + n + 1, max(1, rows - (max(len(panel_rows), 1) + 5)))
    _draw_panel(stdscr, y, x, width, panel_rows, launcher.cursor.get('mode', 0),
                'mode', launcher.footer(), colors, launcher.empty_message())


def _draw_list_screen(stdscr, launcher, colors, rows, cols):
    panel_rows = launcher.rows()
    cursor = launcher.cursor.get(launcher.screen, 0)
    width, x = _panel_geometry(cols, len(panel_rows))
    max_visible = max(1, rows - 6)
    height = min(max(len(panel_rows), 1), max_visible) + 4
    y = max(1, (rows - height) // 2)
    _draw_panel(stdscr, y, x, width, panel_rows, cursor, launcher.title(), launcher.footer(), colors,
                launcher.empty_message(), max_visible)


def _draw_task_screen(stdscr, launcher, colors, rows, cols):
    width, x = _panel_geometry(cols, 0)
    height = 7  # border, blank, field, blank, message, footer, border
    y = max(1, rows // 2 - height // 2)
    _draw_box(stdscr, y, x, width, height, launcher.title(), _pair(colors, 'mid'))
    field_y = y + 2
    field_x = x + 2
    field_width = max(1, width - 4)
    text = launcher.task
    pos = min(launcher.pos, len(text))
    visible = text
    if len(visible) > field_width:
        start = max(0, pos - field_width + 1)
        visible = visible[start:start + field_width]
        pos -= start
    _safe_addstr(stdscr, field_y, field_x, visible, _pair(colors, 'bright'))
    if pos <= len(visible) and pos < field_width:
        caret_ch = visible[pos] if pos < len(visible) else ' '
        _safe_addstr(stdscr, field_y, field_x + pos, caret_ch, curses.A_REVERSE)
    message = launcher.flash or launcher.error
    if message:
        _safe_addstr(stdscr, y + height - 3, field_x, message[:field_width], _pair(colors, 'red'))
    _safe_addstr(stdscr, y + height - 2, field_x, launcher.footer()[:field_width], _pair(colors, 'dim'))


def _draw_screen(stdscr, launcher, rain, colors, rows, cols):
    is_home = launcher.screen == 'mode'
    if rain is not None:
        _draw_rain(stdscr, rain, colors, faint=not is_home)
    if launcher.screen == 'task':
        _draw_task_screen(stdscr, launcher, colors, rows, cols)
    elif is_home:
        _draw_home(stdscr, launcher, colors, rows, cols)
    else:
        _draw_list_screen(stdscr, launcher, colors, rows, cols)


def _session(stdscr, launcher, no_rain, min_cols, min_rows):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.timeout(FRAME_MS)
    colors = _init_colors(no_rain)
    rows, cols = stdscr.getmaxyx()
    rain = None if no_rain else Rain(cols, rows, random.Random())
    while not launcher.quit and launcher.launch_request is None:
        rows, cols = stdscr.getmaxyx()
        stdscr.erase()
        too_small = cols < min_cols or rows < min_rows
        if rain is not None:
            rain.resize(cols, rows)
        if too_small:
            msg = f'enlarge the terminal (min {min_cols}x{min_rows})'
            _safe_addstr(stdscr, rows // 2, max(0, (cols - len(msg)) // 2), msg, _pair(colors, 'red'))
        else:
            if rain is not None:
                rain.step()
            _draw_screen(stdscr, launcher, rain, colors, rows, cols)
        stdscr.refresh()
        try:
            ch = stdscr.get_wch()
        except curses.error:
            ch = None
        if ch is None:
            continue
        if ch == curses.KEY_RESIZE:
            continue
        name = keyname(ch)
        if name is None:
            continue
        launcher.key(name)


def run_ui(plain=False, launcher=None, call=None):
    """Entry point for `oas ui`. Raises ValueError with no terminal attached."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError('the interactive launcher needs a terminal; use oas run ...')
    import oas_ui as _oas_ui  # lazy: keeps this module importable without oas_ui present
    if launcher is None:
        launcher = _oas_ui.Launcher()
    if call is None:
        call = subprocess.call
    no_rain = bool(plain or os.environ.get('NO_COLOR'))
    try:
        while True:
            curses.wrapper(_session, launcher, no_rain, _oas_ui.MIN_COLS, _oas_ui.MIN_ROWS)
            if launcher.quit or launcher.launch_request is None:
                return 0
            cmd, workspace = launcher.launch_request
            sys.stdout.write('\033[2J\033[H')
            sys.stdout.flush()
            code = call(cmd, cwd=workspace)
            launcher.returned(code)
    except KeyboardInterrupt:
        return 0
