"""Build the update release: release/update/Arraytron-<version>.zip and release/update/version.json.

    python tools/make_update_zip.py [--out release/update] [--update-source <folder or https url>]

The zip holds the same installer package as the RAR (make_release.build_release): the HDAs for
Houdini 22 and 20.5 / 21, the demos, the docs, the installer and the in-Houdini updater. The
updater downloads it, checks it against the SHA-256 in version.json and runs its install.ps1.
Publish BOTH files in one place (a GitHub release, an https address or a shared folder): that
place is the update source. With --update-source it is baked into the zip, so installed copies
already know where to look. Run tools/make_release.py first (it checks the docs and the manifest);
this tool needs the built HDAs and demos in dist/ and otls_h205/.

The version comes from tools/versions.py (CURRENT); the notes come from its CHANGELOG.md section.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOUDINI_MIN, HOUDINI_MAX_EXCLUSIVE = "20.5", "23.0"       # keep in step with VERSION.json in make_release.py


def changelog_notes(version):
    """Bullet lines of this version's CHANGELOG.md section, without markdown."""
    lines, grab = [], False
    for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if grab:
                break
            grab = line[3:].strip().lstrip("v").split(" ")[0] == version
        elif grab and line.lstrip().startswith(("*", "-")):
            text = line.strip().lstrip("*-").strip()
            lines.append(re.sub(r"[`*]", "", text))
    return lines


DEFAULT_UPDATE_SOURCE = "https://github.com/abdulkarimnoah01/Arraytron/releases/latest/download/"     # baked into every package, so an installed copy knows where its updates come from (pass --update-source "" for none)
def build(out, update_source=""):
    os.environ["ARRAYTRON_UPDATE_SOURCE_BAKED"] = update_source
    sys.path.insert(0, str(ROOT / "tools"))
    import make_release                                   # reads the baked source at import
    version = make_release.VER
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        top = make_release.build_release(Path(temp))
        archive = out / ("Arraytron-%s.zip" % version)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(top.rglob("*")):
                if path.is_file():
                    zipped.write(path, path.relative_to(top.parent).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {"name": "Arraytron", "version": version, "released": date.today().isoformat(),
                "zip": archive.name, "sha256": digest, "size": archive.stat().st_size,
                "houdini": {"min": HOUDINI_MIN, "max_exclusive": HOUDINI_MAX_EXCLUSIVE},
                "notes": changelog_notes(version)}
    (out / "version.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return archive, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(ROOT / "release" / "update"))
    parser.add_argument("--update-source", default=DEFAULT_UPDATE_SOURCE)
    arguments = parser.parse_args()
    archive, manifest = build(Path(arguments.out), arguments.update_source)
    print("built", archive, "(%.1f MB)" % (archive.stat().st_size / 1e6))
    print("sha256", manifest["sha256"])
    print("notes", len(manifest["notes"]))
    print("publish %s and version.json together" % archive.name)
