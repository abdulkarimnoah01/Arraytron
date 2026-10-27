"""Single source of truth for Arraytron version names and file locations.

Scheme: vMAJOR.MINOR.PATCH with plain numbers (v0.3.5), no zero padding. MAJOR is 0 until the 1.0 production release;
MINOR is one step of the master roadmap (3 = Prototype Bank, 4 = Curve/Surface ...); PATCH is a small addition or fix inside a
step. File names use the id (Arraytron_v0.3.5.hda); the Houdini type uses the same dotted numbers (arraytron::instancer::0.3.5).
Releases before v0.3.5 keep the type names they already shipped with (0.1, 0.15, 0.16, 0.20, 0.21, 0.30), so scenes built with
them still load. Plain numbers sort correctly in natural-sort file managers (Windows Explorer); a strict plain-text sorter only
misorders a field once it reaches 10 (v0.3.10 before v0.3.2), which the roadmap does not reach before 1.0.

The current release lives in dist/; every earlier release lives in dist/archive/ (HDA, demo HIP, USD export).
Both share dist/test_assets, and render previews live in renders/.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
ARCHIVE=DIST/'archive'
RENDERS=ROOT/'renders'

# id -> metadata. 'old' is the ad-hoc name used before the scheme (kept for the docs and as an alias).
VERSIONS={
 'v0.1.0':dict(old='0.1', type='arraytron::instancer::0.1'),
 'v0.1.5':dict(old='0.15',type='arraytron::instancer::0.15'),
 'v0.1.6':dict(old='0.16',type='arraytron::instancer::0.16'),
 'v0.2.0':dict(old='0.2', type='arraytron::instancer::0.20'),
 'v0.2.1':dict(old='0.21',type='arraytron::instancer::0.21'),
 'v0.3.0':dict(old='0.3', type='arraytron::instancer::0.30',h205=True),
 'v0.3.5':dict(old='0.35',type='arraytron::instancer::0.3.5',h205=True),
 'v0.3.6':dict(old='-',type='arraytron::instancer::0.3.6',h205=True),
 'v0.4.0':dict(old='-',type='arraytron::instancer::0.4.0',h205=True),
 'v0.4.5':dict(old='-',type='arraytron::instancer::0.4.5',h205=True),
 'v0.4.6':dict(old='-',type='arraytron::instancer::0.4.6',h205=True),
 'v0.5.0':dict(old='-',type='arraytron::instancer::0.5.0',h205=True),
 'v0.5.1':dict(old='-',type='arraytron::instancer::0.5.1',h205=True),
 'v0.5.2':dict(old='-',type='arraytron::instancer::0.5.2',h205=True),
 'v0.6.0':dict(old='-',type='arraytron::instancer::0.6.0',h205=True),
 'v0.7.0':dict(old='-',type='arraytron::instancer::0.7.0',h205=True),
 'v0.8.0':dict(old='-',type='arraytron::instancer::0.8.0',h205=True),
 'v0.9.0':dict(old='-',type='arraytron::instancer::0.9.0',h205=True),
 'v1.0.0':dict(old='-',type='arraytron::instancer::1.0.0',h205=True),     # h205 on a release before v1.1.0: its Houdini 20.5 / 21 build exists only as the comparison baseline of the suites (otls_h205/, built by the same builder)
 'v1.5.0':dict(old='-',type='arraytron::instancer::1.5.0',h205=True),     # adds Imported Points (scatter on FX / imported points)
 'v1.6.0':dict(old='-',type='arraytron::instancer::1.6.0',h205=True),     # the Paint tool shortcuts (mouse wheel, Ctrl+Shift drag, keys, live prompt, coloured brush)
 'v1.6.1':dict(old='-',type='arraytron::instancer::1.6.1',h205=True),     # fix: selecting the node no longer switches the Distribution Mode to Paint
 'v1.6.2':dict(old='-',type='arraytron::instancer::1.6.2',h205=True),     # the Settle tab is called Physics
 'v1.7.0':dict(old='-',type='arraytron::instancer::1.7.0',h205=True),     # Pick Instance: click an instance in the viewport to create its override row
 'v1.8.0':dict(old='-',type='arraytron::instancer::1.8.0',h205=True),     # the built-in LOD generator
 'v1.9.0':dict(old='-',type='arraytron::instancer::1.9.0',h205=True),     # the Instance Place distribution mode
 'v1.10.0':dict(old='-',type='arraytron::instancer::1.10.0',h205=True),     # Instance Place arrays (Copy and Transform steps)
 'v1.11.0':dict(old='-',type='arraytron::instancer::1.11.0',h205=True),     # Place tool extras (snap, drag, along curve), node name arraytron1, Settle Instances label
 'v1.12.0':dict(old='-',type='arraytron::instancer::1.12.0',h205=True),     # Falloff: scale and density fade towards the edge of the layout
 'v1.13.0':dict(old='-',type='arraytron::instancer::1.13.0',h205=True),     # mode-aware Falloff (paint strokes, clusters, 3D grid); tabs Prototypes / Variation / Debugging / Export
 'v1.14.0':dict(old='-',type='arraytron::instancer::1.14.0',h205=True),     # Rows for the Line, Circle and Curve modes
 'v1.15.0':dict(old='-',type='arraytron::instancer::1.15.0',h205=True),     # the Biome distribution mode
 'v1.16.0':dict(old='-',type='arraytron::instancer::1.16.0',h205=True),     # Biome: an Effect per condition in every row
 'v1.17.0':dict(old='-',type='arraytron::instancer::1.17.0',h205=True),     # the Distribution Mode as a strip of icon cells
 'v1.18.0':dict(old='-',type='arraytron::instancer::1.18.0',h205=True),     # the Asset Library; Stagger Rows as a slider
 'v1.19.0':dict(old='-',type='arraytron::instancer::1.19.0',h205=True),     # Biome layers, exclusion and presets
 'v1.20.0':dict(old='-',type='arraytron::instancer::1.20.0',h205=True),     # the painted biome map
 'v1.21.0':dict(old='-',type='arraytron::instancer::1.21.0',h205=True),     # the LOD generator keeps materials; the all-demos scene in a grid
 'v1.21.1':dict(old='-',type='arraytron::instancer::1.21.1',h205=True),
 'v1.22.0':dict(old='-',type='arraytron::instancer::1.22.0',h205=True),
 'v1.23.0':dict(old='-',type='arraytron::instancer::1.23.0',h205=True),
 'v1.24.0':dict(old='-',type='arraytron::instancer::1.24.0',h205=True),
 'v1.25.0':dict(old='-',type='arraytron::instancer::1.25.0',h205=True),
 'v1.25.1':dict(old='-',type='arraytron::instancer::1.25.1',h205=True),     # the test setup of a new node: robust check + button     # every noise type also as the Mask noise     # Display: Boxes / Spheres proxy     # copy settings between Arraytron nodes: code and the Import Settings button     # Stagger cycles (orbit kept), Display: Points Only, position Noise for every mode     # the LOD generator also works on instanceable prototypes
 'v1.1.0':dict(old='-',type='arraytron::instancer::1.1.0',h205=True),     # adds the Houdini 20.5 / 21 build (otls_h205/); see docs/PORT_HOUDINI_205.md
}
CURRENT='v1.25.1'
# Other spellings still accepted on command lines: the first ad-hoc tags, and the short-lived zero-padded ids (v00.03.05).
ALIASES={'v01':'v0.1.0','v015':'v0.1.5','v016':'v0.1.6','v02':'v0.2.0','v021':'v0.2.1','v03':'v0.3.0','v035':'v0.3.5',
         '0.1':'v0.1.0','0.15':'v0.1.5','0.16':'v0.1.6','0.2':'v0.2.0','0.21':'v0.2.1','0.3':'v0.3.0','0.35':'v0.3.5',
         'v00.01.00':'v0.1.0','v00.01.05':'v0.1.5','v00.01.06':'v0.1.6','v00.02.00':'v0.2.0','v00.02.01':'v0.2.1','v00.03.00':'v0.3.0','v00.03.05':'v0.3.5',
         '0.1.0':'v0.1.0','0.1.5':'v0.1.5','0.1.6':'v0.1.6','0.2.0':'v0.2.0','0.2.1':'v0.2.1','0.3.0':'v0.3.0','0.3.5':'v0.3.5','0.3.6':'v0.3.6','0.4.0':'v0.4.0','0.4.5':'v0.4.5','0.4.6':'v0.4.6','0.5.0':'v0.5.0','0.5.1':'v0.5.1','0.5.2':'v0.5.2'}

def resolve(tag):
    """Accept an id (v0.3.5) or an older spelling (v035, v00.03.05)."""
    if tag in VERSIONS:return tag
    if tag in ALIASES:return ALIASES[tag]
    raise KeyError(f'unknown Arraytron version {tag!r}; known: {sorted(VERSIONS)}')

H205_DIST=ROOT/'otls_h205'
def is_h205():
    """True when the code runs for the Houdini 20.5 / 21 build: set ARRAYTRON_TARGET=h205 (or h22) to force it, otherwise a hython older than 22 selects it.
    Outside Houdini (plain Python) it is False."""
    import os
    forced=os.environ.get('ARRAYTRON_TARGET','').lower()
    if forced:return forced=='h205'
    try:import hou
    except ImportError:return False
    return hou.applicationVersion()[0]<22

def _h205(vid,h205=None):
    """True when this release has a Houdini 20.5 / 21 build and the run targets it."""
    return bool(VERSIONS[resolve(vid)].get('h205')) and (is_h205() if h205 is None else h205)

import os as _os
BUILD=resolve(_os.environ['ARRAYTRON_VERSION']) if _os.environ.get('ARRAYTRON_VERSION') else CURRENT     # release the demo builders target; set ARRAYTRON_VERSION=v1.1.0 to build its demos before it is current

def folder(vid,h205=None):
    if _h205(vid,h205):return H205_DIST
    return DIST if resolve(vid)==CURRENT else ARCHIVE
def stem(vid,h205=None):
    """File name stem: Arraytron_v1.1.0 (Houdini 22) or Arraytron_v1.1.0_H205 (Houdini 20.5 / 21)."""
    vid=resolve(vid);return f'Arraytron_{vid}'+('_H205' if _h205(vid,h205) else '')
def hda(vid,h205=None):
    """HDA file of a release. Releases with an h205 flag have a second file for Houdini 20.5 / 21 in otls_h205/ (chosen by is_h205() unless h205 is given)."""
    return folder(vid,h205)/f'{stem(vid,h205)}.hda'
def demo(vid,kind=''):
    """Demo HIP. kind '' is the main demo; 'transform' is the v0.1.0 transform demo."""
    return folder(vid)/f'{stem(vid)}_{kind+"_" if kind else ""}demo.hip'
def demo_file(vid,suffix):
    """A demo HIP by its file suffix: 'demo', 'paint_demo', 'all_demos' ..."""
    return folder(vid)/f'{stem(vid)}_{suffix}.hip'
def ensure_installed(vid):
    """Make the HDA of a release available in this session. In Houdini 20.5 / 21 the demos are built and tested with the HDA found through the scan path
    (HOUDINI_OTLSCAN_PATH=<project>/otls_h205;& ), not installed per scene: a scene that records its HDA library breaks the node type when a second scene is
    opened in the same session (the handle-binding problem in tools/h205_compat.py). Without the scan path the file is installed like before."""
    import hou
    if _h205(vid) and hou.nodeType(hou.lopNodeTypeCategory(),type_name(vid)) is not None:return
    hou.hda.installFile(str(hda(vid)))
def render_usd(vid,kind=''):
    return folder(vid)/f'{stem(vid)}_{kind+"_" if kind else ""}demo_render.usda'
def render_name(vid,kind=''):
    """Base name (no extension) of the Karma preview in renders/."""
    vid=resolve(vid);return f'arraytron_{vid}_{kind+"_" if kind else ""}demo_xpu'
def tag(vid):
    """Release id for result files: v1.1.0, or v1.1.0_H205 for the Houdini 20.5 / 21 build, so the two builds keep separate evidence."""
    vid=resolve(vid);return vid+('_H205' if _h205(vid) else '')
def validation_json(vid):return ROOT/'tests'/f'validation_{resolve(vid)}{"_H205" if _h205(vid) else ""}.json'
def type_name(vid):return VERSIONS[resolve(vid)]['type']
def assets_ref(vid):
    """$HIP-relative folder of the shared test assets, as seen from that version's HIP."""
    if _h205(vid):return '$HIP/test_assets'
    return '$HIP/test_assets' if resolve(vid)==CURRENT else '$HIP/../test_assets'
def renders_ref(vid):
    """$HIP-relative folder of renders/, as seen from that version's HIP."""
    if _h205(vid):return '$HIP/../renders'
    return '$HIP/../renders' if resolve(vid)==CURRENT else '$HIP/../../renders'

try:
    import hou as _hou
    if _hou.applicationVersion()[0]<22:
        import h205_compat;h205_compat.patch()          # reinstalling an unloaded Arraytron type needs this in Houdini 20.5 / 21
except ImportError:pass

if __name__=='__main__':
    for vid,meta in VERSIONS.items():
        print(vid,('(was v'+meta['old']+')') if meta['old']!='-' else '','type',meta['type'],'->',hda(vid).relative_to(ROOT))

def tab_names(vid):
    """The labels of the tabs that were renamed in v1.13.0: Source > Prototypes, Look > Variation, Finish > Debugging, plus the Export tab (None before v1.13.0)."""
    new=tuple(int(x) for x in resolve(vid)[1:].split('.'))>=(1,13,0)
    return dict(source='Prototypes' if new else 'Source',look='Variation' if new else 'Look',finish='Debugging' if new else 'Finish',export='Export' if new else None)
