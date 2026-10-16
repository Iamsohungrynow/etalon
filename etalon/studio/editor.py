"""``POST /api/simulations/{id}/open``: the script in the OS's editor, never run.

On Windows and macOS the default action for ``.py`` is often to *run* it with
Python. Studio must only ever open it for editing:

- Windows: the app registered to open ``.py``, unless that app is a Python
  interpreter; then Notepad.
- macOS: ``open -t``, the default text editor.
- Linux and others: ``xdg-open``, which opens text files in an editor.
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

INTERPRETERS = frozenset({"python.exe", "pythonw.exe", "py.exe", "pyw.exe"})


def _windows_open_command(extension: str) -> str | None:
    """The command Explorer runs to open ``extension`` (honours the user's choice)."""
    if sys.platform != "win32":
        return None
    assoc_str_command = 1
    size = ctypes.c_uint(0)
    shlwapi = ctypes.windll.shlwapi
    shlwapi.AssocQueryStringW(0, assoc_str_command, extension, "open", None, ctypes.byref(size))
    if size.value == 0:
        return None
    buffer = ctypes.create_unicode_buffer(size.value)
    result = shlwapi.AssocQueryStringW(
        0, assoc_str_command, extension, "open", buffer, ctypes.byref(size)
    )
    return buffer.value if result == 0 else None


def opens_with_interpreter(command: str | None) -> bool:
    """True when an "open" command would run the file with Python instead of editing it."""
    if not command:
        return True
    text = command.strip()
    program = text[1:].split('"', 1)[0] if text.startswith('"') else text.split(" ", 1)[0]
    name = os.path.basename(program).lower()
    return name in INTERPRETERS or name.startswith("python")


def open_in_editor(path: Path) -> None:
    """Open ``path`` for editing; raises OSError if the OS cannot."""
    if sys.platform == "win32":
        if opens_with_interpreter(_windows_open_command(".py")):
            subprocess.Popen(["notepad.exe", str(path)])
        else:
            os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-t", str(path)], check=True, timeout=10)
    else:
        subprocess.Popen(["xdg-open", str(path)])
