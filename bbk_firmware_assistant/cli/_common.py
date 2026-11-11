from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence

import questionary

DOWNLOADS_DIR = Path.cwd() / "downloads"
EXTRACTED_DIR = Path.cwd() / "firmware"
BLOAT_DIR = Path.cwd() / "bloat"

STYLE = questionary.Style([
    ("qmark", "fg:#00bcd4 bold"),
    ("question", "bold"),
    ("answer", "fg:#00e676 bold"),
    ("pointer", "fg:#00bcd4 bold"),
    ("highlighted", "fg:#00bcd4 bold"),
    ("selected", "fg:#00e676"),
])


def _ask(prompt_fn):
    """Run a questionary prompt, returning None when the user hits Ctrl-C."""
    try:
        return prompt_fn()
    except KeyboardInterrupt:
        return None


def ask_select(message: str, choices: Sequence[str], **kwargs):
    """Single-choice menu. Returns the chosen string, or None if cancelled."""
    return _ask(lambda: questionary.select(message, choices=list(choices), style=STYLE, **kwargs).ask())


def ask_multiselect(message: str, choices: Sequence[str], **kwargs):
    """Multi-choice menu. Returns the list of chosen strings, or None if cancelled."""
    return _ask(lambda: questionary.checkbox(message, choices=list(choices), style=STYLE, **kwargs).ask())


def ask_text(message: str, **kwargs):
    """Free-text prompt. Returns the entered string, or None if cancelled."""
    return _ask(lambda: questionary.text(message, style=STYLE, **kwargs).ask())


def ask_path(message: str, **kwargs):
    """Filesystem-path prompt. Returns the entered path, or None if cancelled."""
    return _ask(lambda: questionary.path(message, style=STYLE, **kwargs).ask())


def ask_confirm(message: str, default: bool = False, **kwargs):
    """Yes/no prompt. Returns the boolean answer, or None if cancelled."""
    return _ask(lambda: questionary.confirm(message, default=default, style=STYLE, **kwargs).ask())


def run_cmd(*cmd: str) -> int:
    """Run a command, streaming its output to the terminal. Returns the exit code."""
    return subprocess.run(cmd).returncode


def error(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)


def success(msg: str) -> None:
    print(f"  ✓ {msg}")