"""Regenerate dist/manifest.json: SHA-256 of every release file (HDA, HIP, USD, and the Physics Settle cache files) in dist/, dist/archive/, dist/test_assets/, dist/arraytron_cache/ and otls_h205/ (with its test_assets and arraytron_cache).
Usage: python tools/make_manifest.py   (same record format as before: [{"Path": ..., "Hash": ...}], Windows paths, upper-case hex)"""
from pathlib import Path
import hashlib, json
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist'
EXTENSIONS={'.hda','.hip','.usda','.sc'}
entries=[]
H205=ROOT/'otls_h205'          # the Houdini 20.5 / 21 build (v1.1.0 and later): HDAs, demos, caches
for folder in (DIST,DIST/'archive',DIST/'test_assets',DIST/'arraytron_cache',H205,H205/'test_assets',H205/'arraytron_cache'):
    if not folder.is_dir():continue
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in EXTENSIONS and path.name!='manifest.json':
            entries.append({'Path':str(path),'Hash':hashlib.sha256(path.read_bytes()).hexdigest().upper()})
(DIST/'manifest.json').write_text(json.dumps(entries,indent=2))
print(len(entries),'files hashed ->',DIST/'manifest.json')
