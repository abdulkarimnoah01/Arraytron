"""Build Arraytron Stamp (arraytron::stamp::<STAMP_VERSION>): hython tools/build_arraytron_stamp.py [base version]
The same builder as Arraytron (build_arraytron_v03.py, base version = the current release by default) with ARRAYTRON_STAMP set: a node that is only for placing instances by hand. It is always in
Instance Place mode (the Distribution Mode is hidden), shows the tabs Prototypes, Layout (the placing), Optimize, Debugging and Export, starts with the built-in sphere, and has the extra per-stamp
randomness (Random Scale, Random Tilt, Random Prototype) next to the Random Rotation. Writes dist/Arraytron_Stamp_v<ver>.hda, or otls_h205/Arraytron_Stamp_v<ver>_H205.hda with hython 20.5."""
import os, sys
from pathlib import Path
os.environ['ARRAYTRON_STAMP']='1'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_arraytron_v03 as builder, versions
builder.configure(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
builder.build()
