"""Validated input helpers.

Every helper re-asks until it gets a valid value. Typing q (or pressing
Ctrl-C / Ctrl-D) at any prompt raises Cancelled, which returns the user
to the main menu without changing anything.
"""
from datetime import date, datetime


class Cancelled(Exception):
    """The user chose to leave the current operation."""


CANCEL_WORDS = {"q", "quit", "cancel"}


def ask(prompt):
    try:
        text = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise Cancelled
    if text.lower() in CANCEL_WORDS:
        raise Cancelled
    return text


def _suffix(default):
    return f" [{default}]" if default is not None else ""


def ask_text(label, required=True, max_len=None, default=None):
    while True:
        text = ask(f"{label}{_suffix(default)}: ")
        if not text:
            if default is not None:
                return default
            if not required:
                return None
            print("  A value is required (or q to cancel).")
            continue
        if max_len and len(text) > max_len:
            print(f"  Must be at most {max_len} characters.")
            continue
        return text


def ask_int(label, min_value=None, max_value=None, default=None, required=True):
    while True:
        text = ask(f"{label}{_suffix(default)}: ")
        if not text:
            if default is not None:
                return default
            if not required:
                return None
            print("  A value is required (or q to cancel).")
            continue
        try:
            value = int(text)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if min_value is not None and value < min_value:
            print(f"  Must be at least {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"  Must be at most {max_value}.")
            continue
        return value


def ask_float(label, min_value=None, max_value=None, required=True):
    while True:
        text = ask(f"{label}: ")
        if not text:
            if not required:
                return None
            print("  A value is required (or q to cancel).")
            continue
        try:
            value = float(text)
        except ValueError:
            print("  Please enter a number, e.g. 12.5")
            continue
        if min_value is not None and value < min_value:
            print(f"  Must be at least {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"  Must be at most {max_value}.")
            continue
        return value


def ask_choice(label, options, default=None, allow_blank=False):
    """Pick one of `options` (case-insensitive). Returns the canonical spelling."""
    lookup = {o.lower(): o for o in options}
    hint = "/".join(options)
    while True:
        text = ask(f"{label} ({hint}){_suffix(default)}: ")
        if not text:
            if default is not None:
                return default
            if allow_blank:
                return None
            print("  A value is required (or q to cancel).")
            continue
        if text.lower() in lookup:
            return lookup[text.lower()]
        print(f"  Please choose one of: {', '.join(options)}.")


def ask_datetime(label, default_now=True):
    """Date and time as 'YYYY-MM-DD HH:MM'; stored as 'YYYY-MM-DD HH:MM:SS'. No future times."""
    default = datetime.now().strftime("%Y-%m-%d %H:%M") if default_now else None
    while True:
        text = ask(f"{label}{_suffix(default)}: ") or default
        if not text:
            print("  A value is required (or q to cancel).")
            continue
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                value = datetime.strptime(text, fmt)
                break
            except ValueError:
                value = None
        if value is None:
            print("  Use the format YYYY-MM-DD HH:MM, e.g. 2026-11-01 20:30")
            continue
        if value > datetime.now():
            print("  A match can't be recorded in the future.")
            continue
        return value.strftime("%Y-%m-%d %H:%M:%S")


def ask_date(label, required=False):
    """Optional date as YYYY-MM-DD; blank returns None when not required."""
    while True:
        text = ask(f"{label}: ")
        if not text:
            if not required:
                return None
            print("  A value is required (or q to cancel).")
            continue
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            print("  Use the format YYYY-MM-DD, e.g. 2026-10-01")


def confirm(label):
    while True:
        text = ask(f"{label} (y/n): ").lower()
        if text in ("y", "yes"):
            return True
        if text in ("n", "no"):
            return False
        print("  Please answer y or n.")
