"""
Tiny terminal styling + prompt helpers, shared across the package (cli, analyzer, config).

Standard library only. Colors switch off automatically when output is not a TTY, when
NO_COLOR is set, or when the terminal can't be put into ANSI mode.

Conventions used across the app:
  * system / status messages -> cyan, with a colored status glyph (ok/warn/fail/info)
  * headings / step banners   -> bold blue / cyan
  * what the USER types        -> shown bold + bright, distinct from program output
"""

from __future__ import annotations

import os
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
_FG = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
    "white": "\033[97m",
}
# Style applied to text the user types at a prompt (bold + bright white).
INPUT_STYLE = BOLD + _FG["white"]

_ENABLED = None


def _enable_windows_vt():
    """Turn on ANSI escape handling in the Windows console; best effort."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            os.system("")  # fallback that also enables VT on modern Windows
            return True
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VT processing
        return True
    except Exception:  # noqa: BLE001
        try:
            os.system("")
        except Exception:  # noqa: BLE001
            pass
        return True


def _detect():
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:  # noqa: BLE001
        return False
    if os.name == "nt":
        return _enable_windows_vt()
    return True


def enabled():
    global _ENABLED
    if _ENABLED is None:
        _ENABLED = _detect()
    return _ENABLED


def paint(text, *codes):
    if not enabled() or not codes:
        return text
    return "".join(codes) + text + RESET


# String helpers (return styled text so callers can embed them) --------------- #
def bold(t):
    return paint(t, BOLD)


def dim(t):
    return paint(t, DIM)


def red(t):
    return paint(t, _FG["red"])


def green(t):
    return paint(t, _FG["green"])


def yellow(t):
    return paint(t, _FG["yellow"])


def blue(t):
    return paint(t, _FG["blue"])


def cyan(t):
    return paint(t, _FG["cyan"])


def gray(t):
    return paint(t, _FG["gray"])


# Printers -------------------------------------------------------------------- #
def rule(width=60):
    print(paint("-" * width, DIM))


def title(text):
    rule()
    print(paint("  " + text, BOLD, _FG["cyan"]))
    rule()


def step(n, total, msg):
    print("\n" + paint(f"[{n}/{total}]", BOLD, _FG["blue"]) + " " + bold(msg))


def ok(msg):
    print(paint("✓", _FG["green"]) + "  " + msg)


def warn(msg):
    print(paint("!", _FG["yellow"]) + "  " + paint(msg, _FG["yellow"]))


def fail(msg):
    print(paint("✗", _FG["red"]) + "  " + paint(msg, _FG["red"]))


def info(msg):
    print(paint("›", _FG["cyan"]) + "  " + msg)


def system(msg):
    """A plain status/system line."""
    print(paint(msg, _FG["cyan"]))


def plain(msg=""):
    print(msg)


# Prompts --------------------------------------------------------------------- #
def _prefix(label, default=None):
    s = paint(label, BOLD, _FG["cyan"])
    if default:
        s += " " + dim(f"[{default}]")
    return s + paint(" › ", DIM)


def ask(label, default=None):
    """Styled prompt whose typed input is shown in a distinct color.

    Raises KeyboardInterrupt on Ctrl+C or EOF so the caller's top level can exit
    cleanly (no traceback).
    """
    try:
        sys.stdout.write(_prefix(label, default))
        if enabled():
            sys.stdout.write(INPUT_STYLE)
        sys.stdout.flush()
        value = input().strip()
    except (EOFError, KeyboardInterrupt):
        raise KeyboardInterrupt
    finally:
        if enabled():
            sys.stdout.write(RESET)
            sys.stdout.flush()
    return value or (default or "")


def confirm(label, default=True):
    answer = ask(f"{label} [{'Y/n' if default else 'y/N'}]")
    if not answer:
        return default
    return answer.strip().lower() in ("y", "yes")


def select(label, options, default=None):
    """Present a numbered menu and return the chosen option string.

    Accepts either the item number or the exact value. Empty input keeps `default` when one is
    given (shown as "(current)"). Re-prompts until a valid choice is made. Raises
    KeyboardInterrupt on Ctrl+C / EOF so the caller's top level can exit cleanly.
    """
    for i, opt in enumerate(options, 1):
        marker = dim("  (current)") if default is not None and opt == default else ""
        print(f"  {bold(str(i))}. {opt}{marker}")
    while True:
        raw = ask(label).strip()
        if not raw and default is not None:
            return default
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        if raw in options:
            return raw
        hint = " or press Enter to keep the current value" if default is not None else ""
        warn(f"Enter a number from the list{hint}.")


def ask_secret(label):
    """Hidden prompt for secrets (input not echoed). Falls back to a visible
    prompt if no TTY is available."""
    import getpass

    try:
        return getpass.getpass(_prefix(label)).strip()
    except (EOFError, KeyboardInterrupt):
        raise KeyboardInterrupt
    except Exception:  # noqa: BLE001 -- e.g. no controlling terminal
        return ask(label)
