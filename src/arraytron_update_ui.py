"""The Houdini side of updating: a few plain Houdini dialogs around arraytron_update.py.

Nothing here runs by itself. The artist clicks "Check for Updates" on the Arraytron shelf, sees
what is new and decides. Only an installed copy (the ARRAYTRON variable set by the package the
installer writes) is updated from here.
"""
import json
import os
import tempfile
from pathlib import Path

import hou

import arraytron_update as updater

TITLE = "Arraytron updates"


def _home():
    return Path(os.environ["ARRAYTRON"]) if os.environ.get("ARRAYTRON") else None


def installed_version(home):
    try:
        return json.loads((home / "VERSION.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return None


def _warn(text):
    hou.ui.displayMessage(text, title=TITLE, severity=hou.severityType.Warning)


def check_for_updates():
    home = _home()
    current = installed_version(home) if home else None
    if not current:
        hou.ui.displayMessage(
            "This Arraytron was not put in place by the Arraytron installer, so it is not "
            "updated from here. Download the latest release and run Install Arraytron.cmd.",
            title=TITLE)
        return
    prefs = hou.getenv("HOUDINI_USER_PREF_DIR")
    source = updater.update_source(prefs, home)
    if not source:
        button, value = hou.ui.readInput(
            "Where do Arraytron updates come from?\n\nPaste the shared folder or the https:// "
            "address you were given with Arraytron.",
            buttons=("Save", "Cancel"), default_choice=0, close_choice=1, title=TITLE)
        if button != 0 or not value.strip():
            return
        source = value.strip()
        updater.save_update_source(prefs, source)
    try:
        manifest = updater.check(source, current, hou.applicationVersion())
    except updater.UpdateError as exc:
        _warn(str(exc))
        return
    if manifest is None:
        hou.ui.displayMessage("Arraytron %s is up to date." % current, title=TITLE)
        return
    notes = "\n".join("  - " + note for note in manifest.get("notes", [])[:8])
    choice = hou.ui.displayMessage(
        "Arraytron %s is available (you have %s).\n\n%s\n\nInstall it now? Houdini needs a "
        "restart afterwards. Your scenes are not touched; the previous version is kept for "
        "a rollback." % (manifest["version"], current, notes or "(no notes)"),
        buttons=("Install", "Later"), default_choice=0, close_choice=1, title=TITLE)
    if choice != 0:
        return
    try:
        with tempfile.TemporaryDirectory(prefix="arraytron_download_") as folder:
            archive = updater.download(source, manifest, folder)
            ok, output = updater.install(archive)
    except updater.UpdateError as exc:
        _warn(str(exc))
        return
    if ok:
        hou.ui.displayMessage(
            "Arraytron %s is installed.\n\nRestart Houdini to start using it. Open scenes "
            "keep the version they were saved with." % manifest["version"], title=TITLE)
    else:
        _warn("The update could not be installed.\n\n" + output[-1500:])
